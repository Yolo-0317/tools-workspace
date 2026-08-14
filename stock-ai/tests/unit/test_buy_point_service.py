from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from stock_ai.buy_point_selection.formatting import render_buy_point_report
from stock_ai.buy_point_selection.models import BuyPointBar, DetectedSetup, SelectionPolicy, SetupType
from stock_ai.buy_point_selection.planning import RiskBudget, structure_id
from stock_ai.buy_point_selection.service import (
    CandidateEvidence,
    LegacyShadow,
    SelectionInput,
    select_buy_points,
)
from stock_ai.buy_point_selection.validation import OutcomeCalibration, calibration_key


POLICY = SelectionPolicy()
BUDGET = RiskBudget(Decimal("500"), Decimal("4000"), Decimal("40000"))


def _bars() -> tuple[BuyPointBar, ...]:
    start = date(2026, 6, 12)
    return tuple(
        BuyPointBar(
            trade_date=start + timedelta(days=index),
            open=Decimal("9.85"),
            high=Decimal("10.00"),
            low=Decimal("9.70"),
            close=Decimal("9.85"),
            pct_chg=Decimal("0"),
            amount_qian=Decimal("150000"),
        )
        for index in range(60)
    )


def _setup(
    code: str,
    quality: str = "0.80",
    start_offset: int = 0,
    setup_type: SetupType = SetupType.PRE_BREAKOUT,
) -> DetectedSetup:
    return DetectedSetup(
        code=code,
        setup_type=setup_type,
        analysis_date=date(2026, 8, 10),
        structure_start=date(2026, 7, 10) + timedelta(days=start_offset),
        structure_high=Decimal("10.00"),
        structure_low=Decimal("9.77"),
        quality=Decimal(quality),
        reasons=("CONTRACTING_PLATFORM_NEAR_TOP",),
        metrics={},
    )


def _candidate(
    code: str,
    *,
    sector: str | None,
    quality: str,
    percentile: str = "0.80",
    missing: tuple[str, ...] = (),
    setup_type: SetupType = SetupType.PRE_BREAKOUT,
) -> CandidateEvidence:
    return CandidateEvidence(
        code=code,
        name=f"虚构{code[-2:]}",
        setup=_setup(code, quality, setup_type=setup_type),
        bars=_bars(),
        sector_code=sector,
        sector_percentile=Decimal(percentile) if sector is not None else None,
        average_amount5_qian=Decimal("150000"),
        gate_reasons=(),
        missing_fields=missing,
    )


def _calibration(
    setup_type: SetupType = SetupType.PRE_BREAKOUT,
    *,
    net_expectancy: str = "0.01",
    target_rate: str = "0.50",
    stop_rate: str = "0.25",
    rolling_ratio: str = "0.80",
    promoted: bool = True,
) -> OutcomeCalibration:
    key = calibration_key(setup_type, None, None)
    return OutcomeCalibration(
        key=key,
        setup_type=setup_type,
        market_status=None,
        sector_resonating=None,
        data_end=date(2026, 8, 9),
        total_plans=45,
        triggered_trades=40,
        untriggered_plans=5,
        target_2r_rate=Decimal(target_rate),
        target_2r_interval=(Decimal("0.35"), Decimal("0.65")),
        stop_first_rate=Decimal(stop_rate),
        stop_first_interval=(Decimal("0.14"), Decimal("0.40")),
        net_expectancy=Decimal(net_expectancy),
        positive_rolling_window_ratio=Decimal(rolling_ratio),
        frozen_test_expectancy=Decimal("0.005"),
        average_profit_loss_ratio=Decimal("1.8"),
        profit_factor=Decimal("1.5"),
        mfe_median=Decimal("0.06"),
        mfe_p25=Decimal("0.03"),
        mae_median=Decimal("0.02"),
        mae_p75=Decimal("0.035"),
        promoted=promoted,
        reasons=() if promoted else ("NEGATIVE_EXPECTANCY",),
    )


