import os
import sys
import pandas as pd
import json
import time
from pathlib import Path
from datetime import datetime
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts._bootstrap import ensure_repo_root_on_path
ensure_repo_root_on_path()

from dotenv import load_dotenv
load_dotenv()

from tushare_mcp import deepseek_trade_signal, _call_deepseek_api
from core_v2.fetch_opencli_sop import (
    get_stock_fundamental,
    get_market_sentiment,
    get_stock_fund_flow,
    get_stock_news,
    prefetch_sop_snapshots,
    clear_sop_cache,
)
from stock_ai.news_impact import ProbabilityPaths, StockContext, analyze_stock_news_impact
from stock_ai.news_impact.formatting import format_portfolio_impact_table, format_stock_impact_card
from stock_ai.news_impact.providers import load_news_coverage
from stock_ai.limit_up_logic import (
    LimitUpContext,
    analyze_limit_up_logic,
    format_limit_up_logic_card,
)


def _limit_up_card(limit_up_result) -> str:
    if limit_up_result is None:
        return "【涨停逻辑】涨停逻辑数据未提供；不得推断封板概率。"
    return format_limit_up_logic_card(limit_up_result)


def build_holdings_prompt(
    *,
    row,
    full_code,
    name,
    fundamental,
    fund_flow,
    market_sentiment,
    tech_report,
    news_result,
    limit_up_result=None,
    diagnosis_decision=None,
):
    memory_context = ""
    if diagnosis_decision is not None:
        from stock_ai.advisor_memory.diagnosis import format_memory_context

        memory_context = f"\n{format_memory_context(diagnosis_decision)}\n"
    return f"""
        你是一个专业的A股短线交易分析师。请根据持仓、市场数据和消息影响给出条件化操作建议。
        {memory_context}

        ## 1. 持仓现状
        - 代码: {full_code} | 名称: {name}
        - 成本价: {row['成本价']} | 当前价: {row['当前价']}
        - 盈亏比例: {row['盈亏比例']} | 持仓数量: {row['证券数量']}

        ## 2. 资金流向
        - 主力净流入: {fund_flow.get('main_net_inflow', 'N/A')}

        ## 3. 消息面影响（共享消息服务）
        {format_stock_impact_card(news_result)}

        ## 4. 涨停与加速逻辑
        {_limit_up_card(limit_up_result)}

        ## 5. 基本面指标
        - PE(动): {fundamental.get('pe_ttm', 'N/A')} | PB: {fundamental.get('pb', 'N/A')}
        - 市值: {fundamental.get('total_mv', 'N/A')} | 换手: {fundamental.get('turnover_rate', 'N/A')}

        ## 6. 大盘背景
        - 上证: {market_sentiment.get('indices', {}).get('shanghai', {})}
        - 涨跌家数: {market_sentiment.get('breadth', 'N/A')}

        ## 7. 技术面趋势分析
        {tech_report}

        ## 任务要求
        1. 消息只有限修正概率；单一利好不得绕过风险门禁。
        2. 涨停逻辑必须区分直接主营、参股映射和概念标签；缺少板块共振、竞价或封单数据时必须披露。
        3. 给出持股/减仓/清仓等条件化结论，不自动下单。
        4. 输出涨停加速/趋势延续/接力失败三种路径、概率、触发价格和失效条件。
        5. 若存在决策记忆约束，禁止改变锁定动作；只解释新增证据与后续触发条件。
        """

def _holdings_df_from_db():
    from scripts.tools.portfolio_db import load_latest_closes, load_positions

    positions = load_positions()
    if not positions:
        return None
    closes = load_latest_closes([p.code for p in positions])
    rows = []
    for p in positions:
        price = closes.get(p.code)
        if price is not None and p.cost:
            pnl_pct = (price / p.cost - 1) * 100
            pnl_str = f"{pnl_pct:+.1f}%"
            current = price
        else:
            pnl_str = "N/A"
            current = price if price is not None else 0
        rows.append(
            {
                "证券代码": p.code,
                "证券名称": p.name,
                "持仓": p.shares,
                "成本价": p.cost,
                "当前价": current,
                "盈亏比例": pnl_str,
                "证券数量": p.shares,
                "上次建议": p.action,
            }
        )
    return pd.DataFrame(rows)


