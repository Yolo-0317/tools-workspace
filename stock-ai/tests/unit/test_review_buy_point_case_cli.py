from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, text

from scripts.analysis.review_buy_point_case import (
    CaseReviewInputs,
    DefaultRuntime,
    _load_holdings_by_date,
    _merge_missing_index_bars,
    main,
)
from stock_ai.buy_point_selection.models import BuyPointBar, MarketSnapshot
from stock_ai.buy_point_selection.reference_data import ReferenceCoverage
from stock_ai.buy_point_selection.case_review import CaseReview, CaseSignalReplay
from stock_ai.buy_point_selection.reference_sources import IndexBar


class FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[date, date, date]] = []

    def build_review(self, start: date, end: date, cutoff: date) -> CaseReview:
        self.calls.append((start, end, cutoff))
        return CaseReview(
            signal_dates=(start, end),
            outcome_cutoff=cutoff,
            rule_version="buy-point-selection-3.1.0",
            policy_hash="policy-hash",
            replay=CaseSignalReplay({}, ()),
            outcomes=(),
            winners=(),
            risk_coverage_complete=False,
        )


def test_cli_rejects_outcome_cutoff_before_signal_end(tmp_path, capsys) -> None:
    """Catches invalid chronology reaching the database runtime."""
    runtime = FakeRuntime()

    result = main(
        [
            "--signal-start",
            "2026-08-03",
            "--signal-end",
            "2026-08-07",
            "--outcome-cutoff",
            "2026-08-06",
            "--output-dir",
            str(tmp_path),
        ],
        runtime_factory=lambda: runtime,
    )

    assert result == 2
    assert runtime.calls == []
    assert "结果截止日必须晚于信号结束日" in capsys.readouterr().err


def test_cli_writes_only_case_artifacts_through_injected_runtime(tmp_path) -> None:
    """Catches the manual case command invoking a production mutation path."""
    runtime = FakeRuntime()

    result = main(
        [
            "--signal-start",
            "2026-08-03",
            "--signal-end",
            "2026-08-07",
            "--outcome-cutoff",
            "2026-08-14",
            "--output-dir",
            str(tmp_path),
        ],
        runtime_factory=lambda: runtime,
    )

    assert result == 0
    assert runtime.calls == [
        (date(2026, 8, 3), date(2026, 8, 7), date(2026, 8, 14))
    ]
    assert sorted(path.suffix for path in tmp_path.iterdir()) == [".json", ".md"]


def test_default_runtime_builds_review_from_bounded_injected_inputs() -> None:
    """Catches the runtime bypassing its bounded point-in-time input bundle."""
    signal_dates = (date(2026, 8, 3), date(2026, 8, 4))
    inputs = CaseReviewInputs(
        trading_dates=(*signal_dates, date(2026, 8, 5)),
        bars_by_code={},
        memberships=(),
        risk_flags=(),
        coverage_by_date={
            value: ReferenceCoverage(value, True, True, True)
            for value in signal_dates
        },
        market_snapshots={
            value: MarketSnapshot(3, 60.0, 1.1, True)
            for value in signal_dates
        },
        holding_codes_by_date={value: frozenset() for value in signal_dates},
    )
    calls = []
    runtime = DefaultRuntime(
        input_loader=lambda start, end, cutoff: (
            calls.append((start, end, cutoff)) or inputs
        )
    )

    review = runtime.build_review(
        signal_dates[0],
        signal_dates[-1],
        date(2026, 8, 5),
    )

    assert calls == [(signal_dates[0], signal_dates[-1], date(2026, 8, 5))]
    assert review.signal_dates == signal_dates
    assert review.outcomes == ()
    assert review.winners == ()