def _request(
    *,
    market_status: str = "ALLOW",
    candidates: tuple[CandidateEvidence, ...] | None = None,
    legacy_shadow: tuple[LegacyShadow, ...] = (),
    existing: frozenset[str] = frozenset(),
    risk_coverage_complete: bool = True,
    account_fresh: bool = True,
    budget: RiskBudget = BUDGET,
    calibrations: dict[str, OutcomeCalibration] | None = None,
) -> SelectionInput:
    resolved_calibrations = (
        {value.key: value for value in (_calibration(),)}
        if calibrations is None
        else calibrations
    )
    return SelectionInput(
        market_status=market_status,
        candidates=candidates
        or (_candidate("600001", sector="S1", quality="0.90"),),
        legacy_shadow=legacy_shadow,
        risk_budget=budget,
        existing_structure_ids=existing,
        risk_coverage_complete=risk_coverage_complete,
        account_fresh=account_fresh,
        policy=POLICY,
        calibrations=resolved_calibrations,
    )


def test_freeze_returns_no_qualified_candidates_and_preserves_shadow_only() -> None:
    """Catches legacy research being promoted as a fallback during a market freeze."""
    shadow = LegacyShadow("600099", "虚构影子", "legacy-three-up", ("RESEARCH_ONLY",))
    result = select_buy_points(_request(market_status="FREEZE", legacy_shadow=(shadow,)))
    assert result.qualified == ()
    assert len(result.shadow) == 1
    assert result.shadow[0].source == "legacy-three-up"


def test_ranking_limits_three_and_keeps_one_candidate_per_sector() -> None:
    """Catches score order or sector concentration bypassing deterministic allocation."""
    candidates = (
        _candidate("600001", sector="S1", quality="0.90"),
        _candidate("600002", sector="S1", quality="0.85"),
        _candidate("600003", sector="S2", quality="0.80"),
        _candidate("600004", sector="S3", quality="0.70"),
        _candidate("600005", sector="S4", quality="0.60"),
    )
    result = select_buy_points(_request(candidates=candidates))
    assert [item.code for item in result.qualified] == ["600001", "600003", "600004"]
    assert result.rejection_counts["SECTOR_CONCENTRATION"] == 1
    assert result.rejection_counts["DAILY_CANDIDATE_LIMIT"] == 1


def test_limited_market_keeps_only_one_half_sized_candidate() -> None:
    """Catches LIMITED producing multiple plans or full-sized exposure."""
    candidates = (
        _candidate("600001", sector="S1", quality="0.90"),
        _candidate("600003", sector="S2", quality="0.80"),
    )
    result = select_buy_points(_request(market_status="LIMITED", candidates=candidates))
    assert len(result.qualified) == 1
    assert result.qualified[0].plan.maximum_shares == 100


def test_allocation_never_exceeds_remaining_portfolio_exposure() -> None:
    """Catches each candidate independently spending the same remaining account capacity."""
    candidates = (
        _candidate("600001", sector="S1", quality="0.90"),
        _candidate("600003", sector="S2", quality="0.80"),
    )
    budget = RiskBudget(Decimal("500"), Decimal("4000"), Decimal("3500"))
    result = select_buy_points(_request(candidates=candidates, budget=budget))
    nominal_exposure = sum(
        item.plan.trigger_price * item.plan.maximum_shares
        for item in result.qualified
        if item.plan is not None
    )
    assert nominal_exposure <= budget.remaining_exposure
    assert result.rejection_counts["PORTFOLIO_EXPOSURE_EXHAUSTED"] == 1


def test_missing_sector_risk_or_account_data_downgrades_to_observe() -> None:
    """Catches incomplete point-in-time or account inputs generating executable output."""
    candidate = _candidate("600001", sector=None, quality="0.90", missing=("SECTOR",))
    result = select_buy_points(
        _request(
            candidates=(candidate,),
            risk_coverage_complete=False,
            account_fresh=False,
        )
    )
    assert result.qualified == ()
    assert result.observe[0].missing_fields == ("SECTOR", "RISK_COVERAGE", "ACCOUNT_FRESHNESS")
    assert result.observe[0].plan is None


