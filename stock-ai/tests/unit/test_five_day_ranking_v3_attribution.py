from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3_attribution import (
    MIN_MARKET_MEDIAN_MEMBERS,
    MarketClosePanel,
    MarketCoverageIncomplete,
    attribute_interval,
    fifth_subsequent_train_date,
    matched_index_id,
    simple_return,
)

from five_day_ranking_v3_fixtures import weekday_dates


START = date(2026, 7, 1)
END = date(2026, 7, 8)


def _market_panel(
    *,
    stock_start: str = "10",
    stock_end: str = "11",
    index_start: str = "100",
    index_end: str = "102",
    median_start: str = "10",
    median_end: str = "10.50",
    market_members: int = MIN_MARKET_MEDIAN_MEMBERS,
) -> MarketClosePanel:
    stock_closes = {
        (
            f"600{member:03d}"
            if member < 1000
            else f"601{member - 1000:03d}"
        ): {
            START: Decimal(median_start),
            END: Decimal(median_end),
        }
        for member in range(market_members)
    }
    stock_closes["600001"] = {
        START: Decimal(stock_start),
        END: Decimal(stock_end),
    }
    return MarketClosePanel(
        train_dates=(START, END),
        stock_closes=stock_closes,
        index_closes={
            "sh.000001": {
                START: Decimal(index_start),
                END: Decimal(index_end),
            },
        },
    )


@pytest.mark.parametrize(
    ("code", "expected"),
    (
        ("600001", "sh.000001"),
        ("601001.SH", "sh.000001"),
        ("603001", "sh.000001"),
        ("605001", "sh.000001"),
        ("000001", "sz.399001"),
        ("001001.SZ", "sz.399001"),
        ("002001", "sz.399001"),
        ("003001", "sz.399001"),
        ("688001", "sh.000688"),
    ),
)
def test_v3_attribution_maps_supported_boards_to_indexes(
    code: str,
    expected: str,
) -> None:
    assert matched_index_id(code) == expected


@pytest.mark.parametrize("code", ("300001", "830001", "900001", "fund"))
def test_v3_attribution_rejects_unsupported_boards(code: str) -> None:
    with pytest.raises(ValueError, match="unsupported attribution board"):
        matched_index_id(code)


def test_fixed_five_date_never_crosses_train_boundary() -> None:
    dates = weekday_dates(7, start=START)

    assert fifth_subsequent_train_date(dates[0], dates) == dates[5]
    assert fifth_subsequent_train_date(dates[2], dates) is None


@pytest.mark.parametrize(
    "dates",
    (
        (START, START),
        (END, START),
    ),
)
def test_fixed_five_date_rejects_non_increasing_train_calendar(
    dates: tuple[date, ...],
) -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        fifth_subsequent_train_date(START, dates)


def test_fixed_five_date_rejects_signal_outside_train_calendar() -> None:
    dates = weekday_dates(7, start=START)

    with pytest.raises(ValueError, match="signal date is not in train calendar"):
        fifth_subsequent_train_date(date(2026, 6, 30), dates)


def test_simple_return_is_exact_decimal() -> None:
    assert simple_return(Decimal("7.5"), Decimal("8.25")) == Decimal("0.1")


@pytest.mark.parametrize(
    ("start", "end"),
    (
        (Decimal("0"), Decimal("1")),
        (Decimal("1"), Decimal("-1")),
        (Decimal("NaN"), Decimal("1")),
        (Decimal("1"), Decimal("Infinity")),
    ),
)
def test_simple_return_rejects_non_positive_or_non_finite_endpoints(
    start: Decimal,
    end: Decimal,
) -> None:
    with pytest.raises(ValueError, match="finite positive close"):
        simple_return(start, end)


def test_interval_attribution_uses_dual_benchmarks_and_decimal() -> None:
    value = attribute_interval("600001", START, END, _market_panel())

    assert value.raw_return == Decimal("0.1")
    assert value.matched_index_return == Decimal("0.02")
    assert value.market_median_return == Decimal("0.05")
    assert value.index_excess == Decimal("0.08")
    assert value.market_median_excess == Decimal("0.05")
    assert value.market_members == 1000


def test_interval_attribution_uses_even_cross_sectional_return_median() -> None:
    panel = _market_panel(market_members=1000)
    stock_closes = dict(panel.stock_closes)
    stock_closes["600998"] = {START: Decimal("10"), END: Decimal("10.40")}
    stock_closes["600999"] = {START: Decimal("10"), END: Decimal("10.60")}

    value = attribute_interval(
        "600001",
        START,
        END,
        MarketClosePanel(panel.train_dates, stock_closes, panel.index_closes),
    )

    assert value.market_median_return == Decimal("0.05")


def test_interval_attribution_uses_odd_cross_sectional_return_median() -> None:
    panel = _market_panel(market_members=1001)
    stock_closes = dict(panel.stock_closes)
    member_codes = tuple(sorted(stock_closes))
    for member_code in member_codes[:500]:
        stock_closes[member_code] = {
            START: Decimal("10"),
            END: Decimal("10.40"),
        }
    stock_closes[member_codes[500]] = {
        START: Decimal("10"),
        END: Decimal("10.50"),
    }
    for member_code in member_codes[501:]:
        stock_closes[member_code] = {
            START: Decimal("10"),
            END: Decimal("10.60"),
        }

    value = attribute_interval(
        "600001",
        START,
        END,
        MarketClosePanel(panel.train_dates, stock_closes, panel.index_closes),
    )

    assert value.market_median_return == Decimal("0.05")
    assert value.market_members == 1001


def test_interval_attribution_excludes_non_main_board_from_market_median() -> None:
    panel = _market_panel()
    stock_closes = dict(panel.stock_closes)
    stock_closes["300001"] = {START: Decimal("1"), END: Decimal("100")}

    value = attribute_interval(
        "600001",
        START,
        END,
        MarketClosePanel(panel.train_dates, stock_closes, panel.index_closes),
    )

    assert value.market_median_return == Decimal("0.05")
    assert value.market_members == 1000


def test_interval_attribution_rejects_interval_outside_train_calendar() -> None:
    panel = _market_panel()

    with pytest.raises(ValueError, match="interval endpoints must be train dates"):
        attribute_interval("600001", START, date(2026, 7, 9), panel)


def test_interval_attribution_fails_closed_when_index_endpoint_is_missing() -> None:
    panel = _market_panel()
    incomplete = MarketClosePanel(
        panel.train_dates,
        panel.stock_closes,
        {"sh.000001": {START: Decimal("100")}},
    )

    with pytest.raises(MarketCoverageIncomplete) as raised:
        attribute_interval("600001", START, END, incomplete)

    assert raised.value.reason == "INDEX_ENDPOINT_MISSING"


def test_interval_attribution_requires_one_thousand_market_members() -> None:
    panel = _market_panel(market_members=999)

    with pytest.raises(MarketCoverageIncomplete) as raised:
        attribute_interval("600001", START, END, panel)

    assert raised.value.reason == "MARKET_MEMBERS_BELOW_1000"
