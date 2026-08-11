from __future__ import annotations

from datetime import date, timedelta
import importlib
import importlib.util
import sys
from pathlib import Path

import pytest


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


def _strict_snapshot(**changes: float):
    indicators = importlib.import_module("stock_ai.technical_indicators")
    values = {
        "adx14": 25.0,
        "rsi14": 60.0,
        "atr14": 0.24,
        "atr_pct": 0.02,
        "trend_r2_20": 0.70,
        "trend_slope_20": 0.01,
        "return20": 0.10,
        "breakout_pct": 0.02,
        "average_amount5": 150_000.0,
        "amount_ratio": 1.5,
        "advance_amount5": 150_000.0,
        "pullback_amount5": 105_000.0,
        "pullback_amount_ratio": 0.70,
    }
    values.update(changes)
    return indicators.TechnicalIndicatorSnapshot(**values)


def _strict_result(
    monkeypatch,
    *,
    candidate_type: str = "BREAKOUT",
    snapshot=None,
    relative_strength: float | None = 0.90,
    bars: list[dict[str, object]] | None = None,
):
    selection = importlib.import_module("stock_ai.short_term_selection")
    monkeypatch.setattr(
        selection,
        "compute_technical_indicators",
        lambda _: snapshot or _strict_snapshot(),
    )
    code = "600001" if candidate_type == "BREAKOUT" else "000001"
    relative_strength_by_code = (
        {} if relative_strength is None else {code: relative_strength}
    )
    return selection.select_short_term_candidates(
        analysis_date=ANALYSIS_DATE,
        rows=[
            {
                "代码": code,
                "名称": "测试股票",
                "所属行业": "测试",
                "策略来源": "综合+底部突破",
            }
        ],
        bars_by_code={
            code: bars
            or (_breakout_bars() if candidate_type == "BREAKOUT" else _pullback_bars())
        },
        relative_strength_by_code=relative_strength_by_code,
        policy=selection.STRICT_A,
        holding_codes=set(),
        st_codes=set(),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("adx14", 22.0),
        ("rsi14", 55.0),
        ("rsi14", 70.0),
        ("atr_pct", 0.015),
        ("atr_pct", 0.05),
        ("trend_r2_20", 0.55),
        ("breakout_pct", 0.005),
        ("breakout_pct", 0.04),
        ("amount_ratio", 2.5),
    ),
)
def test_strict_breakout_accepts_exact_gate_boundaries(
    monkeypatch, field: str, value: float
) -> None:
    result = _strict_result(monkeypatch, snapshot=_strict_snapshot(**{field: value}))

    assert [(item.code, item.candidate_type) for item in result.candidates] == [
        ("600001", "BREAKOUT")
    ]


@pytest.mark.parametrize(
    ("changes", "relative_strength", "reason"),
    (
        ({"trend_slope_20": 0.0}, 0.90, "TREND_NOT_POSITIVE"),
        ({"adx14": 21.99}, 0.90, "ADX_WEAK"),
        ({"rsi14": 54.99}, 0.90, "RSI_WEAK"),
        ({"rsi14": 70.01}, 0.90, "RSI_OVERHEATED"),
        ({"atr_pct": 0.0149}, 0.90, "VOLATILITY_OUT_OF_RANGE"),
        ({"atr_pct": 0.0501}, 0.90, "VOLATILITY_OUT_OF_RANGE"),
        ({"trend_r2_20": 0.549}, 0.90, "TREND_UNSTABLE"),
        ({}, 0.749, "RELATIVE_STRENGTH_LOW"),
        ({"breakout_pct": 0.0049}, 0.90, "BREAKOUT_TOO_SHALLOW"),
        ({"breakout_pct": 0.0401}, 0.90, "BREAKOUT_OVEREXTENDED"),
        ({"amount_ratio": 2.501}, 0.90, "VOLUME_EXPANSION_EXCESSIVE"),
    ),
)
def test_strict_breakout_rejects_each_failed_gate(
    monkeypatch,
    changes: dict[str, float],
    relative_strength: float,
    reason: str,
) -> None:
    result = _strict_result(
        monkeypatch,
        snapshot=_strict_snapshot(**changes),
        relative_strength=relative_strength,
    )

    assert [(item.code, item.reason) for item in result.rejected] == [
        ("600001", reason)
    ]


