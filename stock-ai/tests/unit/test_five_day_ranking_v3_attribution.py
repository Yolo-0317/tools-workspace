from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3_attribution import (
    MIN_MARKET_MEDIAN_MEMBERS,
    AttributedReturn,
    MarketClosePanel,
    MarketCoverageIncomplete,
    attribute_interval,
    attribution_verdict,
    fifth_subsequent_train_date,
    matched_index_id,
    simple_return,
    summarize_attributed_returns,
)

from five_day_ranking_v3_fixtures import weekday_dates


START = date(2026, 7, 1)
END = date(2026, 7, 8)


def _attributed(
    raw: str,
    matched_index: str,
    market_median: str,
) -> AttributedReturn:
    raw_value = Decimal(raw)
    index_value = Decimal(matched_index)
    median_value = Decimal(market_median)
    return AttributedReturn(
        raw_return=raw_value,
        matched_index_return=index_value,
        market_median_return=median_value,
        index_excess=raw_value - index_value,
        market_median_excess=raw_value - median_value,
        market_members=1000,
    )


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


def test_attribution_summary_reports_hand_derived_aggregate_metrics() -> None:
    rows = (
        _attributed("-0.02", "-0.03", "-0.04"),
        _attributed("0.04", "-0.01", "0.00"),
        _attributed("0.01", "0.00", "0.01"),
    )

    value = summarize_attributed_returns(
        rows,
        eligible_rows=4,
        excluded_missing_coverage=1,
    )

    assert value.eligible_rows == 4
    assert value.completed_rows == 3
    assert value.excluded_rows == 1
    assert value.excluded_missing_coverage == 1
    assert value.mean_return == Decimal("0.01")
    assert value.median_return == Decimal("0.01")
    assert value.positive_ratio == Decimal("2") / Decimal("3")
    assert value.positive_wilson_interval == (
        Decimal("0.2076596008020477361408035871"),
        Decimal("0.9385080552796037749310168249"),
    )
    assert value.mean_matched_index_return == (
        Decimal("-0.04") / Decimal("3")
    )
    assert value.median_matched_index_return == Decimal("-0.01")
    assert value.mean_market_median_return == Decimal("-0.01")
    assert value.median_market_median_return == Decimal("0")
    assert value.mean_index_excess == Decimal("0.07") / Decimal("3")
    assert value.median_index_excess == Decimal("0.01")
    assert value.mean_market_median_excess == Decimal("0.02")
    assert value.median_market_median_excess == Decimal("0.02")
    assert value.mean_gross_return is None
    assert value.mean_after_cost_drag is None
    assert value.verdict == "INCONCLUSIVE"


def test_attribution_summary_reports_gross_return_and_after_cost_drag() -> None:
    value = summarize_attributed_returns(
        (
            _attributed("0.04", "0.01", "0.02"),
            _attributed("-0.02", "-0.01", "-0.03"),
        ),
        eligible_rows=2,
        excluded_missing_coverage=0,
        gross_returns=(Decimal("0.05"), Decimal("-0.01")),
    )

    assert value.mean_gross_return == Decimal("0.02")
    assert value.mean_after_cost_drag == Decimal("0.01")


def test_empty_attribution_summary_uses_none_instead_of_fabricated_zero() -> None:
    value = summarize_attributed_returns(
        (),
        eligible_rows=2,
        excluded_missing_coverage=2,
    )

    assert value.completed_rows == 0
    assert value.excluded_rows == 2
    assert value.mean_return is None
    assert value.median_return is None
    assert value.positive_ratio is None
    assert value.positive_wilson_interval is None
    assert value.mean_index_excess is None
    assert value.mean_market_median_excess is None
    assert value.verdict == "INCONCLUSIVE"


@pytest.mark.parametrize(
    ("eligible_rows", "missing_coverage", "gross_returns", "message"),
    (
        (0, 0, None, "completed rows cannot exceed eligible rows"),
        (1, 1, None, "missing coverage cannot exceed excluded rows"),
        (-1, 0, None, "counts must be non-negative"),
        (1, 0, (), "gross returns must align with completed rows"),
    ),
)
def test_attribution_summary_rejects_inconsistent_counts_or_gross_rows(
    eligible_rows: int,
    missing_coverage: int,
    gross_returns: tuple[Decimal, ...] | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        summarize_attributed_returns(
            (_attributed("0.01", "0", "0"),),
            eligible_rows=eligible_rows,
            excluded_missing_coverage=missing_coverage,
            gross_returns=gross_returns,
        )


def test_attribution_summary_rejects_non_finite_values() -> None:
    row = AttributedReturn(
        raw_return=Decimal("NaN"),
        matched_index_return=Decimal("0"),
        market_median_return=Decimal("0"),
        index_excess=Decimal("0"),
        market_median_excess=Decimal("0"),
        market_members=1000,
    )

    with pytest.raises(ValueError, match="finite attribution values"):
        summarize_attributed_returns(
            (row,),
            eligible_rows=1,
            excluded_missing_coverage=0,
        )


def test_attribution_summary_rejects_non_finite_gross_return() -> None:
    with pytest.raises(ValueError, match="finite attribution values"):
        summarize_attributed_returns(
            (_attributed("0.01", "0", "0"),),
            eligible_rows=1,
            excluded_missing_coverage=0,
            gross_returns=(Decimal("NaN"),),
        )


@pytest.mark.parametrize(
    ("raw", "index_excess", "median_excess", "expected"),
    (
        ("-0.01", "0.002", "0.001", "MARKET_DRAG"),
        ("-0.01", "0", "-0.001", "STRATEGY_DRAG"),
        ("-0.01", "0.001", "0", "MIXED"),
        ("-0.01", "0", "0", "STRATEGY_DRAG"),
        ("0", "-0.001", "-0.001", "INCONCLUSIVE"),
        ("0.01", "0.001", "0.001", "INCONCLUSIVE"),
    ),
)
def test_attribution_verdict_uses_frozen_sign_truth_table(
    raw: str,
    index_excess: str,
    median_excess: str,
    expected: str,
) -> None:
    assert attribution_verdict(
        completed_rows=30,
        mean_return=Decimal(raw),
        mean_index_excess=Decimal(index_excess),
        mean_market_median_excess=Decimal(median_excess),
    ) == expected


def test_attribution_verdict_requires_thirty_completed_rows() -> None:
    assert attribution_verdict(
        completed_rows=29,
        mean_return=Decimal("-0.01"),
        mean_index_excess=Decimal("0.002"),
        mean_market_median_excess=Decimal("0.001"),
    ) == "INCONCLUSIVE"