def analyze_holdings_v2():
    print("🚀 开始持仓全维度分析（MySQL portfolio_positions）...")
    df_holdings = _holdings_df_from_db()
    if df_holdings is None or df_holdings.empty:
        print("❌ MySQL 无持仓。请先 sync_portfolio_from_card")
        return
    if df_holdings.empty:
        print("❌ 持仓文件为空")
        return

    # 1. 获取大盘情绪
    print("📊 获取大盘情绪...")
    market_sentiment = get_market_sentiment()
    now = datetime.now().astimezone()
    news_coverage = load_news_coverage(now=now)

    stock_codes = [
        str(row["证券代码"]).zfill(6)
        for _, row in df_holdings.iterrows()
        if not str(row["证券代码"]).zfill(6).startswith(("15", "51", "58"))
    ]
    if stock_codes:
        print(f"🌐 OpenCLI SOP 批量预取 {len(stock_codes)} 只持仓基本面/资金面...")
        prefetch_sop_snapshots(stock_codes)

    reports = []
    # 过滤掉 ETF (代码长度通常不是 6 位，或者以 15, 51, 58 开头且不是股票)
    # 这里简单处理，只分析 6 位数字代码的股票
    for _, row in df_holdings.iterrows():
        code = str(row['证券代码']).zfill(6)
        name = row['证券名称']
        
        # 跳过 ETF (简单判断：15, 51, 58 开头的通常是基金)
        if code.startswith(('15', '51', '58')):
            print(f"⏩ 跳过基金/ETF: {code} ({name})")
            continue
            
        full_code = f"{code}.SH" if code.startswith(('60', '688')) else f"{code}.SZ"
        
        print(f"\n🔍 正在深度分析持仓股: {full_code} ({name})...")
        
        # 2. 获取个股多维数据
        fundamental = get_stock_fundamental(code)
        fund_flow = get_stock_fund_flow(code)
        news = get_stock_news(code)
        
        # 技术面分析
        print(f"  📈 分析技术面 (结合历史日线)...")
        try:
            tech_report = deepseek_trade_signal(full_code)
        except Exception as e:
            print(f"  ⚠️ 技术面分析失败: {e}")
            tech_report = "技术面数据获取失败"

        time.sleep(1)

        from scripts.tools.portfolio_db import load_stock_daily_bars, load_stock_profiles_by_codes

        profile = load_stock_profiles_by_codes([code]).get(code, {})
        profile_concepts = tuple(profile.get("concepts") or ())
        stock = StockContext(
            code,
            name,
            fundamental.get("industry") or fundamental.get("行业") or profile.get("industry") or "",
            tuple(fundamental.get("concepts") or profile_concepts),
        )
        news_result = analyze_stock_news_impact(
            stock,
            list(news_coverage.events),
            ProbabilityPaths(35, 45, 20),
            now=now,
            existing_holding=True,
        )
        concepts = tuple(profile.get("concepts") or stock.concepts)
        mapped_sectors = {
            sector
            for impact in news_result.impacts
            for sector in impact.mapped_sectors
        }
        active_themes = tuple(
            concept
            for concept in concepts
            if any(concept in sector or sector in concept for sector in mapped_sectors)
        )
        main_pct = fund_flow.get("main_net_pct")
        try:
            main_pct = float(main_pct) if main_pct is not None else None
        except (TypeError, ValueError):
            main_pct = None
        bars = load_stock_daily_bars(code, limit=60)
        limit_up_result = (
            analyze_limit_up_logic(
                code,
                name,
                bars,
                LimitUpContext(
                    concepts=concepts,
                    active_themes=active_themes,
                    main_net_inflow_ratio=main_pct,
                    material_risk=news_result.veto.new_risk_forbidden,
                    material_risk_reasons=news_result.veto.reasons,
                    observed_at=now,
                ),
            )
            if bars
            else None
        )
        from stock_ai.advisor_memory.diagnosis import prepare_diagnosis
        from stock_ai.advisor_memory.hard_events import HardEventInputs, detect_hard_events
        from stock_ai.advisor_memory.repository import AdvisorLedgerRepository
        from stock_ai.trading_calendar import is_a_share_trading_day
        from scripts.tools.portfolio_db import get_engine

        as_of = now.date()
        calendar_start = as_of - timedelta(days=14)
        calendar_end = as_of + timedelta(days=21)
        decision_calendar = tuple(
            calendar_start + timedelta(days=offset)
            for offset in range((calendar_end - calendar_start).days + 1)
            if is_a_share_trading_day(calendar_start + timedelta(days=offset))
        )
        decision_engine = get_engine()
        if decision_engine is None:
            raise RuntimeError("未配置 MYSQL_URL，无法读取决策记忆")
        with decision_engine.begin() as decision_conn:
            from stock_ai.advisor_memory.trade_plan import build_trade_plan

            initial_action = str(row.get("上次建议") or "").strip() or "持有观察"
            proposed_plan = build_trade_plan(
                initial_action,
                current_price=float(row.get("当前价") or 0) or None,
                bars=bars,
            )
            repository = AdvisorLedgerRepository(decision_conn)
            active_cycle = repository.load_active_cycle_model(code)
            cycle_plan = dict(active_cycle.trigger_plan) if active_cycle and active_cycle.trigger_plan else proposed_plan
            previous_price = (
                float(bars[-2]["close"])
                if len(bars) >= 2 and bars[-2].get("close") is not None
                else None
            )
            hard_events = detect_hard_events(
                HardEventInputs(
                    price=float(row.get("当前价") or 0) or None,
                    previous_price=previous_price,
                    support_price=cycle_plan.get("defense_trigger_price"),
                    pressure_price=cycle_plan.get("strength_trigger_price"),
                    material_risk=news_result.veto.new_risk_forbidden,
                    material_risk_reasons=tuple(news_result.veto.reasons),
                    observed_at=now,
                )
            )
            diagnosis_decision = prepare_diagnosis(
                code,
                name=name,
                as_of=as_of,
                trading_days=decision_calendar,
                hard_events=hard_events,
                repository=repository,
                initial_action=initial_action,
                trigger_plan=cycle_plan,
            )
        combined_prompt = build_holdings_prompt(
            row=row,
            full_code=full_code,
            name=name,
            fundamental=fundamental,
            fund_flow=fund_flow,
            market_sentiment=market_sentiment,
            tech_report=tech_report,
            news_result=news_result,
            limit_up_result=limit_up_result,
            diagnosis_decision=diagnosis_decision,
        )
        
        print(f"  🧠 DeepSeek 综合决策中...")
        try:
            from scripts.tools.decision_context import inject_decision_context

            ai_report = _call_deepseek_api(
                inject_decision_context(combined_prompt), temperature=0.2
            )
            from stock_ai.advisor_memory.diagnosis import enforce_locked_action

            final_report, rejected = enforce_locked_action(ai_report, diagnosis_decision)
            if rejected:
                with decision_engine.begin() as decision_conn:
                    AdvisorLedgerRepository(decision_conn).append_decision_event(
                        cycle_id=int(diagnosis_decision.cycle_id),
                        event_type="AI_ACTION_REJECTED",
                        previous_action=diagnosis_decision.previous_action,
                        new_action=diagnosis_decision.locked_action,
                        reason={"reason": "conflicting_ai_action"},
                        evidence={"ai_action_removed": True},
                        source="diagnosis_guard",
                        observed_at=now,
                        effective_trade_date=as_of,
                    )
            reports.append({
                'full_code': full_code,
                'name': name,
                'profit_loss': row['盈亏比例'],
                'final_report': final_report,
                'news_result': news_result,
            })
        except Exception as e:
            print(f"  ❌ AI 决策失败: {e}")

    # 4. 生成报告
    date_str = datetime.now().strftime("%Y%m%d")
    output_md = f"output/holdings_operation_advice_{date_str}.md"
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(f"# 📋 持仓股票操作建议报告 ({date_str})\n\n")
        f.write(f"## 🌍 市场环境\n")
        f.write(f"- 上证指数: {market_sentiment.get('上证指数')}\n")
        f.write(f"- 涨跌分布: {market_sentiment.get('涨跌分布')}\n\n")
        
        f.write(f"## 📊 持仓诊断摘要\n\n")
        f.write("## 消息面影响摘要\n\n")
        f.write(format_portfolio_impact_table({r['full_code'].split('.')[0]: r['news_result'] for r in reports}))
        f.write("\n\n")
        f.write("| 股票 | 盈亏 | 操作建议 | 核心逻辑摘要 |\n")
        f.write("|---|---|---|---|\n")
        for r in reports:
            # 提取第一行建议
            advice = r['final_report'].split('\n')[0].replace('操作建议:', '').strip()
            logic = r['final_report'].split('\n')[1].replace('核心逻辑:', '').strip()[:50] + "..."
            f.write(f"| {r['name']} ({r['full_code']}) | {r['profit_loss']} | **{advice}** | {logic} |\n")
        
        f.write("\n---\n\n")
        for r in reports:
            f.write(f"### 🎯 {r['name']} ({r['full_code']})\n\n")
            f.write(r['final_report'])
            f.write("\n\n---\n\n")

    print(f"\n✨ 持仓分析完成！报告已保存至: {output_md}")

if __name__ == "__main__":
    analyze_holdings_v2()
