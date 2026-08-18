"""Point-in-time runtime adapters for the isolated public challenger."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
import os
from typing import Callable, Mapping, Sequence

from stock_ai.market_codes import normalize_code6

from .five_day_ranking_v3_attribution_market import load_required_benchmark_closes
from .execution import ExecutionCosts
from .gates import classify_market
from .historical_replay_runtime import (
    BENCHMARK_INDEX_CODES,
    _load_daily_bars,
    _load_market_aggregates,
    _trade_dates,
    build_historical_market_snapshots,
)
from .models import BuyPointBar
from .reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SQLReferenceRepository,
    SectorMembership,
    membership_on,
)
from .public_challenger_execution import (
    simulate_direct_five_day,
    simulate_reclaim_five_day,
)
from .public_challenger_portfolio import (
    eligible_universe_on,
    qualify_track_signals,
    select_capacity_matched,
)
from .public_challenger_signals import (
    CONTRARIAN_TRACK,
    EXECUTION_TRACK,
    RESIDUAL_TRACK,
    build_contrarian_signals,
    build_execution_signals,
    build_residual_signals,
)
from .public_challenger_validation import (
    ChallengerObservation,
    PublicChallengerResearchReview,
    PublicChallengerTestReview,
    V3ComparableArtifact,
    compare_with_v3,
    evaluate_execution_segment,
)
from .validation import chronological_split


PUBLIC_CHALLENGER_RUNTIME_VERSION = "public-challenger-runtime-v1"


@dataclass(frozen=True)
class PublicChallengerRuntimeInputs:
    signal_dates: tuple[date, ...]
    trading_dates: tuple[date, ...]
    bars_by_code: Mapping[str, tuple[BuyPointBar, ...]]
    memberships: tuple[SectorMembership, ...]
    risk_flags: tuple[RiskFlag, ...]
    coverage_by_date: Mapping[date, ReferenceCoverage]
    market_status_by_date: Mapping[date, str]
    index_closes: Mapping[str, Mapping[date, Decimal]]
    held_codes: frozenset[str]
    input_fingerprint: str


def _strict_dates(values: Sequence[date], label: str) -> tuple[date, ...]:
    ordered = tuple(values)
    if not ordered or any(
        current <= previous
        for previous, current in zip(ordered, ordered[1:])
    ):
        raise ValueError(f"{label}_DATES_NOT_STRICT")
    return ordered


def _default_benchmark_loader(
    start: date,
    end: date,
) -> Mapping[str, Sequence[object]]:
    from .reference_baostock import BaoStockReferenceProvider

    provider = BaoStockReferenceProvider()
    with provider.session():
        return {
            code: tuple(provider.fetch_index_bars(code, start, end))
            for code in BENCHMARK_INDEX_CODES
        }


def _load_current_held_codes(engine: object) -> frozenset[str]:
    """Read the latest complete position snapshot without mutating the ledger."""
    from sqlalchemy import text

    with engine.connect() as connection:
        snapshot_date = connection.execute(
            text("SELECT MAX(snapshot_date) FROM portfolio_positions_daily")
        ).scalar_one_or_none()
        if snapshot_date is None:
            return frozenset()
        rows = connection.execute(
            text(
                "SELECT ts_code FROM portfolio_positions_daily "
                "WHERE snapshot_date=:snapshot_date AND shares > 0"
            ),
            {"snapshot_date": snapshot_date},
        ).scalars()
        return frozenset(normalize_code6(str(value)) for value in rows)


def _canonical_fingerprint(
    *,
    signal_dates: Sequence[date],
    trading_dates: Sequence[date],
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    memberships: Sequence[SectorMembership],
    risk_flags: Sequence[RiskFlag],
    coverage_by_date: Mapping[date, ReferenceCoverage],
    market_status_by_date: Mapping[date, str],
    index_closes: Mapping[str, Mapping[date, Decimal]],
    held_codes: frozenset[str],
) -> str:
    payload = {
        "version": PUBLIC_CHALLENGER_RUNTIME_VERSION,
        "signal_dates": [value.isoformat() for value in signal_dates],
        "trading_dates": [value.isoformat() for value in trading_dates],
        "bars": {
            code: [
                [
                    row.trade_date.isoformat(),
                    str(row.open),
                    str(row.high),
                    str(row.low),
                    str(row.close),
                    str(row.pct_chg),
                    str(row.amount_qian),
                ]
                for row in values
            ]
            for code, values in sorted(bars_by_code.items())
        },
        "memberships": [
            [
                normalize_code6(row.code),
                row.sector_code,
                row.sector_name,
                row.valid_from.isoformat(),
                row.valid_to.isoformat() if row.valid_to else None,
                row.source,
            ]
            for row in sorted(
                memberships,
                key=lambda row: (
                    normalize_code6(row.code),
                    row.valid_from,
                    row.sector_code,
                ),
            )
        ],
        "risk_flags": [
            [
                normalize_code6(row.code),
                row.flag_type,
                row.severity,
                row.effective_from.isoformat(),
                row.effective_to.isoformat() if row.effective_to else None,
                row.source,
                row.evidence_ref,
            ]
            for row in sorted(
                risk_flags,
                key=lambda row: (
                    normalize_code6(row.code),
                    row.effective_from,
                    row.flag_type,
                ),
            )
        ],
        "coverage": {
            day.isoformat(): [
                value.sector_complete,
                value.st_complete,
                value.announcement_complete,
            ]
            for day, value in sorted(coverage_by_date.items())
        },
        "market_status": {
            day.isoformat(): str(value)
            for day, value in sorted(market_status_by_date.items())
        },
        "index_closes": {
            code: {
                day.isoformat(): str(value)
                for day, value in sorted(closes.items())
            }
            for code, closes in sorted(index_closes.items())
        },
        "held_codes": sorted(normalize_code6(code) for code in held_codes),
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_mysql_public_challenger_inputs(
    signal_dates: Sequence[date],
    history_start: date,
    outcome_cutoff: date,
    *,
    mysql_url: str | None = None,
    engine_factory: Callable[..., object] | None = None,
    trade_dates_loader: Callable[..., Sequence[date]] | None = None,
    bars_loader: Callable[..., Mapping[str, Sequence[BuyPointBar]]] | None = None,
    repository_factory: Callable[[object], object] | None = None,
    aggregate_loader: Callable[..., Mapping[date, object]] | None = None,
    benchmark_loader: Callable[[date, date], Mapping[str, Sequence[object]]]
    | None = None,
    market_status_loader: Callable[..., Mapping[date, str]] | None = None,
    holdings_loader: Callable[[object], frozenset[str]] | None = None,
) -> PublicChallengerRuntimeInputs:
    """Load one bounded, read-only and credential-free-fingerprinted input bundle."""
    from dotenv import load_dotenv
    from sqlalchemy import create_engine

    ordered_signals = _strict_dates(signal_dates, "SIGNAL")
    if history_start > ordered_signals[0] or outcome_cutoff < ordered_signals[-1]:
        raise ValueError("PUBLIC_CHALLENGER_BOUNDS_INVALID")

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    load_dotenv(os.path.join(root, ".env"), override=False)
    resolved_url = (mysql_url or os.environ.get("MYSQL_URL", "")).replace(
        "host.docker.internal",
        "127.0.0.1",
    )
    if not resolved_url:
        raise RuntimeError("MYSQL_URL is not configured")

    create = engine_factory or create_engine
    engine = create(resolved_url, pool_pre_ping=True)
    try:
        runtime_dates = _strict_dates(
            (trade_dates_loader or _trade_dates)(
                engine,
                history_start,
                outcome_cutoff,
            ),
            "TRADING",
        )
        if not frozenset(ordered_signals).issubset(runtime_dates):
            raise RuntimeError("bounded daily-bar calendar is incomplete")

        bars_by_code = {
            normalize_code6(code): tuple(
                sorted(values, key=lambda row: row.trade_date)
            )
            for code, values in (bars_loader or _load_daily_bars)(
                engine,
                history_start,
                outcome_cutoff,
            ).items()
        }
        repository = (repository_factory or SQLReferenceRepository)(engine)
        coverage = dict(repository.coverage_between(ordered_signals))
        memberships = tuple(
            repository.memberships_between(history_start, ordered_signals[-1])
        )
        risk_flags = tuple(
            repository.risk_flags_between(ordered_signals[0], outcome_cutoff)
        )

        load_benchmarks = benchmark_loader or _default_benchmark_loader
        benchmark_cache: Mapping[str, Sequence[object]] | None = None

        def cached_benchmarks(start: date, end: date):
            nonlocal benchmark_cache
            if benchmark_cache is None:
                benchmark_cache = load_benchmarks(start, end)
            return benchmark_cache

        index_closes = load_required_benchmark_closes(
            BENCHMARK_INDEX_CODES,
            history_start,
            outcome_cutoff,
            benchmark_loader=cached_benchmarks,
        )
        if market_status_loader is None:
            aggregates = (aggregate_loader or _load_market_aggregates)(
                engine,
                history_start,
                outcome_cutoff,
            )
            snapshots = build_historical_market_snapshots(
                runtime_dates,
                bars_by_code,
                cached_benchmarks(history_start, outcome_cutoff),
                market_aggregates_by_date=aggregates,
            )
            market_statuses = {
                day: classify_market(snapshot).status
                for day, snapshot in snapshots.items()
            }
        else:
            market_statuses = dict(
                market_status_loader(
                    engine,
                    ordered_signals,
                    history_start,
                    outcome_cutoff,
                    bars_by_code,
                    index_closes,
                )
            )
        held_codes = frozenset(
            (holdings_loader or _load_current_held_codes)(engine)
        )
        fingerprint = _canonical_fingerprint(
            signal_dates=ordered_signals,
            trading_dates=runtime_dates,
            bars_by_code=bars_by_code,
            memberships=memberships,
            risk_flags=risk_flags,
            coverage_by_date=coverage,
            market_status_by_date=market_statuses,
            index_closes=index_closes,
            held_codes=held_codes,
        )
        return PublicChallengerRuntimeInputs(
            signal_dates=ordered_signals,
            trading_dates=runtime_dates,
            bars_by_code=bars_by_code,
            memberships=memberships,
            risk_flags=risk_flags,
            coverage_by_date=coverage,
            market_status_by_date=market_statuses,
            index_closes=index_closes,
            held_codes=held_codes,
            input_fingerprint=fingerprint,
        )
    finally:
        dispose = getattr(engine, "dispose", None)
        if callable(dispose):
            dispose()


def _validate_research_inputs(inputs: PublicChallengerRuntimeInputs) -> None:
    if len(inputs.signal_dates) != 630:
        raise ValueError("PUBLIC_CHALLENGER_REQUIRES_630_SESSIONS")
    split = chronological_split(inputs.signal_dates)
    research_dates = split.train + split.validation
    if any(
        day not in inputs.coverage_by_date
        or not inputs.coverage_by_date[day].sector_complete
        or not inputs.coverage_by_date[day].st_complete
        or day not in inputs.market_status_by_date
        for day in research_dates
    ):
        raise ValueError("POINT_IN_TIME_INPUT_INCOMPLETE")
    if not inputs.memberships:
        raise ValueError("POINT_IN_TIME_INPUT_INCOMPLETE")
    if set(inputs.index_closes) != set(BENCHMARK_INDEX_CODES):
        raise ValueError("POINT_IN_TIME_INPUT_INCOMPLETE")
    research_end = research_dates[-1]
    history_start = inputs.trading_dates[0]
    if any(
        history_start not in inputs.index_closes[index_id]
        or research_end not in inputs.index_closes[index_id]
        for index_id in BENCHMARK_INDEX_CODES
    ):
        raise ValueError("POINT_IN_TIME_INPUT_INCOMPLETE")


def _bounded_bars(
    bars_by_code: Mapping[str, Sequence[BuyPointBar]],
    through: date,
) -> dict[str, tuple[BuyPointBar, ...]]:
    return {
        code: tuple(row for row in rows if row.trade_date <= through)
        for code, rows in bars_by_code.items()
    }


def _segment_observations(
    *,
    inputs: PublicChallengerRuntimeInputs,
    segment_dates: Sequence[date],
    funnel: Counter[str],
) -> tuple[ChallengerObservation, ...]:
    dates = tuple(segment_dates)
    segment_end = dates[-1]
    segment_positions = {value: index for index, value in enumerate(dates)}
    segment_bars = _bounded_bars(inputs.bars_by_code, segment_end)
    costs = ExecutionCosts()
    observations: list[ChallengerObservation] = []

    for signal_date in dates:
        active = membership_on(inputs.memberships, signal_date)
        sector_by_code = {
            normalize_code6(code): row.sector_code
            for code, row in active.items()
        }
        eligible_codes = eligible_universe_on(
            signal_date,
            segment_bars,
            inputs.memberships,
            inputs.held_codes,
        )
        eligible_bars = {
            code: segment_bars[code]
            for code in eligible_codes
            if code in segment_bars
        }
        contrarian = build_contrarian_signals(
            signal_date=signal_date,
            bars_by_code=eligible_bars,
            sector_by_code=sector_by_code,
        )
        try:
            residual = build_residual_signals(
                signal_date=signal_date,
                bars_by_code=eligible_bars,
                memberships=inputs.memberships,
                index_closes=inputs.index_closes,
            )
        except ValueError as error:
            reason = str(error) or "RESIDUAL_SIGNAL_FAILED"
            if reason not in {
                "SECTOR_MEMBERS_BELOW_10",
                "RESIDUAL_REGRESSION_SINGULAR",
            }:
                raise ValueError("POINT_IN_TIME_INPUT_INCOMPLETE") from error
            funnel[reason] += 1
            residual = ()
        tracks = {
            CONTRARIAN_TRACK: contrarian,
            RESIDUAL_TRACK: residual,
            EXECUTION_TRACK: build_execution_signals(residual),
        }
        coverage = inputs.coverage_by_date[signal_date]
        market_status = inputs.market_status_by_date[signal_date]
        for track_id, signals in tracks.items():
            decisions = tuple(
                qualify_track_signals(
                    signals=(signal,),
                    coverage=coverage,
                    risk_flags=inputs.risk_flags,
                    held_codes=inputs.held_codes,
                )[track_id]
                for signal in signals
            )
            if not decisions:
                funnel[f"{track_id}:NO_SIGNAL"] += 1
                continue
            selection = select_capacity_matched(decisions, market_status)
            funnel.update(selection.funnel_counts)
            for decision in selection.selected:
                # Apply the frozen conservative buffer before reading an
                # outcome. Delayed exits unresolved at the boundary are
                # classified below without reading the following segment.
                remaining = len(dates) - segment_positions[signal_date] - 1
                if remaining < 7:
                    funnel["OUTCOME_CROSSES_SEGMENT"] += 1
                    continue
                signal = decision.signal
                bars = segment_bars.get(normalize_code6(signal.code), ())
                trade = (
                    simulate_reclaim_five_day(signal, bars, costs)
                    if track_id == EXECUTION_TRACK
                    else simulate_direct_five_day(signal, bars, costs)
                )
                if trade.exit_date is None or trade.net_return is None:
                    reason = (
                        "OUTCOME_CROSSES_SEGMENT"
                        if trade.status == "PENDING"
                        else trade.status
                    )
                    funnel[reason] += 1
                    continue
                observations.append(
                    ChallengerObservation(
                        signal=signal,
                        trade=trade,
                        selected=True,
                        resolution_date=trade.exit_date,
                    )
                )
    return tuple(observations)


def build_public_challenger_research(
    inputs: PublicChallengerRuntimeInputs,
) -> PublicChallengerResearchReview:
    """Build the train/validation review without consulting test outcomes."""
    _validate_research_inputs(inputs)
    split = chronological_split(inputs.signal_dates)
    funnel: Counter[str] = Counter()
    _segment_observations(
        inputs=inputs,
        segment_dates=split.train,
        funnel=funnel,
    )
    validation_observations = _segment_observations(
        inputs=inputs,
        segment_dates=split.validation,
        funnel=funnel,
    )
    track_metrics = {
        track_id: evaluate_execution_segment(
            tuple(
                row
                for row in validation_observations
                if row.signal.track_id == track_id
            ),
            split.validation,
            "VALIDATION",
        )
        for track_id in (CONTRARIAN_TRACK, RESIDUAL_TRACK, EXECUTION_TRACK)
    }
    execution_observations = tuple(
        row
        for row in validation_observations
        if row.signal.track_id == EXECUTION_TRACK
    )
    assessment = compare_with_v3(
        challenger=execution_observations,
        v3_days=None,
        input_fingerprint=inputs.input_fingerprint,
    )
    return PublicChallengerResearchReview(
        split=split,
        input_fingerprint=inputs.input_fingerprint,
        track_metrics=track_metrics,
        validation_assessment=assessment,
        funnel_counts=dict(sorted(funnel.items())),
        point_in_time_complete=True,
        test_outcomes_read=False,
        trade_permission="NO-TRADE",
    )


def _split_identity(signal_dates: Sequence[date]) -> str:
    split = chronological_split(signal_dates)
    payload = {
        "train": [value.isoformat() for value in split.train],
        "validation": [value.isoformat() for value in split.validation],
        "test": [value.isoformat() for value in split.test],
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_public_challenger_test(
    freeze: object,
    research: PublicChallengerResearchReview,
    inputs: PublicChallengerRuntimeInputs,
    v3: V3ComparableArtifact | None,
) -> PublicChallengerTestReview:
    """Evaluate the frozen test segment exactly once with strict lineage."""
    from .public_challenger_report import PublicChallengerFreezeArtifact

    if not isinstance(freeze, PublicChallengerFreezeArtifact):
        raise ValueError("STRICT_FREEZE_ARTIFACT_REQUIRED")
    if (
        freeze.review.parent_research_identity
        != freeze.parent_research_identity
        or freeze.review.input_fingerprint != freeze.input_fingerprint
        or freeze.review.split_identity != freeze.split_identity
        or freeze.review.test_eligible != freeze.test_eligible
    ):
        raise ValueError("FREEZE_ARTIFACT_LINEAGE_INVALID")
    if not freeze.test_eligible:
        raise ValueError("FREEZE_NOT_TEST_ELIGIBLE")
    if (
        research.input_fingerprint != inputs.input_fingerprint
        or freeze.input_fingerprint != inputs.input_fingerprint
    ):
        raise ValueError("INPUT_FINGERPRINT_MISMATCH")
    split = chronological_split(inputs.signal_dates)
    if research.split != split:
        raise ValueError("RESEARCH_SPLIT_MISMATCH")
    split_identity = _split_identity(inputs.signal_dates)
    if freeze.split_identity != split_identity:
        raise ValueError("SPLIT_IDENTITY_MISMATCH")
    if any(
        day not in inputs.coverage_by_date
        or not inputs.coverage_by_date[day].sector_complete
        or not inputs.coverage_by_date[day].st_complete
        or day not in inputs.market_status_by_date
        for day in split.test
    ):
        raise ValueError("POINT_IN_TIME_INPUT_INCOMPLETE")
    history_start = inputs.trading_dates[0]
    if set(inputs.index_closes) != set(BENCHMARK_INDEX_CODES) or any(
        history_start not in inputs.index_closes[index_id]
        or split.test[-1] not in inputs.index_closes[index_id]
        for index_id in BENCHMARK_INDEX_CODES
    ):
        raise ValueError("POINT_IN_TIME_INPUT_INCOMPLETE")
    if v3 is not None:
        if (
            v3.parent_research_identity != freeze.parent_research_identity
            or v3.input_fingerprint != inputs.input_fingerprint
            or v3.split_identity != split_identity
            or tuple(row.signal_date for row in v3.days) != split.test
        ):
            raise ValueError("V3_COMPARABLE_LINEAGE_MISMATCH")

    funnel: Counter[str] = Counter()
    observations = _segment_observations(
        inputs=inputs,
        segment_dates=split.test,
        funnel=funnel,
    )
    execution_observations = tuple(
        row for row in observations if row.signal.track_id == EXECUTION_TRACK
    )
    assessment = compare_with_v3(
        challenger=execution_observations,
        v3_days=v3.days if v3 is not None else None,
        input_fingerprint=inputs.input_fingerprint,
    )
    return PublicChallengerTestReview(
        parent_freeze_identity=freeze.artifact_identity,
        parent_research_identity=freeze.parent_research_identity,
        input_fingerprint=inputs.input_fingerprint,
        assessment=assessment,
        trade_permission="NO-TRADE",
    )
