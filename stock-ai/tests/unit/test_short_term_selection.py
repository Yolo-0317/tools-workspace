from __future__ import annotations

from datetime import date, timedelta
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ANALYSIS_DATE = date(2026, 8, 10)


def _breakout_bars() -> list[dict[str, object]]:
    bars: list[dict[str, object]] = []
    closes = [10.0 + index * 0.025 for index in range(64)] + [12.20]
    for index, close in enumerate(closes):
        trade_date = ANALYSIS_DATE - timedelta(days=len(closes) - 1 - index)
        if index == len(closes) - 1:
            open_price, high, low, amount = 11.68, 12.30, 11.80, 225_000.0
        else:
            open_price, high, low, amount = close - 0.03, close + 0.10, close - 0.10, 150_000.0
        bars.append(
            {
                "trade_date": trade_date.isoformat(),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "pct_chg": 5.4 if index == len(closes) - 1 else 0.2,
                "amount": amount,
            }
        )
    return bars


def _pullback_bars() -> list[dict[str, object]]:
    leading = [8.0 + index * (2.5 / 54) for index in range(55)]
    closes = leading + [10.60, 10.80, 11.00, 11.30, 11.60, 12.00, 11.90, 11.75, 11.65, 11.62]
    bars: list[dict[str, object]] = []
    for index, close in enumerate(closes):
        trade_date = ANALYSIS_DATE - timedelta(days=len(closes) - 1 - index)
        if index == len(closes) - 1:
            open_price, high, low, amount, pct_chg = 11.50, 11.72, 11.40, 90_000.0, -0.26
        else:
            open_price, high, low, amount, pct_chg = close - 0.03, close + 0.10, close - 0.10, 140_000.0, 0.4
        bars.append(
            {
                "trade_date": trade_date.isoformat(),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "pct_chg": pct_chg,
                "amount": amount,
            }
        )
    return bars


def test_breakout_prior_high_excludes_the_analysis_bar() -> None:
    short_term_selection = importlib.import_module("stock_ai.short_term_selection")
    result = short_term_selection.select_short_term_candidates(
        analysis_date=ANALYSIS_DATE,
        rows=[
            {
                "代码": "600001",
                "名称": "浦发银行",
                "所属行业": "银行",
                "策略来源": "综合+底部突破",
            }
        ],
        bars_by_code={"600001": _breakout_bars()},
        holding_codes=set(),
        st_codes=set(),
    )

    assert [(item.code, item.candidate_type) for item in result.candidates] == [
        ("600001", "BREAKOUT")
    ]
    assert round(result.candidates[0].metrics["prior_high20"], 3) == 11.675
    assert result.candidates[0].setup_score >= 70


def test_selector_detects_a_shrinking_volume_pullback() -> None:
    short_term_selection = importlib.import_module("stock_ai.short_term_selection")
    result = short_term_selection.select_short_term_candidates(
        analysis_date=ANALYSIS_DATE,
        rows=[
            {
                "代码": "000001",
                "名称": "平安银行",
                "所属行业": "银行",
                "策略来源": "MA5+五因子",
            }
        ],
        bars_by_code={"000001": _pullback_bars()},
        holding_codes=set(),
        st_codes=set(),
    )

    assert [(item.code, item.candidate_type) for item in result.candidates] == [
        ("000001", "PULLBACK")
    ]
    assert 0.02 <= result.candidates[0].metrics["drawdown_from_high"] <= 0.10
    assert result.candidates[0].setup_score >= 70


def test_selector_excludes_holdings_and_risk_names() -> None:
    short_term_selection = importlib.import_module("stock_ai.short_term_selection")
    rows = [
        {"代码": "600001", "名称": "浦发银行", "所属行业": "银行", "策略来源": "综合+底部突破"},
        {"代码": "600002", "名称": "*ST测试", "所属行业": "工业", "策略来源": "综合+底部突破"},
    ]
    result = short_term_selection.select_short_term_candidates(
        analysis_date=ANALYSIS_DATE,
        rows=rows,
        bars_by_code={"600001": _breakout_bars(), "600002": _breakout_bars()},
        holding_codes={"600001"},
        st_codes=set(),
    )

    assert result.candidates == ()
    assert {(item.code, item.reason) for item in result.rejected} == {
        ("600001", "当前持仓"),
        ("600002", "风险股票"),
    }


