from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.models import BuyPointBar, SelectionPolicy, SetupType
from stock_ai.buy_point_selection.patterns import detect_setups


POLICY = SelectionPolicy()
START = date(2026, 4, 1)


def _bar(
    index: int,
    close: str | Decimal,
    *,
    previous: str | Decimal | None = None,
    open_: str | Decimal | None = None,
    high: str | Decimal | None = None,
    low: str | Decimal | None = None,
    amount: str | Decimal = "120000",
) -> BuyPointBar:
    close_value = Decimal(str(close))
    previous_value = Decimal(str(previous)) if previous is not None else close_value
    pct_chg = (
        (close_value / previous_value - Decimal("1")) * Decimal("100")
        if previous_value
        else Decimal("0")
    )
    return BuyPointBar(
        trade_date=START + timedelta(days=index),
        open=Decimal(str(open_)) if open_ is not None else close_value,
        high=Decimal(str(high)) if high is not None else close_value + Decimal("0.08"),
        low=Decimal(str(low)) if low is not None else close_value - Decimal("0.08"),
        close=close_value,
        pct_chg=pct_chg,
        amount_qian=Decimal(str(amount)),
    )


def _bars_from_closes(
    closes: list[str | Decimal],
    *,
    amounts: list[str | Decimal] | None = None,
) -> tuple[BuyPointBar, ...]:
    result = []
    for index, close in enumerate(closes):
        previous = closes[index - 1] if index else close
        result.append(
            _bar(
                index,
                close,
                previous=previous,
                amount=amounts[index] if amounts is not None else "120000",
            )
        )
    return tuple(result)


def platform_fixture() -> tuple[BuyPointBar, ...]:
    closes: list[str | Decimal] = [Decimal("9.60") + Decimal(index) * Decimal("0.01") for index in range(30)]
    closes.extend(
        [
            "9.85", "10.05", "9.90", "10.20", "9.95",
            "10.25", "10.00", "10.30", "10.05", "10.20",
            "9.95", "10.15", "10.00", "10.25", "10.10",
            "10.28", "10.12", "10.30", "10.18", "10.26",
            "10.18", "10.21", "10.20", "10.24", "10.23",
            "10.27", "10.25", "10.29", "10.28", "10.31",
        ]
    )
    amounts: list[str | Decimal] = ["120000"] * 50 + ["120000"] * 5 + ["90000"] * 5
    bars = list(_bars_from_closes(closes, amounts=amounts))
    for index in range(30, 40):
        bars[index] = replace(bars[index], high=Decimal("10.42"), low=Decimal("9.75"))
    for index in range(40, 50):
        bars[index] = replace(bars[index], high=bars[index].close + Decimal("0.12"), low=bars[index].close - Decimal("0.12"))
    for index in range(50, 60):
        bars[index] = replace(bars[index], high=bars[index].close + Decimal("0.06"), low=bars[index].close - Decimal("0.06"))
    return tuple(bars)


def trend_pullback_fixture() -> tuple[BuyPointBar, ...]:
    closes: list[str | Decimal] = ["10.00"] * 47
    closes.extend(["10.10", "10.20", "10.30", "10.40", "10.50", "10.60", "10.70", "10.80", "10.90"])
    closes.extend(["10.82", "10.74", "10.70", "10.69"])
    amounts: list[str | Decimal] = ["110000"] * 47 + ["140000"] * 9 + ["85000"] * 4
    return _bars_from_closes(closes, amounts=amounts)


def first_launch_fixture() -> tuple[BuyPointBar, ...]:
    closes: list[str | Decimal] = ["10.00"] * 57 + ["10.40", "10.35", "10.40"]
    amounts: list[str | Decimal] = ["100000"] * 57 + ["160000", "110000", "105000"]
    bars = list(_bars_from_closes(closes, amounts=amounts))
    bars[57] = replace(
        bars[57],
        open=Decimal("10.02"),
        high=Decimal("10.48"),
        low=Decimal("9.98"),
    )
    return tuple(bars)


def three_up_fixture() -> tuple[BuyPointBar, ...]:
    closes: list[str | Decimal] = ["10.00"] * 57 + ["10.30", "10.60", "10.90"]
    amounts: list[str | Decimal] = ["100000"] * 57 + ["150000", "170000", "190000"]
    return _bars_from_closes(closes, amounts=amounts)


def _only_setup(values):
    assert len(values) == 1
    return values[0]


def test_pre_breakout_is_near_contracting_platform_top() -> None:
    """Catches a broad or already-extended range being called a pending breakout."""
    setup = _only_setup(detect_setups("600001", platform_fixture(), POLICY))
    assert setup.setup_type is SetupType.PRE_BREAKOUT
    assert setup.metrics["distance_to_platform_top"] <= Decimal("0.03")
    assert setup.metrics["range_contraction_ratio"] <= Decimal("0.80")


def test_trend_pullback_requires_two_to_four_contracting_sessions() -> None:
    """Catches an ordinary down day being mislabeled as a completed pullback."""
    setup = _only_setup(detect_setups("600002", trend_pullback_fixture(), POLICY))
    assert setup.setup_type is SetupType.TREND_PULLBACK
    assert Decimal("2") <= setup.metrics["pullback_sessions"] <= Decimal("4")
    assert setup.metrics["pullback_amount_ratio"] <= Decimal("0.80")


def test_first_launch_requires_launch_then_one_or_two_quiet_bars() -> None:
    """Catches a standalone high-volume candle with no quiet entry structure."""
    setup = _only_setup(detect_setups("600003", first_launch_fixture(), POLICY))
    assert setup.setup_type is SetupType.FIRST_LAUNCH_PULLBACK
    assert setup.metrics["launch_gain_pct"] == Decimal("0.04")
    assert setup.metrics["quiet_sessions"] == Decimal("2")


def test_plain_three_up_has_no_setup() -> None:
    """Catches the deprecated three-up condition regaining executable status."""
    assert detect_setups("600004", three_up_fixture(), POLICY) == ()


def test_platform_rejects_non_contracting_turnover() -> None:
    """Catches a platform with rising participation being treated as a quiet pre-entry."""
    bars = list(platform_fixture())
    for index in range(55, 60):
        bars[index] = replace(bars[index], amount_qian=Decimal("130000"))
    assert detect_setups("600005", tuple(bars), POLICY) == ()


@pytest.mark.parametrize(("launch_gain", "quiet_amount"), [("0.06", "110000"), ("0.04", "140000")])
def test_first_launch_rejects_overextended_launch_or_loud_follow_through(
    launch_gain: str, quiet_amount: str
) -> None:
    """Catches chasing an overextended launch or a non-contracting continuation."""
    bars = list(first_launch_fixture())
    launch_close = Decimal("10") * (Decimal("1") + Decimal(launch_gain))
    bars[57] = replace(
        bars[57],
        close=launch_close,
        high=launch_close + Decimal("0.08"),
        pct_chg=Decimal(launch_gain) * Decimal("100"),
    )
    bars[58] = replace(bars[58], amount_qian=Decimal(quiet_amount))
    bars[59] = replace(bars[59], amount_qian=Decimal(quiet_amount))
    assert not any(
        setup.setup_type is SetupType.FIRST_LAUNCH_PULLBACK
        for setup in detect_setups("600006", tuple(bars), POLICY)
    )
