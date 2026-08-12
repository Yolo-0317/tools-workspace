from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.news_impact import ProbabilityPaths, StockContext, analyze_stock_news_impact
from core_v2.analyze_specific_stocks import build_single_stock_prompt
from scripts.analysis.analyze_holdings_v2 import build_holdings_prompt


NOW = datetime(2026, 8, 12, 9, 0, tzinfo=timezone(timedelta(hours=8)))
RESULT = analyze_stock_news_impact(
    StockContext("600186", "莲花控股", "食品", ("算力租赁",)),
    [],
    ProbabilityPaths(35, 45, 20),
    now=NOW,
    existing_holding=True,
)


def test_single_stock_prompt_contains_shared_news_card():
    prompt = build_single_stock_prompt(
        full_code="600186.SH",
        fundamental={"name": "莲花控股", "industry": "食品"},
        fund_flow={},
        market_sentiment={},
        tech_report="技术摘要",
        news_result=RESULT,
    )
    assert "【消息面影响】" in prompt
    assert "海外公司新闻覆盖不足" in prompt
    assert "最终概率：强35% / 中45% / 弱20%" in prompt


def test_holdings_prompt_contains_shared_news_card():
    prompt = build_holdings_prompt(
        row={"成本价": 11.41, "当前价": 11.45, "盈亏比例": "+0.4%", "证券数量": 500},
        full_code="600186.SH",
        name="莲花控股",
        fundamental={},
        fund_flow={},
        market_sentiment={},
        tech_report="技术摘要",
        news_result=RESULT,
    )
    assert "【消息面影响】" in prompt
    assert "消息数据缺失" not in prompt
    assert "最终概率：强35% / 中45% / 弱20%" in prompt
