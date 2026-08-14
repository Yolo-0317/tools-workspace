from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from stock_ai.buy_point_selection.models import BuyPointBar, DetectedSetup, SelectionPolicy, SetupType
from stock_ai.buy_point_selection.planning import RiskBudget, build_price_plan, structure_id


POLICY = SelectionPolicy()


def _bars(*, resistance: Decimal | None = None) -> tuple[BuyPointBar, ...]:
    values = []
    start = date(2026, 6, 12)
    for index in range(60):
        values.append(
            BuyPointBar(
                trade_date=start + timedelta(days=index),
                open=Decimal("9.85"),
                high=Decimal("10.00"),
                low=Decimal("9.70"),
                close=Decimal("9.85"),
                pct_chg=Decimal("0"),
                amount_qian=Decimal("150000"),
            )
        )
    if resistance is not None:
        values[20] = replace(values[20], high=resistance)
    return tuple(values)


def _setup(**changes) -> DetectedSetup:
    base = DetectedSetup(
        code="600001",
        setup_type=SetupType.PRE_BREAKOUT,
        analysis_date=date(2026, 8, 10),
        structure_start=date(2026, 7, 10),
        structure_high=Decimal("10.00"),
        structure_low=Decimal("9.77"),
        quality=Decimal("0.85"),
        reasons=("CONTRACTING_PLATFORM_NEAR_TOP",),
        metrics={},
    )
    return replace(base, **changes)


def test_plan_uses_tick_atr_buffer_two_r_and_risk_sizing() -> None:
    """Catches optimistic stop rounding or position sizing beyond either risk cap."""
    decision = build_price_plan(
        _setup(),
        _bars(),
        RiskBudget(Decimal("500"), Decimal("4000"), Decimal("40000")),
        "ALLOW",
        POLICY,
    )
    assert decision.reasons == ()
    assert decision.plan is not None
    assert decision.plan.trigger_price == Decimal("10.01")
    assert decision.plan.invalidation_price == Decimal("9.71")
    assert decision.plan.target_2r == Decimal("10.61")
    assert decision.plan.risk_distance == Decimal("0.30")
    assert decision.plan.maximum_shares == 300
    assert decision.plan.valid_through_trade_date == date(2026, 8, 12)


def test_limited_market_halves_ticket_and_loss_budget() -> None:
    """Catches LIMITED silently retaining ALLOW-sized exposure."""
    decision = build_price_plan(
        _setup(),
        _bars(),
        RiskBudget(Decimal("500"), Decimal("4000"), Decimal("40000")),
        "LIMITED",
        POLICY,
    )
    assert decision.plan is not None
    assert decision.plan.maximum_shares == 100


def test_plan_rejects_too_tight_risk_and_resistance_before_two_r() -> None:
    """Catches attractive-looking setups that cannot support a valid protective plan."""
    tight = build_price_plan(
        _setup(structure_low=Decimal("9.98")),
        _bars(),
        RiskBudget(Decimal("500"), Decimal("4000"), Decimal("40000")),
        "ALLOW",
        POLICY,
    )
    blocked = build_price_plan(
        _setup(),
        _bars(resistance=Decimal("10.40")),
        RiskBudget(Decimal("500"), Decimal("4000"), Decimal("40000")),
        "ALLOW",
        POLICY,
    )
    assert tight.reasons == ("RISK_DISTANCE_OUT_OF_RANGE",)
    assert blocked.reasons == ("INSUFFICIENT_TWO_R_SPACE",)


def test_freeze_and_sub_lot_budget_never_create_a_plan() -> None:
    """Catches a market freeze or unaffordable odd lot leaking into execution."""
    frozen = build_price_plan(
        _setup(),
        _bars(),
        RiskBudget(Decimal("500"), Decimal("4000"), Decimal("40000")),
        "FREEZE",
        POLICY,
    )
    tiny = build_price_plan(
        _setup(),
        _bars(),
        RiskBudget(Decimal("10"), Decimal("500"), Decimal("500")),
        "ALLOW",
        POLICY,
    )
    assert frozen.reasons == ("MARKET_FREEZE",)
    assert tiny.reasons == ("POSITION_BELOW_BOARD_LOT",)


def test_same_structure_has_same_id_on_next_analysis_day() -> None:
    """Catches daily reruns producing duplicate recommendations for one structure."""
    first = structure_id("600001", _setup(), POLICY.rule_version)
    second = structure_id(
        "600001",
        replace(_setup(), analysis_date=date(2026, 8, 11)),
        POLICY.rule_version,
    )
    assert first == second
    assert first != structure_id(
        "600001",
        replace(_setup(), structure_start=date(2026, 7, 11)),
        POLICY.rule_version,
    )
