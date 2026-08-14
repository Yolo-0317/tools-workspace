from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from stock_ai.buy_point_selection.execution import (
    ExecutionCosts,
    PortfolioCase,
    simulate_plan,
    simulate_portfolio,
)
from stock_ai.buy_point_selection import models as buy_point_models
from stock_ai.buy_point_selection.models import BuyPointBar, SetupType
from stock_ai.buy_point_selection.planning import PricePlan


COSTS = ExecutionCosts()
ZERO_COSTS = ExecutionCosts(
    commission_rate=Decimal("0"),
    minimum_commission=Decimal("0"),
    slippage_rate=Decimal("0"),
    sell_tax_rate=Decimal("0"),
)


def _plan(*, code: str = "600001", quantity: int = 300) -> PricePlan:
    return PricePlan(
        structure_id=f"structure-{code}",
        code=code,
        setup_type=SetupType.PRE_BREAKOUT,
        signal_date=date(2026, 8, 10),
        signal_close=Decimal("10.00"),
        trigger_price=Decimal("10.10"),
        invalidation_price=Decimal("9.80"),
        target_2r=Decimal("10.70"),
        risk_distance=Decimal("0.30"),
        risk_reward_ratio=Decimal("2"),
        maximum_shares=quantity,
        valid_through_trade_date=date(2026, 8, 12),
    )


def _bar(
    day: int,
    *,
    open_: str,
    high: str,
    low: str,
    close: str,
    pct_chg: str = "0",
) -> BuyPointBar:
    return BuyPointBar(
        trade_date=date(2026, 8, day),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        pct_chg=Decimal(pct_chg),
        amount_qian=Decimal("200000"),
    )


def _flat_exit_after_entry() -> tuple[BuyPointBar, ...]:
    return (
        _bar(11, open_="10.10", high="10.20", low="9.95", close="10.10"),
        _bar(12, open_="10.10", high="10.30", low="9.95", close="10.15"),
        _bar(13, open_="10.15", high="10.30", low="10.00", close="10.20"),
        _bar(14, open_="10.20", high="10.30", low="10.00", close="10.20"),
        _bar(17, open_="10.20", high="10.30", low="10.00", close="10.20"),
    )


def _time_exit_with_close(close: str) -> tuple[BuyPointBar, ...]:
    return (
        _bar(11, open_="10.10", high="10.20", low="9.95", close="10.10"),
        _bar(12, open_="10.10", high="10.30", low="9.95", close="10.15"),
        _bar(13, open_="10.15", high="10.30", low="10.00", close="10.20"),
        _bar(14, open_="10.20", high="10.30", low="10.00", close="10.20"),
        _bar(17, open_="10.20", high="10.30", low="10.00", close=close),
    )


def test_untriggered_first_day_can_trigger_on_second_day() -> None:
    """Catches first-day non-entry incorrectly expiring a two-session plan."""
    bars = (
        _bar(11, open_="10.00", high="10.05", low="9.95", close="10.02"),
        _bar(12, open_="10.02", high="10.20", low="9.95", close="10.12"),
        _bar(13, open_="10.10", high="10.30", low="10.00", close="10.15"),
        _bar(14, open_="10.15", high="10.30", low="10.00", close="10.15"),
        _bar(17, open_="10.15", high="10.30", low="10.00", close="10.15"),
        _bar(18, open_="10.15", high="10.30", low="10.00", close="10.15"),
    )
    trade = simulate_plan(_plan(), bars, COSTS, sector_code="S1")
    assert trade.entry_date == date(2026, 8, 12)
    assert trade.entry_price == Decimal("10.11010")


def test_gap_above_three_percent_cancels() -> None:
    """Catches an overextended opening auction being chased."""
    bars = (_bar(11, open_="10.31", high="10.40", low="10.20", close="10.30"),)
    assert simulate_plan(_plan(), bars, COSTS, sector_code="S1").status == "GAP_CANCELLED"


def test_trigger_above_five_percent_and_locked_limit_up_cancel() -> None:
    """Catches a price-cap chase or an unfillable one-price board being simulated as filled."""
    chased = replace(_plan(), trigger_price=Decimal("10.51"))
    chase_bar = (_bar(11, open_="10.00", high="10.60", low="9.95", close="10.55"),)
    locked_bar = (_bar(11, open_="11.00", high="11.00", low="11.00", close="11.00", pct_chg="10"),)
    assert simulate_plan(chased, chase_bar, COSTS, sector_code="S1").status == "CHASE_CANCELLED"
    assert simulate_plan(_plan(), locked_bar, COSTS, sector_code="S1").status == "LOCKED_LIMIT_UP"


def test_same_bar_stop_and_target_assumes_stop_first() -> None:
    """Catches unknown intraday ordering being resolved optimistically."""
    bars = (_bar(11, open_="10.10", high="10.80", low="9.70", close="10.40"),)
    trade = simulate_plan(_plan(), bars, COSTS, sector_code="S1")
    assert trade.exit_reason == "STOP"
    assert trade.exit_legs[0].quantity == 300
    assert trade.outcome is buy_point_models.OutcomeLabel.STOP_FIRST
    assert trade.intraday_order_ambiguous


