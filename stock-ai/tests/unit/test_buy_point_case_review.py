from __future__ import annotations

from datetime import date
from decimal import Decimal

from stock_ai.buy_point_selection.case_review import GateTrace, classify_near_miss


SIGNAL = date(2026, 8, 3)


def test_exactly_one_allowed_soft_gate_enters_near_miss() -> None:
    """Catches an explainable sector near miss being discarded with hard failures."""
    trace = GateTrace(
        code="600001",
        signal_date=SIGNAL,
        failed_reasons=("SECTOR_BREADTH_WEAK",),
        passed_stages=("BASE", "SETUP", "ANTI_CHASE"),
        metrics={"boundary_deviation": Decimal("0.10")},
    )

    decision = classify_near_miss(
        trace,
        setup_quality=Decimal("0.8"),
        average_amount5_qian=Decimal("200000"),
    )

    assert decision.admitted
    assert decision.soft_reason == "SECTOR_BREADTH_WEAK"
    assert decision.ranking_key == (
        Decimal("0.10"),
        Decimal("-0.8"),
        Decimal("-200000"),
        "600001",
    )


def test_hard_or_two_soft_failures_never_enter_near_miss() -> None:
    """Catches the diagnostic lane accidentally weakening hard or multiple gates."""
    hard = GateTrace(
        code="600001",
        signal_date=SIGNAL,
        failed_reasons=("LIQUIDITY_TOO_LOW",),
        passed_stages=(),
        metrics={},
    )
    two_soft = GateTrace(
        code="600002",
        signal_date=SIGNAL,
        failed_reasons=(
            "SECTOR_BREADTH_WEAK",
            "INSUFFICIENT_TWO_R_SPACE",
        ),
        passed_stages=("BASE", "SETUP", "ANTI_CHASE"),
        metrics={},
    )

    assert not classify_near_miss(
        hard,
        setup_quality=Decimal("1"),
        average_amount5_qian=Decimal("200000"),
    ).admitted
    assert not classify_near_miss(
        two_soft,
        setup_quality=Decimal("1"),
        average_amount5_qian=Decimal("200000"),
    ).admitted
