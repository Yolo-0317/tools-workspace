import os
import sys
import pandas as pd
import json
import time
from pathlib import Path
from datetime import datetime

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

        # 3. 整合 Prompt 发给 DeepSeek
        combined_prompt = f"""
        你是一个顶级的量化私募策略师。请根据以下【持仓数据】和【全维度市场数据】，给出该股票今天的具体操作建议。

        ## 1. 持仓现状
        - 代码: {full_code} | 名称: {name}
        - 成本价: {row['成本价']} | 当前价: {row['当前价']}
        - 盈亏比例: {row['盈亏比例']} | 持仓数量: {row['证券数量']}

        ## 2. 资金流向 (OpenCLI SOP)
        - 主力净流入: {fund_flow.get('main_net_inflow', 'N/A')}

        ## 3. 舆情新闻 (最近 3 条)
        {chr(10).join(['- ' + str(n) for n in news[:3]]) if news else '暂无重大新闻'}

        ## 4. 基本面指标
        - PE(动): {fundamental.get('pe_ttm', 'N/A')} | PB: {fundamental.get('pb', 'N/A')}
        - 市值: {fundamental.get('total_mv', 'N/A')} | 换手: {fundamental.get('turnover_rate', 'N/A')}

        ## 5. 大盘背景
        - 上证: {market_sentiment.get('indices', {}).get('shanghai', {})}
        - 涨跌家数: {market_sentiment.get('breadth', 'N/A')}

        ## 6. 技术面趋势分析 (基于历史日线)
        {tech_report}

        ## 任务要求
        1. **盈亏诊断**：分析当前盈亏的原因（是系统性回调、个股走弱、还是正常震荡）。
        2. **操作建议**：给出明确指令：加仓 / 减仓 / 持股不动 / 清仓。
        3. **核心理由**：结合资金流、技术面支撑/压力位、以及基本面。
        4. **今日计划**：给出具体的触发价格和预期目标。

        ## 输出格式
        操作建议: [加仓/减仓/持股/清仓]
        核心逻辑: [简述理由]
        今日计划: [触发价/目标/止损]
        """
        
        print(f"  🧠 DeepSeek 综合决策中...")
        try:
            from scripts.tools.decision_context import inject_decision_context

            final_report = _call_deepseek_api(
                inject_decision_context(combined_prompt), temperature=0.2
            )
            reports.append({
                'full_code': full_code,
                'name': name,
                'profit_loss': row['盈亏比例'],
                'final_report': final_report
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
