from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json

import pytest

from stock_ai.buy_point_selection.public_challenger_runtime import (
    PublicChallengerRuntimeInputs,
    build_public_challenger_research,
    build_public_challenger_test,
    load_mysql_public_challenger_inputs,
)
from stock_ai.buy_point_selection.public_challenger_report import (
    PublicChallengerFreezeArtifact,
)
from stock_ai.buy_point_selection.public_challenger_signals import EXECUTION_TRACK
from stock_ai.buy_point_selection.public_challenger_validation import (
    PublicChallengerFreezeReview,
)
from stock_ai.buy_point_selection.reference_sources import IndexBar
from stock_ai.buy_point_selection.models import BuyPointBar
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    SectorMembership,
)


def _weekday_dates(count: int, start: date = date(2023, 1, 3)) -> tuple[date, ...]:
    values: list[date] = []
    current = start
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current)
        current += timedelta(days=1)
    return tuple(values)


class _FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


class _Repository:
    def coverage_between(self, dates):
        return {}

    def memberships_between(self, start: date, end: date):
        return ()

    def risk_flags_between(self, start: date, end: date):
        return ()


def test_mysql_loader_uses_literal_bounds_and_disposes_engine() -> None:
    signal_dates = _weekday_dates(630)
    history_start = signal_dates[0] - timedelta(days=120)
    outcome_cutoff = signal_dates[-1] + timedelta(days=10)
    engine = _FakeEngine()
    calls: list[tuple[object, ...]] = []

    def engine_factory(url: str, **kwargs):
        calls.append(("engine", url, kwargs))
        return engine

    def trade_dates_loader(actual_engine, start: date, end: date):
        calls.append(("dates", actual_engine, start, end))
        return tuple(
            value
            for value in _weekday_dates(760, history_start)
            if value <= end
        )

    def bars_loader(actual_engine, start: date, end: date):
        calls.append(("bars", actual_engine, start, end))
        return {}

    def benchmark_loader(start: date, end: date):
        calls.append(("benchmarks", start, end))
        return {
            code: (
                IndexBar(code, start, Decimal("100"), Decimal("0")),
                IndexBar(code, end, Decimal("101"), Decimal("1")),
            )
            for code in ("sh.000001", "sz.399001", "sh.000688")
        }

    inputs = load_mysql_public_challenger_inputs(
        signal_dates=signal_dates,
        history_start=history_start,
        outcome_cutoff=outcome_cutoff,
        mysql_url="mysql+pymysql://user:password@192.168.1.13:3306/stock",
        engine_factory=engine_factory,
        trade_dates_loader=trade_dates_loader,
        bars_loader=bars_loader,
        repository_factory=lambda _: _Repository(),
        aggregate_loader=lambda *_: {},
        benchmark_loader=benchmark_loader,
        holdings_loader=lambda _: frozenset(),
    )

    assert engine.disposed is True
    assert ("bars", engine, history_start, outcome_cutoff) in calls
    assert ("benchmarks", history_start, outcome_cutoff) in calls
    assert inputs.signal_dates == signal_dates
    assert set(inputs.market_status_by_date.values()) == {"FREEZE"}
    assert "mysql" not in inputs.input_fingerprint.lower()
    assert "password" not in inputs.input_fingerprint.lower()


def test_mysql_loader_disposes_engine_when_an_adapter_fails() -> None:
    signal_dates = _weekday_dates(630)
    engine = _FakeEngine()

    with pytest.raises(RuntimeError, match="loader failed"):
        load_mysql_public_challenger_inputs(
            signal_dates=signal_dates,
            history_start=date(2022, 1, 1),
            outcome_cutoff=signal_dates[-1],
            mysql_url="mysql+pymysql://u:p@192.168.1.13:3306/stock",
            engine_factory=lambda *_args, **_kwargs: engine,
            trade_dates_loader=lambda *_args: (_ for _ in ()).throw(
                RuntimeError("loader failed")
            ),
            bars_loader=lambda *_args: {},
            repository_factory=lambda _: _Repository(),
            benchmark_loader=lambda *_args: {},
            market_status_loader=lambda *_args: {},
            holdings_loader=lambda _: frozenset(),
        )

    assert engine.disposed is True


def test_research_builder_rejects_missing_point_in_time_coverage() -> None:
    signal_dates = _weekday_dates(630)
    incomplete = PublicChallengerRuntimeInputs(
        signal_dates=signal_dates,
        trading_dates=signal_dates,
        bars_by_code={},
        memberships=(),
        risk_flags=(),
        coverage_by_date={},
        market_status_by_date={},
        index_closes={},
        held_codes=frozenset(),
        input_fingerprint="a" * 64,
    )

    with pytest.raises(ValueError, match="POINT_IN_TIME_INPUT_INCOMPLETE"):
        build_public_challenger_research(incomplete)


