from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.news_impact import ProbabilityPaths, StockContext, analyze_stock_news_impact
from stock_ai.limit_up_logic import (
    LimitUpPaths,
    LimitUpResult,
    LimitUpScoreBreakdown,
)
from core_v2.analyze_specific_stocks import build_single_stock_prompt
from scripts.analysis.analyze_holdings_v2 import build_holdings_prompt
from stock_ai.advisor_memory.diagnosis import DiagnosisDecision
from stock_ai.advisor_memory.models import CycleStatus


NOW = datetime(2026, 8, 12, 9, 0, tzinfo=timezone(timedelta(hours=8)))
RESULT = analyze_stock_news_impact(
    StockContext("600186", "莲花控股", "食品", ("算力租赁",)),
    [],
    ProbabilityPaths(35, 45, 20),
    now=NOW,
    existing_holding=True,
)
LIMIT_UP_RESULT = LimitUpResult(
    code="600186",
    name="莲花控股",
    identity="SECOND_WAVE_CANDIDATE",
    gene="STRONG",
    score=LimitUpScoreBreakdown(30, 24, 10, 5),
    paths=LimitUpPaths(40, 40, 20),
    drivers=("首板后连续承接，未破首板低点",),
    prerequisites=("板块形成共振",),
    suppressors=("封单数据缺失",),
    missing_fields=("auction_strength", "seal_quality"),
    data_cutoff=NOW,
)
MEMORY_DECISION = DiagnosisDecision(
    cycle_id=1,
    cycle_day=2,
    next_review_date=NOW.date(),
    expiry_date=NOW.date(),
    previous_action="持有观察",
    locked_action="持有观察",
    relation="维持",
    status=CycleStatus.ACTIVE,
    hard_events=(),
    allowed_actions=("持有观察",),
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


def test_single_stock_prompt_contains_shared_limit_up_card():
    prompt = build_single_stock_prompt(
        full_code="600186.SH",
        fundamental={"name": "莲花控股", "industry": "食品"},
        fund_flow={},
        market_sentiment={},
        tech_report="技术摘要",
        news_result=RESULT,
        limit_up_result=LIMIT_UP_RESULT,
    )
    assert "【涨停逻辑】" in prompt
    assert "涨停加速40%" in prompt
    assert "区分直接主营、参股映射和概念标签" in prompt


def test_holdings_prompt_discloses_missing_limit_up_data():
    prompt = build_holdings_prompt(
        row={"成本价": 11.41, "当前价": 11.45, "盈亏比例": "+0.4%", "证券数量": 500},
        full_code="600186.SH",
        name="莲花控股",
        fundamental={},
        fund_flow={},
        market_sentiment={},
        tech_report="技术摘要",
        news_result=RESULT,
        limit_up_result=None,
    )
    assert "涨停逻辑数据未提供" in prompt


def test_holdings_prompt_contains_locked_decision_memory():
    prompt = build_holdings_prompt(
        row={"成本价": 10.0, "当前价": 10.1, "盈亏比例": "+1%", "证券数量": 500},
        full_code="600000.SH",
        name="测试股份",
        fundamental={},
        fund_flow={},
        market_sentiment={},
        tech_report="技术摘要",
        news_result=RESULT,
        diagnosis_decision=MEMORY_DECISION,
    )

    assert "当前周期第2/5日" in prompt
    assert "锁定动作：持有观察" in prompt
    assert "禁止改变锁定动作" in prompt
