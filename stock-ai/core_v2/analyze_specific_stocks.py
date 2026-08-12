import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import ensure_repo_root_on_path
ensure_repo_root_on_path()

from dotenv import load_dotenv
load_dotenv()

from tushare_mcp import deepseek_trade_signal, _call_deepseek_api
from fetch_opencli_sop import (
    get_stock_fundamental, 
    get_market_sentiment, 
    get_stock_fund_flow, 
    get_stock_news
)
from stock_ai.news_impact import ProbabilityPaths, StockContext, analyze_stock_news_impact
from stock_ai.news_impact.formatting import format_stock_impact_card
from stock_ai.news_impact.providers import load_news_coverage


def build_single_stock_prompt(
    *, full_code, fundamental, fund_flow, market_sentiment, tech_report, news_result
):
    news_card = format_stock_impact_card(news_result)
    return f"""
        你是一个专业的A股短线交易分析师。请根据以下全维度数据给出条件化决策支持。

        ## 1. 股票基础
        - 代码: {full_code} | 名称: {fundamental.get('name') or fundamental.get('名称', 'N/A')} | 行业: {fundamental.get('industry') or fundamental.get('行业', 'N/A')}

        ## 2. 资金流向
        - 主力净流入: {fund_flow.get('main_net_inflow', fund_flow.get('今日主力净流入', 'N/A'))}
        - 净流入占比: {fund_flow.get('main_net_pct', fund_flow.get('主力净流入占比', 'N/A'))}

        ## 3. 消息面影响（共享消息服务）
        {news_card}

        ## 4. 基本面指标
        - PE(动): {fundamental.get('pe_ttm', fundamental.get('市盈率-动态', 'N/A'))} | PB: {fundamental.get('pb', fundamental.get('市净率', 'N/A'))}
        - 总市值: {fundamental.get('total_mv', fundamental.get('总市值', 'N/A'))}

        ## 5. 大盘背景
        - 指数: {market_sentiment.get('上证指数', 'N/A')}
        - 涨跌分布: {market_sentiment.get('涨跌分布', 'N/A')}

        ## 6. 技术面预分析
        {tech_report}

        ## 任务要求
        1. 消息只允许有限修正概率，不得用单一利好绕过风险门禁。
        2. 输出交易结论、核心逻辑、强/中/弱三种路径及对应条件。
        3. 明确支撑、压力、失效条件、风险预算和数据缺口。
        """

def analyze_specific_stocks(codes):
    print(f"🚀 开始对指定股票进行全维度分析: {codes}...")
    
    # 1. 获取全局信息
    print("📊 获取大盘情绪...")
    market_sentiment = get_market_sentiment()
    now = datetime.now().astimezone()
    news_coverage = load_news_coverage(now=now)
    
    reports = []
    for code in codes:
        code_6 = "".join(filter(str.isdigit, str(code)))[:6]
        full_code = f"{code_6}.SH" if code_6.startswith(('60', '688')) else f"{code_6}.SZ"
        
        print(f"\n🔍 正在深度挖掘: {full_code}...")
        
        # 2. 获取个股多维数据
        fundamental = get_stock_fundamental(code_6)
        fund_flow = get_stock_fund_flow(code_6)
        news = get_stock_news(code_6)
        
        # 技术面分析
        print(f"  📈 分析技术面...")
        try:
            tech_report = deepseek_trade_signal(full_code)
        except Exception as e:
            print(f"  ⚠️ 技术面分析失败: {e}")
            tech_report = "技术面数据获取失败"

        time.sleep(1)

        stock = StockContext(
            code_6,
            fundamental.get("name") or fundamental.get("名称") or code_6,
            fundamental.get("industry") or fundamental.get("行业") or "",
            tuple(fundamental.get("concepts") or ()),
        )
        news_result = analyze_stock_news_impact(
            stock,
            list(news_coverage.events),
            ProbabilityPaths(35, 45, 20),
            now=now,
            existing_holding=False,
        )
        combined_prompt = build_single_stock_prompt(
            full_code=full_code,
            fundamental=fundamental,
            fund_flow=fund_flow,
            market_sentiment=market_sentiment,
            tech_report=tech_report,
            news_result=news_result,
        )
        
        print(f"  🧠 DeepSeek 综合决策中...")
        try:
            final_report = _call_deepseek_api(combined_prompt, temperature=0.3)
            reports.append({
                'full_code': full_code,
                'fundamental': fundamental,
                'fund_flow': fund_flow,
                'news': news,
                'final_report': final_report
            })
        except Exception as e:
            print(f"  ❌ AI 决策失败: {e}")

    # 4. 输出结果
    print("\n" + "="*50)
    print("🚀 指定股票分析报告")
    print("="*50)
    for r in reports:
        print(f"\n### {r['fundamental'].get('名称')} ({r['full_code']})")
        print(f"AI 结论: {r['final_report']}")
        print("-" * 30)

if __name__ == "__main__":
    analyze_specific_stocks(["600098", "002258"])