def test_strict_breakout_rejects_missing_relative_strength(monkeypatch) -> None:
    result = _strict_result(monkeypatch, relative_strength=None)

    assert [(item.code, item.reason) for item in result.rejected] == [
        ("600001", "RELATIVE_STRENGTH_MISSING")
    ]


def test_real_breakout_bars_reject_an_overheated_rsi() -> None:
    selection = importlib.import_module("stock_ai.short_term_selection")

    result = selection.select_short_term_candidates(
        analysis_date=ANALYSIS_DATE,
        rows=[
            {
                "代码": "600001",
                "名称": "测试股票",
                "所属行业": "测试",
                "策略来源": "综合+底部突破",
            }
        ],
        bars_by_code={"600001": _breakout_bars()},
        relative_strength_by_code={"600001": 0.90},
        policy=selection.STRICT_A,
        holding_codes=set(),
        st_codes=set(),
    )

    assert [(item.code, item.reason) for item in result.rejected] == [
        ("600001", "RSI_OVERHEATED")
    ]


def test_strict_profile_thresholds_are_frozen_as_designed() -> None:
    selection = importlib.import_module("stock_ai.short_term_selection")

    assert (
        selection.STRICT_B.breakout_adx_min,
        selection.STRICT_B.breakout_trend_r2_min,
        selection.STRICT_B.breakout_relative_strength_min,
        selection.STRICT_B.pullback_adx_min,
        selection.STRICT_B.pullback_trend_r2_min,
        selection.STRICT_B.pullback_relative_strength_min,
    ) == (24.0, 0.60, 0.80, 22.0, 0.55, 0.75)
    assert (
        selection.STRICT_C.breakout_rsi_min,
        selection.STRICT_C.breakout_rsi_max,
        selection.STRICT_C.breakout_atr_pct_max,
        selection.STRICT_C.pullback_rsi_min,
        selection.STRICT_C.pullback_rsi_max,
        selection.STRICT_C.pullback_atr_pct_max,
    ) == (57.0, 67.0, 0.04, 50.0, 62.0, 0.035)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("adx14", 20.0),
        ("rsi14", 48.0),
        ("rsi14", 65.0),
        ("atr_pct", 0.012),
        ("atr_pct", 0.045),
        ("trend_r2_20", 0.50),
        ("pullback_amount_ratio", 0.80),
    ),
)
def test_strict_pullback_accepts_exact_gate_boundaries(
    monkeypatch, field: str, value: float
) -> None:
    result = _strict_result(
        monkeypatch,
        candidate_type="PULLBACK",
        snapshot=_strict_snapshot(**{field: value}),
    )

    assert [(item.code, item.candidate_type) for item in result.candidates] == [
        ("000001", "PULLBACK")
    ]


@pytest.mark.parametrize(
    ("changes", "relative_strength", "reason"),
    (
        ({"adx14": 19.99}, 0.90, "ADX_WEAK"),
        ({"rsi14": 47.99}, 0.90, "RSI_WEAK"),
        ({"rsi14": 65.01}, 0.90, "RSI_OVERHEATED"),
        ({"atr_pct": 0.0119}, 0.90, "VOLATILITY_OUT_OF_RANGE"),
        ({"atr_pct": 0.0451}, 0.90, "VOLATILITY_OUT_OF_RANGE"),
        ({"trend_r2_20": 0.499}, 0.90, "TREND_UNSTABLE"),
        ({}, 0.699, "RELATIVE_STRENGTH_LOW"),
        ({"pullback_amount_ratio": 0.801}, 0.90, "PULLBACK_VOLUME_NOT_CONTRACTING"),
    ),
)
def test_strict_pullback_rejects_each_failed_gate(
    monkeypatch,
    changes: dict[str, float],
    relative_strength: float,
    reason: str,
) -> None:
    result = _strict_result(
        monkeypatch,
        candidate_type="PULLBACK",
        snapshot=_strict_snapshot(**changes),
        relative_strength=relative_strength,
    )

    assert [(item.code, item.reason) for item in result.rejected] == [
        ("000001", reason)
    ]