def test_two_r_sells_half_and_moves_remainder_to_entry() -> None:
    """Catches a 2R event failing to reduce risk on the remaining position."""
    bars = (
        _bar(11, open_="10.10", high="10.20", low="9.95", close="10.10"),
        _bar(12, open_="10.20", high="10.80", low="10.00", close="10.70"),
        _bar(13, open_="10.60", high="10.65", low="10.05", close="10.20"),
    )
    trade = simulate_plan(_plan(quantity=400), bars, COSTS, sector_code="S1")
    assert trade.exit_legs[0].quantity == 200
    assert trade.exit_legs[0].reason == "TARGET_2R"
    assert trade.exit_legs[1].quantity == 200
    assert trade.exit_legs[1].reason == "BREAKEVEN_STOP"


def test_target_before_stop_records_two_r_path_and_excursions() -> None:
    """Catches a successful 2R path being reduced to only its final net return."""
    bars = (
        _bar(11, open_="10.10", high="10.20", low="9.95", close="10.10"),
        _bar(12, open_="10.20", high="10.80", low="10.00", close="10.70"),
        _bar(13, open_="10.60", high="10.65", low="10.05", close="10.20"),
    )
    trade = simulate_plan(_plan(quantity=400), bars, COSTS, sector_code="S1")
    assert trade.outcome is buy_point_models.OutcomeLabel.TARGET_2R_FIRST
    assert trade.mfe == Decimal("10.80") / Decimal("10.11010") - Decimal("1")
    assert trade.mae == Decimal("1") - Decimal("9.95") / Decimal("10.11010")
    assert not trade.intraday_order_ambiguous


def test_one_lot_exits_fully_at_two_r_and_charges_all_costs() -> None:
    """Catches impossible half-lot exits or understated A-share round-trip costs."""
    bars = (
        _bar(11, open_="10.10", high="10.20", low="9.95", close="10.10"),
        _bar(12, open_="10.20", high="10.80", low="10.00", close="10.70"),
    )
    trade = simulate_plan(_plan(quantity=100), bars, COSTS, sector_code="S1")
    assert trade.exit_legs[0].quantity == 100
    assert trade.exit_legs[0].reason == "TARGET_2R"
    assert trade.exit_legs[0].price == Decimal("10.68930")
    assert trade.net_pnl == Decimal("46.85107000")


def test_untriggered_plan_expires_and_open_trade_exits_on_session_five() -> None:
    """Catches phantom fills or positions silently escaping the five-session horizon."""
    expired_bars = (
        _bar(11, open_="10.00", high="10.05", low="9.95", close="10.00"),
        _bar(12, open_="10.00", high="10.05", low="9.95", close="10.00"),
    )
    expired = simulate_plan(_plan(), expired_bars, COSTS, sector_code="S1")
    timed = simulate_plan(_plan(), _flat_exit_after_entry(), COSTS, sector_code="S1")
    assert expired.status == "EXPIRED"
    assert expired.outcome is buy_point_models.OutcomeLabel.NOT_TRIGGERED
    assert expired.mfe is None
    assert expired.mae is None
    assert timed.exit_legs[-1].exit_date == date(2026, 8, 17)
    assert timed.exit_legs[-1].reason == "TIME_EXIT"


def test_untriggered_plan_with_incomplete_trigger_window_remains_pending() -> None:
    """Catches a one-session partial future path being mislabeled as a resolved miss."""
    bars = (
        _bar(11, open_="10.00", high="10.05", low="9.95", close="10.00"),
    )

    trade = simulate_plan(_plan(), bars, COSTS, sector_code="S1")

    assert trade.status == "PENDING"
    assert trade.outcome is buy_point_models.OutcomeLabel.PENDING


def test_five_session_time_exit_classifies_gain_loss_and_flat() -> None:
    """Catches time exits being treated as one undifferentiated non-2R outcome."""
    gain = simulate_plan(
        _plan(), _time_exit_with_close("10.20"), ZERO_COSTS, sector_code="S1"
    )
    loss = simulate_plan(
        _plan(), _time_exit_with_close("10.00"), ZERO_COSTS, sector_code="S1"
    )
    flat = simulate_plan(
        _plan(), _time_exit_with_close("10.10"), ZERO_COSTS, sector_code="S1"
    )
    assert gain.outcome is buy_point_models.OutcomeLabel.EXPIRY_GAIN
    assert loss.outcome is buy_point_models.OutcomeLabel.EXPIRY_LOSS
    assert flat.outcome is buy_point_models.OutcomeLabel.EXPIRY_FLAT


def test_portfolio_enforces_sector_position_count_and_exposure() -> None:
    """Catches individually valid plans violating portfolio-level limits."""
    duplicate_sector = simulate_portfolio(
        (
            PortfolioCase(_plan(code="600001"), "S1", _flat_exit_after_entry()),
            PortfolioCase(_plan(code="600002"), "S1", _flat_exit_after_entry()),
        ),
        COSTS,
    )
    assert duplicate_sector[1].status == "SECTOR_POSITION_LIMIT"

    four_positions = simulate_portfolio(
        tuple(
            PortfolioCase(_plan(code=f"60000{index}"), f"S{index}", _flat_exit_after_entry())
            for index in range(1, 5)
        ),
        COSTS,
    )
    assert four_positions[3].status == "POSITION_COUNT_LIMIT"

    exposure = simulate_portfolio(
        (
            PortfolioCase(_plan(code="600011", quantity=2000), "S1", _flat_exit_after_entry()),
            PortfolioCase(_plan(code="600012", quantity=2000), "S2", _flat_exit_after_entry()),
        ),
        COSTS,
    )
    assert exposure[1].status == "EXPOSURE_LIMIT"