def _complete_runtime_inputs(
    *,
    boundary_allow: bool = False,
    include_test_data: bool = False,
):
    calendar = _weekday_dates(66 + 630)
    signal_dates = calendar[66:]
    data_end = signal_dates[-1] if include_test_data else signal_dates[503]
    codes = tuple(f"60000{value}" for value in range(1, 6))
    bars_by_code = {}
    for offset, code in enumerate(codes):
        rows = []
        prior = Decimal("10") + Decimal(offset)
        for index, trade_date in enumerate(calendar):
            close = prior * (Decimal("1") + Decimal(offset - 2) / Decimal("10000"))
            rows.append(
                BuyPointBar(
                    trade_date=trade_date,
                    open=close,
                    high=close * Decimal("1.01"),
                    low=close * Decimal("0.99"),
                    close=close,
                    pct_chg=Decimal("0"),
                    amount_qian=Decimal("1000000"),
                )
            )
            prior = close
        bars_by_code[code] = tuple(
            row for row in rows if row.trade_date <= data_end
        )
    memberships = tuple(
        SectorMembership(
            code=code,
            sector_code="TEST",
            sector_name="测试行业",
            valid_from=calendar[0],
            valid_to=None,
            source="TEST",
        )
        for code in codes
    )
    coverage = {
        trade_date: ReferenceCoverage(trade_date, True, True, True)
        for trade_date in signal_dates
    }
    market = {trade_date: "FREEZE" for trade_date in signal_dates}
    if boundary_allow:
        market[signal_dates[377]] = "ALLOW"
    closes = {
        code: {
            trade_date: Decimal("100") + Decimal(index) / Decimal("10")
            for index, trade_date in enumerate(calendar)
            if trade_date <= data_end
        }
        for code in ("sh.000001", "sz.399001", "sh.000688")
    }
    return PublicChallengerRuntimeInputs(
        signal_dates=signal_dates,
        trading_dates=calendar,
        bars_by_code=bars_by_code,
        memberships=memberships,
        risk_flags=(),
        coverage_by_date=coverage,
        market_status_by_date=market,
        index_closes=closes,
        held_codes=frozenset(),
        input_fingerprint="b" * 64,
    )


def test_research_builds_train_and_validation_without_reading_test_outcomes() -> None:
    review = build_public_challenger_research(_complete_runtime_inputs())

    assert len(review.split.train) == 378
    assert len(review.split.validation) == 126
    assert len(review.split.test) == 126
    assert review.test_outcomes_read is False
    assert review.trade_permission == "NO-TRADE"
    assert review.validation_assessment.execution_metrics.segment == "VALIDATION"
    assert (
        review.validation_assessment.execution_metrics.positive_window_ratio
        == review.track_metrics[EXECUTION_TRACK].positive_window_ratio
    )


def test_train_holding_period_cannot_cross_validation_boundary() -> None:
    review = build_public_challenger_research(
        _complete_runtime_inputs(boundary_allow=True)
    )

    assert review.funnel_counts["OUTCOME_CROSSES_SEGMENT"] == 1


def _split_identity(signal_dates: tuple[date, ...]) -> str:
    payload = {
        "train": [value.isoformat() for value in signal_dates[:378]],
        "validation": [value.isoformat() for value in signal_dates[378:504]],
        "test": [value.isoformat() for value in signal_dates[504:]],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def test_test_builder_is_inconclusive_without_same_segment_v3() -> None:
    inputs = _complete_runtime_inputs(include_test_data=True)
    research = build_public_challenger_research(inputs)
    split_identity = _split_identity(inputs.signal_dates)
    freeze_review = PublicChallengerFreezeReview(
        parent_research_identity="c" * 64,
        input_fingerprint=inputs.input_fingerprint,
        split_identity=split_identity,
        frozen_rule_hash="d" * 64,
        test_eligible=True,
        reasons=(),
    )
    freeze = PublicChallengerFreezeArtifact(
        artifact_identity="e" * 64,
        parent_research_identity=freeze_review.parent_research_identity,
        input_fingerprint=inputs.input_fingerprint,
        split_identity=split_identity,
        test_eligible=True,
        review=freeze_review,
        payload={"artifact_identity": "e" * 64},
    )

    review = build_public_challenger_test(freeze, research, inputs, None)

    assert review.parent_freeze_identity == freeze.artifact_identity
    assert review.assessment.verdict == "INCONCLUSIVE"
    assert review.assessment.reasons == ("V3_COMPARABLE_MISSING",)
    assert review.assessment.execution_metrics.segment == "TEST"
    assert review.trade_permission == "NO-TRADE"