def test_missing_historical_holdings_marks_signal_date_incomplete() -> None:
    """Catches unknown historical positions being treated as a known empty portfolio."""
    signal = date(2026, 8, 3)
    history = tuple(
        BuyPointBar(
            signal - timedelta(days=4 - index),
            Decimal("10"),
            Decimal("10.1"),
            Decimal("9.9"),
            Decimal("10"),
            Decimal("0"),
            Decimal("200000"),
        )
        for index in range(5)
    )
    outcome = BuyPointBar(
        signal + timedelta(days=1),
        Decimal("10.2"),
        Decimal("10.6"),
        Decimal("10.1"),
        Decimal("10.5"),
        Decimal("5"),
        Decimal("200000"),
    )
    inputs = CaseReviewInputs(
        trading_dates=(signal, date(2026, 8, 4), date(2026, 8, 5)),
        bars_by_code={"600001": history + (outcome,)},
        memberships=(),
        risk_flags=(),
        coverage_by_date={signal: ReferenceCoverage(signal, True, True, True)},
        market_snapshots={signal: MarketSnapshot(3, 60.0, 1.1, True)},
        holding_codes_by_date={signal: frozenset()},
        holdings_complete_by_date={signal: False},
    )
    runtime = DefaultRuntime(input_loader=lambda *_: inputs)

    review = runtime.build_review(signal, signal, date(2026, 8, 5))

    assert review.replay.incomplete_dates == (signal,)
    assert review.winners == ()


def test_historical_holdings_use_daily_snapshot_then_append_only_events() -> None:
    """Catches current positions leaking backward into historical signal dates."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    first = date(2026, 8, 3)
    second = date(2026, 8, 4)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE portfolio_account_daily ("
                "snapshot_date DATE, snapshot_slot TEXT)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE portfolio_positions_daily ("
                "snapshot_date DATE, snapshot_slot TEXT, ts_code TEXT, shares INTEGER)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE portfolio_position_events ("
                "ts_code TEXT, shares_after INTEGER, broker_captured_at TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO portfolio_account_daily VALUES "
                "(:day, 'eod')"
            ),
            {"day": first},
        )
        connection.execute(
            text(
                "INSERT INTO portfolio_positions_daily VALUES "
                "(:day, 'eod', '600001', 100)"
            ),
            {"day": first},
        )
        connection.execute(
            text(
                "INSERT INTO portfolio_position_events VALUES "
                "('600002', 200, '2026-08-04 10:00:00')"
            )
        )

    holdings, complete = _load_holdings_by_date(engine, (first, second))

    assert holdings[first] == frozenset({"600001"})
    assert holdings[second] == frozenset({"600002"})
    assert complete == {first: True, second: True}


def test_runtime_uses_latest_complete_market_date_as_effective_cutoff() -> None:
    """Catches a requested future cutoff being presented as complete market data."""
    signal = date(2026, 8, 3)
    latest = date(2026, 8, 5)
    inputs = CaseReviewInputs(
        trading_dates=(signal, date(2026, 8, 4), latest),
        bars_by_code={},
        memberships=(),
        risk_flags=(),
        coverage_by_date={signal: ReferenceCoverage(signal, True, True, True)},
        market_snapshots={signal: MarketSnapshot(3, 60.0, 1.1, True)},
        holding_codes_by_date={signal: frozenset()},
    )
    runtime = DefaultRuntime(input_loader=lambda *_: inputs)

    review = runtime.build_review(signal, signal, date(2026, 8, 6))

    assert review.outcome_cutoff == latest


def test_eastmoney_index_rows_only_fill_missing_baostock_series() -> None:
    """Catches the fallback replacing an authoritative non-empty primary series."""
    primary_bar = IndexBar(
        "sh.000001",
        date(2026, 8, 3),
        Decimal("3550.12"),
        Decimal("0.35"),
    )

    merged = _merge_missing_index_bars(
        {
            "sh.000001": (primary_bar,),
            "sz.399001": (),
            "sh.000688": (),
        },
        {
            "000001": [
                ["2026-08-03", "1", "9999", "1", "1", "1", "1", "1", "9.99"]
            ],
            "399001": [
                [
                    "2026-08-03",
                    "1",
                    "11100.50",
                    "1",
                    "1",
                    "1",
                    "1",
                    "1",
                    "0.42",
                ]
            ],
            "000688": [
                ["2026-08-03", "1", "1025.33", "1", "1", "1", "1", "1", "-0.18"],
                ["malformed"],
            ],
        },
        start=date(2026, 8, 1),
        end=date(2026, 8, 7),
    )

    assert merged["sh.000001"] == (primary_bar,)
    assert merged["sz.399001"] == (
        IndexBar(
            "sz.399001",
            date(2026, 8, 3),
            Decimal("11100.50"),
            Decimal("0.42"),
        ),
    )
    assert merged["sh.000688"] == (
        IndexBar("sh.000688", date(2026, 8, 3), Decimal("1025.33"), Decimal("-0.18")),
    )