def test_selector_rejects_incomplete_stale_suspended_illiquid_and_overheated_data() -> None:
    short_term_selection = importlib.import_module("stock_ai.short_term_selection")
    stale = [
        {
            **bar,
            "trade_date": (date.fromisoformat(str(bar["trade_date"])) - timedelta(days=1)).isoformat(),
        }
        for bar in _breakout_bars()
    ]
    suspended = _breakout_bars()
    suspended[-1] = {**suspended[-1], "amount": 0.0}
    illiquid = [{**bar, "amount": 50_000.0} for bar in _breakout_bars()]
    illiquid[-1] = {**illiquid[-1], "amount": 75_000.0}
    overheated = _breakout_bars()
    overheated[-1] = {**overheated[-1], "pct_chg": 8.0}
    rows = [
        {"代码": code, "名称": code, "所属行业": "测试", "策略来源": "综合+底部突破"}
        for code in ("600010", "600011", "600012", "600013", "600014")
    ]

    result = short_term_selection.select_short_term_candidates(
        analysis_date=ANALYSIS_DATE,
        rows=rows,
        bars_by_code={
            "600010": _breakout_bars()[-59:],
            "600011": stale,
            "600012": suspended,
            "600013": illiquid,
            "600014": overheated,
        },
        holding_codes=set(),
        st_codes=set(),
    )

    assert {(item.code, item.reason) for item in result.rejected} == {
        ("600010", "上市不足60个交易日"),
        ("600011", "最近日线日期不匹配"),
        ("600012", "停牌或日线字段无效"),
        ("600013", "流动性不足"),
        ("600014", "当日涨幅超过7%"),
    }


def test_selector_rejects_duplicate_daily_dates() -> None:
    short_term_selection = importlib.import_module("stock_ai.short_term_selection")
    bars = _breakout_bars()
    bars[-2] = {**bars[-2], "trade_date": bars[-3]["trade_date"]}

    result = short_term_selection.select_short_term_candidates(
        analysis_date=ANALYSIS_DATE,
        rows=[{"代码": "600020", "名称": "测试", "所属行业": "测试", "策略来源": "综合+底部突破"}],
        bars_by_code={"600020": bars},
        holding_codes=set(),
        st_codes=set(),
    )

    assert result.candidates == ()
    assert [(item.code, item.reason) for item in result.rejected] == [
        ("600020", "日线交易日重复")
    ]


def _candidate(code: str, candidate_type: str, score: float, sector: str):
    short_term_selection = importlib.import_module("stock_ai.short_term_selection")
    return short_term_selection.CandidateSignal(
        code=code,
        name=code,
        sector=sector,
        candidate_type=candidate_type,
        setup_score=score,
        liquidity_score=0.8,
        trend_score=0.8,
        catalyst_score=0.0,
        source_strategies=("综合", "MA5"),
        reasons=("fixture",),
        metrics={"risk_reward_hint": 2.0, "average_amount5": 200_000.0},
    )


def test_allocator_enforces_shape_quotas_and_sector_cap() -> None:
    short_term_selection = importlib.import_module("stock_ai.short_term_selection")
    candidates = (
        _candidate("600101", "BREAKOUT", 99, "银行"),
        _candidate("600102", "BREAKOUT", 98, "银行"),
        _candidate("600103", "BREAKOUT", 97, "银行"),
        _candidate("600104", "BREAKOUT", 96, "电力"),
        _candidate("000101", "PULLBACK", 95, "电力"),
        _candidate("000102", "PULLBACK", 94, "消费"),
        _candidate("000103", "PULLBACK", 93, "科技"),
    )

    selected = short_term_selection.allocate_candidates(candidates)

    assert len(selected) == 5
    assert sum(item.candidate_type == "BREAKOUT" for item in selected) == 3
    assert sum(item.candidate_type == "PULLBACK" for item in selected) == 2
    assert max(sum(item.sector == sector for item in selected) for sector in {item.sector for item in selected}) == 2


def test_allocator_fills_unused_pullback_slot_with_breakout() -> None:
    short_term_selection = importlib.import_module("stock_ai.short_term_selection")
    candidates = tuple(
        _candidate(f"60020{index}", "BREAKOUT", 95 - index, f"行业{index}")
        for index in range(5)
    ) + (_candidate("000201", "PULLBACK", 89, "消费"),)

    selected = short_term_selection.allocate_candidates(candidates)

    assert len(selected) == 5
    assert sum(item.candidate_type == "BREAKOUT" for item in selected) == 4
    assert sum(item.candidate_type == "PULLBACK" for item in selected) == 1


def test_allocator_keeps_only_the_best_shape_for_one_code() -> None:
    short_term_selection = importlib.import_module("stock_ai.short_term_selection")
    candidates = (
        _candidate("600300", "BREAKOUT", 80, "工业"),
        _candidate("600300", "PULLBACK", 86, "工业"),
        _candidate("600301", "BREAKOUT", 82, "银行"),
    )

    selected = short_term_selection.allocate_candidates(candidates)

    assert [item.code for item in selected].count("600300") == 1
    selected_shape = next(item.candidate_type for item in selected if item.code == "600300")
    assert selected_shape == "PULLBACK"


def test_selector_applies_the_sector_cap_to_final_candidates() -> None:
    short_term_selection = importlib.import_module("stock_ai.short_term_selection")
    codes = ("600401", "600402", "600403")
    result = short_term_selection.select_short_term_candidates(
        analysis_date=ANALYSIS_DATE,
        rows=[
            {"代码": code, "名称": code, "所属行业": "银行", "策略来源": "综合+底部突破"}
            for code in codes
        ],
        bars_by_code={code: _breakout_bars() for code in codes},
        holding_codes=set(),
        st_codes=set(),
        max_per_sector=2,
    )

    assert len(result.candidates) == 2