def test_strict_pullback_requires_a_stop_confirmation(monkeypatch) -> None:
    bars = _pullback_bars()
    bars[-1] = {**bars[-1], "open": 11.70, "high": 11.75, "low": 11.55}

    result = _strict_result(monkeypatch, candidate_type="PULLBACK", bars=bars)

    assert [(item.code, item.reason) for item in result.rejected] == [
        ("000001", "STOP_CONFIRMATION_MISSING")
    ]


def test_strict_signal_exposes_all_indicator_metrics(monkeypatch) -> None:
    result = _strict_result(monkeypatch)

    metrics = result.candidates[0].metrics
    assert {
        "adx14",
        "rsi14",
        "atr14",
        "atr_pct",
        "trend_r2_20",
        "trend_slope_20",
        "return20",
        "breakout_pct",
        "average_amount5",
        "amount_ratio",
        "advance_amount5",
        "pullback_amount5",
        "pullback_amount_ratio",
        "relative_strength_percentile",
    } <= metrics.keys()


def test_future_bars_do_not_change_a_historical_strict_signal(monkeypatch) -> None:
    baseline = _strict_result(monkeypatch)
    future = _breakout_bars() + [
        {
            **_breakout_bars()[-1],
            "trade_date": (ANALYSIS_DATE + timedelta(days=offset)).isoformat(),
            "close": 1.0,
            "high": 1.0,
            "low": 1.0,
        }
        for offset in (1, 2)
    ]

    with_future = _strict_result(monkeypatch, bars=future)

    assert with_future == baseline


def test_omitted_policy_retains_the_2_0_result() -> None:
    selection = importlib.import_module("stock_ai.short_term_selection")
    arguments = {
        "analysis_date": ANALYSIS_DATE,
        "rows": [
            {
                "代码": "600001",
                "名称": "测试股票",
                "所属行业": "测试",
                "策略来源": "综合+底部突破",
            }
        ],
        "bars_by_code": {"600001": _breakout_bars()},
        "holding_codes": set(),
        "st_codes": set(),
    }

    omitted = selection.select_short_term_candidates(**arguments)
    explicit = selection.select_short_term_candidates(
        **arguments, policy=selection.BASELINE_POLICY
    )

    assert omitted == explicit


def test_backtest_entry_uses_only_the_next_session_after_signal() -> None:
    script = ROOT / "scripts" / "analysis" / "backtest_short_term_trade.py"
    spec = importlib.util.spec_from_file_location("backtest_short_term_trade", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    bars = [
        {
            **bar,
            "trade_date": (
                date(2026, 8, 7) - timedelta(days=len(_breakout_bars()) - 1 - index)
            ).isoformat(),
        }
        for index, bar in enumerate(_breakout_bars())
    ]
    frame = module.pd.DataFrame(
        [
            {
                **bar,
                "code": "600001",
                "name": "测试银行",
                "sector": "银行",
            }
            for bar in bars
        ]
        + [
            {
                "trade_date": "2026-08-10",
                "open": 12.40,
                "high": 12.60,
                "low": 12.20,
                "close": 12.50,
                "pct_chg": 2.0,
                "amount": 180_000.0,
                "code": "600001",
                "name": "测试银行",
                "sector": "银行",
            }
        ]
    )

    trades = module.run_backtest(
        frame,
        candidate_type="BREAKOUT",
        hold_days=1,
        commission_rate=0,
        slippage_rate=0,
    )

    assert trades[0].signal_date == date(2026, 8, 7)
    assert trades[0].entry_date == date(2026, 8, 10)
    assert trades[0].entry_price == 12.40
