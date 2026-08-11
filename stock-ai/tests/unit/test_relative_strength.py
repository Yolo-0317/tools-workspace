from __future__ import annotations

from datetime import date
import math

import pytest

from stock_ai.relative_strength import ClosePair, build_relative_strength_snapshot


PRIOR = date(2026, 7, 13)
CURRENT = date(2026, 8, 10)


def _pairs(count: int) -> tuple[ClosePair, ...]:
    return tuple(
        ClosePair(f"{600000 + index:06d}", 10.0, 10.0 + index / 100.0)
        for index in range(count)
    )


def test_tied_returns_receive_the_average_percentile_rank() -> None:
    snapshot = build_relative_strength_snapshot(
        current_trade_date=CURRENT,
        current_count=4,
        prior_trade_date=PRIOR,
        pairs=(
            ClosePair("600001", 10, 11),
            ClosePair("600002", 10, 12),
            ClosePair("000001", 10, 11),
            ClosePair("000002", 10, 9),
        ),
    )

    assert snapshot.percentiles["600002"] == 1.0
    assert snapshot.percentiles["600001"] == pytest.approx(0.5)
    assert snapshot.percentiles["000001"] == pytest.approx(0.5)
    assert snapshot.percentiles["000002"] == 0.0


def test_coverage_below_95_percent_is_not_usable() -> None:
    snapshot = build_relative_strength_snapshot(
        current_trade_date=CURRENT,
        current_count=100,
        prior_trade_date=PRIOR,
        pairs=_pairs(94),
    )

    assert snapshot.coverage_ratio == pytest.approx(0.94)
    assert snapshot.is_usable is False


def test_suffix_duplicate_is_preferred_and_normalized_to_six_digits() -> None:
    snapshot = build_relative_strength_snapshot(
        current_trade_date=CURRENT,
        current_count=1,
        prior_trade_date=PRIOR,
        pairs=(
            ClosePair("600001", 10, 11),
            ClosePair("600001.SH", 10, 12),
        ),
    )

    assert snapshot.eligible_count == 1
    assert snapshot.returns20 == {"600001": pytest.approx(0.2)}
    assert snapshot.percentiles == {"600001": 1.0}


def test_invalid_closes_and_non_main_board_codes_are_excluded() -> None:
    snapshot = build_relative_strength_snapshot(
        current_trade_date=CURRENT,
        current_count=5,
        prior_trade_date=PRIOR,
        pairs=(
            ClosePair("600001", 0, 11),
            ClosePair("600002", 10, math.nan),
            ClosePair("300001.SZ", 10, 12),
            ClosePair("920001.BJ", 10, 12),
            ClosePair("000001.SZ", 10, 11),
        ),
    )

    assert snapshot.eligible_count == 1
    assert snapshot.percentiles == {"000001": 1.0}


def test_one_code_universe_receives_top_percentile() -> None:
    snapshot = build_relative_strength_snapshot(
        current_trade_date=CURRENT,
        current_count=1,
        prior_trade_date=PRIOR,
        pairs=(ClosePair("003001.SZ", 10, 11),),
    )

    assert snapshot.percentiles == {"003001": 1.0}
    assert snapshot.coverage_ratio == 1.0
    assert snapshot.is_usable is True


def test_zero_current_universe_is_not_usable() -> None:
    snapshot = build_relative_strength_snapshot(
        current_trade_date=CURRENT,
        current_count=0,
        prior_trade_date=PRIOR,
        pairs=(),
    )

    assert snapshot.coverage_ratio == 0.0
    assert snapshot.is_usable is False