def test_existing_structure_is_not_emitted_again() -> None:
    """Catches a PREPARED or resolved structure being reissued on every scan."""
    candidate = _candidate("600001", sector="S1", quality="0.90")
    existing = structure_id(candidate.code, candidate.setup, POLICY.rule_version)
    result = select_buy_points(_request(candidates=(candidate,), existing=frozenset({existing})))
    assert result.qualified == ()
    assert result.rejection_counts == {"EXISTING_STRUCTURE": 1}


def test_report_prints_share_count_only_for_qualified_rows() -> None:
    """Catches observe or shadow rows leaking an actionable share recommendation."""
    qualified = _candidate("600001", sector="S1", quality="0.90")
    observe = _candidate("600002", sector=None, quality="0.80", missing=("SECTOR",))
    shadow = LegacyShadow("600099", "虚构影子", "legacy-three-up", ("RESEARCH_ONLY",))
    result = select_buy_points(
        _request(candidates=(qualified, observe), legacy_shadow=(shadow,))
    )
    report = render_buy_point_report(result)
    formal_text, remainder = report.split("准备中观察", 1)
    observe_text, shadow_text = remainder.split("影子研究", 1)
    assert "最大股数" in formal_text
    assert "2R概率 35%-65%" in formal_text
    assert "止损概率 14%-40%" in formal_text
    assert "样本 40" in formal_text
    assert "净期望 1.00%" in formal_text
    assert "最大股数" not in observe_text
    assert "最大股数" not in shadow_text
    assert "无交易资格" in observe_text
    assert "无交易资格" in shadow_text
    assert "拒绝统计" in shadow_text


def test_missing_or_insufficient_calibration_downgrades_to_observe() -> None:
    """Catches an uncalibrated setup receiving a formal price plan and shares."""
    result = select_buy_points(_request(calibrations={}))
    assert result.qualified == ()
    assert result.observe[0].reasons == ("CALIBRATION_MISSING",)
    assert result.observe[0].plan is None


def test_negative_calibration_cannot_gain_trade_qualification() -> None:
    """Catches current technical quality overriding a failed historical cohort."""
    calibration = _calibration(promoted=False, net_expectancy="-0.002")
    result = select_buy_points(_request(calibrations={calibration.key: calibration}))
    assert result.qualified == ()
    assert result.observe[0].reasons == ("CALIBRATION_NOT_PROMOTED",)
    assert result.observe[0].calibration is calibration


def test_ranking_prefers_expectancy_then_target_rate_then_lower_stop_rate() -> None:
    """Catches pattern quality replacing the frozen outcome evidence order."""
    candidates = (
        _candidate(
            "600001",
            sector="S1",
            quality="0.99",
            setup_type=SetupType.PRE_BREAKOUT,
        ),
        _candidate(
            "600002",
            sector="S2",
            quality="0.90",
            setup_type=SetupType.TREND_PULLBACK,
        ),
        _candidate(
            "600003",
            sector="S3",
            quality="0.80",
            setup_type=SetupType.FIRST_LAUNCH_PULLBACK,
        ),
    )
    calibrations = (
        _calibration(
            SetupType.PRE_BREAKOUT,
            net_expectancy="0.01",
            target_rate="0.60",
            stop_rate="0.20",
        ),
        _calibration(
            SetupType.TREND_PULLBACK,
            net_expectancy="0.01",
            target_rate="0.60",
            stop_rate="0.30",
        ),
        _calibration(
            SetupType.FIRST_LAUNCH_PULLBACK,
            net_expectancy="0.02",
            target_rate="0.45",
            stop_rate="0.35",
        ),
    )
    result = select_buy_points(
        _request(
            candidates=candidates,
            calibrations={value.key: value for value in calibrations},
        )
    )
    assert [item.code for item in result.qualified] == [
        "600003",
        "600001",
        "600002",
    ]
