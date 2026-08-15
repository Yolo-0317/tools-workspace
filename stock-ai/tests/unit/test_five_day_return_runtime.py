from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from inspect import stack
from typing import Mapping, Sequence

import pytest

from stock_ai.buy_point_selection import five_day_return_validation
from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDayDiscovery,
    FiveDayForwardScreen,
    FiveDayRuntimeInputs,
    build_five_day_forward_settlement,
    build_five_day_forward_screen,
    build_five_day_research_review,
    build_five_day_test_review,
    discover_five_day_signal_plans,
    entry_blockers_by_date,
    load_mysql_five_day_inputs,
)
from stock_ai.buy_point_selection.five_day_return_report import (
    five_day_research_payload,
    five_day_test_payload,
)
from stock_ai.buy_point_selection.five_day_return_validation import (
    evaluate_validation_freeze,
)
from stock_ai.buy_point_selection.validation import ChronologicalSplit
from stock_ai.buy_point_selection.five_day_return_execution import (
    FiveDayExit,
    FiveDayTrade,
    simulate_five_day_plan,
)
from stock_ai.buy_point_selection.models import (
    BuyPointBar,
    DetectedSetup,
    MarketSnapshot,
    SectorSnapshot,
    SelectionPolicy,
    SetupType,
)
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    RiskFlag,
    SectorMembership,
)


SIGNAL = date(2026, 7, 30)
CODE = "600001"
SECTOR = "801010"


def _bars(*, amount_qian: str = "200000") -> tuple[BuyPointBar, ...]:
    start = SIGNAL - timedelta(days=59)
    return tuple(
        BuyPointBar(
            trade_date=start + timedelta(days=index),
            open=Decimal("9.80"),
            high=Decimal("9.90"),
            low=Decimal("9.70"),
            close=Decimal("9.80"),
            pct_chg=Decimal("0"),
            amount_qian=Decimal(amount_qian),
        )
        for index in range(60)
    )


def _setup(
    bars: Sequence[BuyPointBar],
    *,
    structure_low: str = "9.60",
    quality: str = "0.80",
    setup_type: SetupType = SetupType.TREND_PULLBACK,
) -> DetectedSetup:
    return DetectedSetup(
        code=CODE,
        setup_type=setup_type,
        analysis_date=bars[-1].trade_date,
        structure_start=bars[-10].trade_date,
        structure_high=Decimal("10.00"),
        structure_low=Decimal(structure_low),
        quality=Decimal(quality),
        reasons=("FIXTURE_SETUP",),
        metrics={},
    )


def _sector_builder(
    *,
    resonating: bool,
):
    def build(
        panel: Mapping[str, Sequence[BuyPointBar]],
        memberships: Mapping[str, SectorMembership],
        policy: SelectionPolicy,
    ) -> Mapping[str, SectorSnapshot]:
        del panel, memberships, policy
        if resonating:
            return {
                SECTOR: SectorSnapshot(
                    SECTOR,
                    "能源",
                    0.90,
                    6,
                    3,
                    0.60,
                    1.00,
                    True,
                )
            }
        return {
            SECTOR: SectorSnapshot(
                SECTOR,
                "能源",
                0.20,
                6,
                0,
                0.10,
                0.50,
                True,
            )
        }

    return build


def _fixture_inputs(
    *,
    market_status: str = "ALLOW",
    sector_resonating: bool = True,
    anti_chase_passed: bool = True,
    hard_failure: str | None = None,
    structure_low: str = "9.60",
    bars: Sequence[BuyPointBar] | None = None,
    setups: Sequence[DetectedSetup] | None = None,
) -> dict[str, object]:
    resolved_bars = tuple(bars or _bars())
    if not anti_chase_passed:
        resolved_bars = (
            *resolved_bars[:-1],
            replace(resolved_bars[-1], pct_chg=Decimal("6")),
        )
    coverage = ReferenceCoverage(SIGNAL, True, True, True)
    risk_flags: tuple[RiskFlag, ...] = ()
    memberships: tuple[SectorMembership, ...] = (
        SectorMembership(CODE, SECTOR, "能源", SIGNAL, None, "fixture"),
    )
    if hard_failure == "POINT_IN_TIME_COVERAGE_INCOMPLETE":
        coverage = replace(coverage, announcement_complete=False)
    elif hard_failure == "POINT_IN_TIME_RISK_VETO":
        risk_flags = (
            RiskFlag(CODE, "ST", "VETO", SIGNAL, None, "fixture"),
        )
    elif hard_failure == "LIQUIDITY_TOO_LOW":
        resolved_bars = tuple(
            replace(value, amount_qian=Decimal("99999"))
            if index >= 55
            else value
            for index, value in enumerate(resolved_bars)
        )
    elif hard_failure == "MARKET_FREEZE":
        market_status = "FREEZE"
    elif hard_failure == "SECTOR_MISSING":
        memberships = ()

    market = {
        "ALLOW": MarketSnapshot(3, 60.0, 1.0, True),
        "LIMITED": MarketSnapshot(2, 48.0, 0.9, True),
        "FREEZE": MarketSnapshot(1, 30.0, 1.0, True),
    }[market_status]

    def detect(
        code: str,
        bounded: Sequence[BuyPointBar],
        policy: SelectionPolicy,
    ) -> Sequence[DetectedSetup]:
        del code, policy
        if setups is not None:
            return setups
        return (_setup(bounded, structure_low=structure_low),)

    return {
        "signal_dates": (SIGNAL,),
        "trading_dates": (
            SIGNAL - timedelta(days=1),
            SIGNAL,
            SIGNAL + timedelta(days=1),
            SIGNAL + timedelta(days=2),
        ),
        "bars_by_code": {CODE: resolved_bars},
        "memberships": memberships,
        "risk_flags": risk_flags,
        "coverage_by_date": {SIGNAL: coverage},
        "market_snapshots": {SIGNAL: market},
        "setup_detector": detect,
        "sector_snapshot_builder": _sector_builder(
            resonating=sector_resonating
        ),
    }


def test_discovery_keeps_limited_and_weak_evidence_as_soft_features() -> None:
    result = discover_five_day_signal_plans(
        **_fixture_inputs(
            market_status="LIMITED",
            sector_resonating=False,
            anti_chase_passed=False,
        )
    )

    assert len(result.plans) == 4
    assert {value.candidate.market_status for value in result.plans} == {
        "LIMITED"
    }
    assert {value.candidate.sector_resonating for value in result.plans} == {
        False
    }
    assert {value.candidate.anti_chase_passed for value in result.plans} == {
        False
    }
    assert all(value.executable_shares == 0 for value in result.plans)


@pytest.mark.parametrize(
    "reason",
    (
        "POINT_IN_TIME_COVERAGE_INCOMPLETE",
        "POINT_IN_TIME_RISK_VETO",
        "LIQUIDITY_TOO_LOW",
        "MARKET_FREEZE",
        "SECTOR_MISSING",
    ),
)
def test_discovery_fails_closed_on_each_hard_gate(reason: str) -> None:
    result = discover_five_day_signal_plans(
        **_fixture_inputs(hard_failure=reason)
    )

    assert result.plans == ()
    assert result.rejection_counts[reason] >= 1


def test_discovery_expands_one_setup_into_the_exact_four_profiles() -> None:
    result = discover_five_day_signal_plans(**_fixture_inputs())

    assert tuple(value.profile.profile_id for value in result.plans) == (
        "BREAKOUT_TRIGGER__FIXED_3_PERCENT",
        "BREAKOUT_TRIGGER__STRUCTURE_ATR",
        "PULLBACK_RECLAIM__FIXED_3_PERCENT",
        "PULLBACK_RECLAIM__STRUCTURE_ATR",
    )
    assert len({value.structure_id for value in result.plans}) == 4
    assert {value.breakout_trigger for value in result.plans} == {
        Decimal("10.01")
    }
    assert {value.signal_close for value in result.plans} == {Decimal("9.80")}
    assert tuple(value.reference_entry for value in result.plans) == (
        Decimal("10.01"),
        Decimal("10.01"),
        Decimal("9.80"),
        Decimal("9.80"),
    )
    assert {value.candidate.valid_through_trade_date for value in result.plans} == {
        SIGNAL + timedelta(days=2)
    }
    assert all(value.status == "CASE_ANALYSIS_ONLY" for value in result.plans)
    assert all(value.trade_permission == "NO-TRADE" for value in result.plans)


def test_discovery_rejects_an_explicit_empty_profile_matrix() -> None:
    with pytest.raises(ValueError, match="profile matrix"):
        discover_five_day_signal_plans(
            **_fixture_inputs(),
            profiles=(),
        )


def test_discovery_chooses_the_highest_quality_setup_deterministically() -> None:
    bars = _bars()
    lower = _setup(
        bars,
        quality="0.40",
        setup_type=SetupType.PRE_BREAKOUT,
    )
    higher = _setup(
        bars,
        quality="0.80",
        setup_type=SetupType.TREND_PULLBACK,
    )

    result = discover_five_day_signal_plans(
        **_fixture_inputs(bars=bars, setups=(lower, higher))
    )

    assert all(value.candidate.setup == higher for value in result.plans)


def test_discovery_ignores_future_bars_in_stop_and_resistance_evidence() -> None:
    bars = _bars()
    future = (
        replace(
            bars[-1],
            trade_date=SIGNAL + timedelta(days=1),
            high=Decimal("12.00"),
            low=Decimal("1.00"),
        ),
        replace(
            bars[-1],
            trade_date=SIGNAL + timedelta(days=2),
            high=Decimal("20.00"),
            low=Decimal("1.00"),
        ),
        replace(
            bars[-1],
            trade_date=SIGNAL + timedelta(days=3),
            high=Decimal("12.00"),
            low=Decimal("1.00"),
        ),
    )

    baseline = discover_five_day_signal_plans(
        **_fixture_inputs(bars=bars)
    )
    with_future = discover_five_day_signal_plans(
        **_fixture_inputs(bars=(*bars, *future))
    )

    assert with_future.plans == baseline.plans


def test_missing_structure_stop_rejects_only_structure_profiles() -> None:
    result = discover_five_day_signal_plans(
        **_fixture_inputs(structure_low="0.01")
    )

    assert tuple(value.profile.stop_kind for value in result.plans) == (
        "FIXED_3_PERCENT",
        "FIXED_3_PERCENT",
    )
    assert result.rejection_counts["STRUCTURE_STOP_UNAVAILABLE"] == 2


def test_entry_blockers_keep_allow_and_limited_dates_open() -> None:
    allow = SIGNAL + timedelta(days=1)
    limited = SIGNAL + timedelta(days=2)
    complete = {
        value: ReferenceCoverage(value, True, True, True)
        for value in (allow, limited)
    }

    result = entry_blockers_by_date(
        CODE,
        (limited, allow, allow),
        coverage_by_date=complete,
        risk_flags=(),
        market_snapshots={
            allow: MarketSnapshot(3, 60.0, 1.0, True),
            limited: MarketSnapshot(2, 48.0, 0.9, True),
        },
    )

    assert tuple(result) == (allow, limited)
    assert result == {allow: (), limited: ()}


def test_entry_blockers_combine_and_sort_all_hard_reasons() -> None:
    entry_date = SIGNAL + timedelta(days=1)

    result = entry_blockers_by_date(
        CODE,
        (entry_date,),
        coverage_by_date={
            entry_date: ReferenceCoverage(entry_date, True, True, False)
        },
        risk_flags=(
            RiskFlag(CODE, "SUSPENSION", "VETO", entry_date, entry_date, "fixture"),
        ),
        market_snapshots={
            entry_date: MarketSnapshot(1, 30.0, 1.0, True)
        },
    )

    assert result[entry_date] == (
        "MARKET_FREEZE",
        "POINT_IN_TIME_COVERAGE_INCOMPLETE",
        "POINT_IN_TIME_RISK_VETO",
    )


def test_entry_blockers_treat_missing_market_snapshot_as_freeze() -> None:
    entry_date = SIGNAL + timedelta(days=1)

    result = entry_blockers_by_date(
        CODE,
        (entry_date,),
        coverage_by_date={
            entry_date: ReferenceCoverage(entry_date, True, True, True)
        },
        risk_flags=(),
        market_snapshots={},
    )

    assert result[entry_date] == ("MARKET_FREEZE",)


def test_research_runtime_reads_only_through_validation_resolution_cutoff() -> None:
    signal_dates = tuple(
        date(2024, 1, 1) + timedelta(days=index) for index in range(630)
    )
    requested: list[tuple[date, date, date]] = []

    def load(
        requested_signal_dates: Sequence[date],
        history_start: date,
        signal_end: date,
        outcome_cutoff: date,
    ) -> FiveDayRuntimeInputs:
        assert tuple(requested_signal_dates) == signal_dates
        requested.append((history_start, signal_end, outcome_cutoff))
        return FiveDayRuntimeInputs(
            signal_dates=signal_dates,
            trading_dates=tuple(
                value for value in signal_dates if value <= outcome_cutoff
            ),
            bars_by_code={},
            memberships=(),
            risk_flags=(),
            coverage_by_date={},
            market_snapshots={},
            input_fingerprint="fixture-input-fingerprint",
        )

    review = build_five_day_research_review(
        signal_dates,
        input_loader=load,
    )

    assert requested == [
        (
            signal_dates[0] - timedelta(days=180),
            review.split.validation[-1],
            review.split.test[9],
        )
    ]
    assert review.split.train[-1] < review.split.validation[0]
    assert review.split.validation[-1] < review.split.test[0]
    assert review.test_outcomes_read is False
    assert all(
        value.plan.candidate.signal_date not in frozenset(review.split.test)
        for value in review.observations
    )


def test_research_runtime_discovers_simulates_and_calibrates_train_validation() -> None:
    signal_dates = tuple(
        date(2024, 1, 1) + timedelta(days=index) for index in range(630)
    )
    template = discover_five_day_signal_plans(**_fixture_inputs()).plans[0]
    train_signal = signal_dates[10]
    validation_signal = signal_dates[400]
    requested_discovery_dates: list[tuple[date, ...]] = []

    def load(
        requested_signal_dates: Sequence[date],
        history_start: date,
        signal_end: date,
        outcome_cutoff: date,
    ) -> FiveDayRuntimeInputs:
        del history_start, signal_end
        return FiveDayRuntimeInputs(
            signal_dates=tuple(requested_signal_dates),
            trading_dates=tuple(
                value for value in signal_dates if value <= outcome_cutoff
            ),
            bars_by_code={CODE: ()},
            memberships=(),
            risk_flags=(),
            coverage_by_date={},
            market_snapshots={},
            input_fingerprint="fixture-input-fingerprint",
        )

    def plan_on(signal_date: date, suffix: str):
        setup = replace(
            template.candidate.setup,
            analysis_date=signal_date,
            structure_start=signal_date - timedelta(days=10),
        )
        candidate = replace(
            template.candidate,
            signal_date=signal_date,
            setup=setup,
            valid_through_trade_date=signal_date + timedelta(days=2),
        )
        return replace(
            template,
            candidate=candidate,
            structure_id=f"structure-{suffix}",
        )

    plans = (plan_on(train_signal, "train"), plan_on(validation_signal, "val"))

    def discover(**kwargs):
        requested_discovery_dates.append(tuple(kwargs["signal_dates"]))
        return FiveDayDiscovery(
            signal_dates=tuple(kwargs["signal_dates"]),
            plans=plans,
            rejection_counts={},
            incomplete_dates=(),
        )

    def simulate(plan, bars, calendar, *, entry_blockers=None):
        del bars, calendar, entry_blockers
        exit_value = FiveDayExit(
            planned_exit_date=plan.candidate.signal_date + timedelta(days=5),
            actual_exit_date=plan.candidate.signal_date + timedelta(days=5),
            price=Decimal("10.20"),
            reason="TIME_EXIT_GAIN",
            fees=Decimal("0"),
            delayed=False,
        )
        return FiveDayTrade(
            profile_id=plan.profile.profile_id,
            structure_id=plan.structure_id,
            code=plan.candidate.code,
            signal_date=plan.candidate.signal_date,
            status="TIME_EXIT_GAIN",
            entry_date=plan.candidate.signal_date + timedelta(days=1),
            entry_price=Decimal("10"),
            stop_price=Decimal("9.70"),
            evaluation_target_notional=Decimal("10000"),
            evaluation_shares=1000,
            evaluation_notional=Decimal("10000"),
            entry_fees=Decimal("0"),
            exit=exit_value,
            net_pnl=Decimal("200"),
            net_return=Decimal("0.02"),
            mfe=Decimal("0.03"),
            mae=Decimal("0.01"),
            intraday_order_ambiguous=False,
            reasons=(),
        )

    review = build_five_day_research_review(
        signal_dates,
        input_loader=load,
        discovery_builder=discover,
        plan_simulator=simulate,
    )

    assert requested_discovery_dates == [
        (*review.split.train, *review.split.validation)
    ]
    assert tuple(
        value.plan.candidate.signal_date for value in review.observations
    ) == (train_signal, validation_signal)
    broad_key = (
        f"{template.profile.profile_id}|"
        f"{template.candidate.setup.setup_type.value}|*|*"
    )
    assert review.train_calibrations[broad_key].triggered_resolved == 1
    assert len(review.validation_metrics) == 4
    assert review.point_in_time_complete


def test_mysql_loader_normalizes_host_and_uses_only_bounded_read_adapters() -> None:
    signal_dates = tuple(
        date(2024, 1, 1) + timedelta(days=index) for index in range(630)
    )
    history_start = signal_dates[0] - timedelta(days=180)
    signal_end = signal_dates[503]
    outcome_cutoff = signal_dates[513]
    calls: list[tuple[object, ...]] = []
    engine = object()

    def engine_factory(url: str, **kwargs):
        calls.append(("engine", url, kwargs))
        return engine

    def trade_dates_loader(actual_engine, start: date, end: date):
        calls.append(("dates", actual_engine, start, end))
        return tuple(value for value in signal_dates if value <= end)

    def bars_loader(actual_engine, start: date, end: date):
        calls.append(("bars", actual_engine, start, end))
        return {}

    class Repository:
        def coverage_between(self, dates):
            calls.append(("coverage", tuple(dates)))
            return {}

        def memberships_between(self, start: date, end: date):
            calls.append(("memberships", start, end))
            return ()

        def risk_flags_between(self, start: date, end: date):
            calls.append(("risk", start, end))
            return ()

    def aggregate_loader(actual_engine, start: date, end: date):
        calls.append(("aggregates", actual_engine, start, end))
        return {}

    def benchmark_loader(start: date, end: date):
        calls.append(("benchmarks", start, end))
        return {}

    def market_builder(dates, bars, benchmarks, *, market_aggregates_by_date):
        calls.append(("markets", tuple(dates)))
        assert bars == benchmarks == market_aggregates_by_date == {}
        return {}

    inputs = load_mysql_five_day_inputs(
        signal_dates,
        history_start,
        signal_end,
        outcome_cutoff,
        mysql_url="mysql+pymysql://u:p@host.docker.internal:3306/stock",
        engine_factory=engine_factory,
        trade_dates_loader=trade_dates_loader,
        bars_loader=bars_loader,
        repository_factory=lambda actual_engine: Repository(),
        aggregate_loader=aggregate_loader,
        benchmark_loader=benchmark_loader,
        market_snapshot_builder=market_builder,
    )

    assert calls[0][1] == "mysql+pymysql://u:p@127.0.0.1:3306/stock"
    assert ("bars", engine, history_start, outcome_cutoff) in calls
    assert ("memberships", history_start, signal_end) in calls
    assert ("risk", signal_dates[0], outcome_cutoff) in calls
    assert inputs.signal_dates == signal_dates
    assert inputs.input_fingerprint


def _empty_test_lineage():
    signal_dates = tuple(
        date(2024, 1, 1) + timedelta(days=index) for index in range(630)
    )

    def load(
        requested_signal_dates: Sequence[date],
        history_start: date,
        signal_end: date,
        outcome_cutoff: date,
    ) -> FiveDayRuntimeInputs:
        del history_start, signal_end
        return FiveDayRuntimeInputs(
            signal_dates=tuple(requested_signal_dates),
            trading_dates=tuple(
                value for value in signal_dates if value <= outcome_cutoff
            ),
            bars_by_code={},
            memberships=(),
            risk_flags=(),
            coverage_by_date={},
            market_snapshots={},
            input_fingerprint="a" * 64,
        )

    def discover(**kwargs):
        return FiveDayDiscovery(
            signal_dates=tuple(kwargs["signal_dates"]),
            plans=(),
            rejection_counts={},
            incomplete_dates=(),
        )

    research = build_five_day_research_review(
        signal_dates,
        input_loader=load,
        discovery_builder=discover,
    )
    research_identity = five_day_research_payload(research)[
        "artifact_identity"
    ]
    freeze = evaluate_validation_freeze(
        research.observations,
        train_dates=research.split.train,
        validation_dates=research.split.validation,
        profile_matrix_hash=research.profile_matrix_hash,
        research_identity=research_identity,
    )
    test_inputs = FiveDayRuntimeInputs(
        signal_dates=research.split.test,
        trading_dates=research.split.test,
        bars_by_code={},
        memberships=(),
        risk_flags=(),
        coverage_by_date={},
        market_snapshots={},
        input_fingerprint=f"{research.input_fingerprint}:test-fixture",
    )
    return research, freeze, test_inputs, discover


def test_test_builder_requires_exact_frozen_test_dates() -> None:
    research, freeze, inputs, discover = _empty_test_lineage()

    review = build_five_day_test_review(
        freeze,
        research,
        inputs,
        discovery_builder=discover,
    )

    assert review.signal_dates == research.split.test
    assert review.freeze_hash == freeze.freeze_hash
    assert review.research_identity == freeze.research_identity
    assert review.observations == ()
    assert review.assessment.eligible_profile_ids == ()


def test_test_builder_ranks_with_serialized_frozen_calibrations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    research, freeze, inputs, discover = _empty_test_lineage()
    captured: list[object] = []

    def rank(plans, calibrations, **kwargs):
        captured.append((stack()[1].function, tuple(plans), calibrations, kwargs))
        return five_day_return_validation.FiveDayRanking((), {})

    monkeypatch.setattr(
        five_day_return_validation,
        "rank_five_day_plans",
        rank,
    )

    build_five_day_test_review(
        freeze,
        research,
        inputs,
        discovery_builder=discover,
    )

    assert (
        "build_five_day_test_review",
        (),
        freeze.calibrations,
        {},
    ) in captured


@pytest.mark.parametrize(
    "mutation",
    ("missing_freeze", "parent", "split", "extra", "missing", "fingerprint"),
)
def test_test_builder_rejects_lineage_or_date_membership_changes(
    mutation: str,
) -> None:
    research, freeze, inputs, discover = _empty_test_lineage()
    selected_freeze = freeze
    selected_research = research
    selected_inputs = inputs
    if mutation == "missing_freeze":
        selected_freeze = None
    elif mutation == "parent":
        selected_freeze = replace(freeze, research_identity="0" * 64)
    elif mutation == "split":
        selected_research = replace(
            research,
            split=ChronologicalSplit(
                research.split.train,
                research.split.validation,
                (
                    *research.split.test[:-1],
                    research.split.test[-1] + timedelta(days=1),
                ),
            ),
        )
    elif mutation == "extra":
        selected_inputs = replace(
            inputs,
            signal_dates=(
                *inputs.signal_dates,
                inputs.signal_dates[-1] + timedelta(days=1),
            ),
        )
    elif mutation == "missing":
        selected_inputs = replace(inputs, signal_dates=inputs.signal_dates[:-1])
    else:
        selected_inputs = replace(inputs, input_fingerprint="conflict")

    with pytest.raises(ValueError, match="frozen five-day test lineage"):
        build_five_day_test_review(
            selected_freeze,
            selected_research,
            selected_inputs,
            discovery_builder=discover,
        )


def _forward_inputs(
    test_review,
    signal_date: date,
    *,
    complete: bool = True,
) -> FiveDayRuntimeInputs:
    return FiveDayRuntimeInputs(
        signal_dates=(signal_date,),
        trading_dates=tuple(
            signal_date + timedelta(days=index) for index in range(8)
        ),
        bars_by_code={},
        memberships=(),
        risk_flags=(),
        coverage_by_date={
            signal_date: ReferenceCoverage(
                signal_date,
                complete,
                complete,
                complete,
            )
        },
        market_snapshots={
            signal_date: MarketSnapshot(3, 60.0, 1.0, complete)
        },
        input_fingerprint=f"{test_review.input_fingerprint}:forward-fixture",
    )


def test_forward_screen_allows_an_empty_eligible_profile_set() -> None:
    research, freeze, inputs, discover_test = _empty_test_lineage()
    test_review = build_five_day_test_review(
        freeze,
        research,
        inputs,
        discovery_builder=discover_test,
    )
    signal_date = research.split.test[-1] + timedelta(days=1)

    def discover_forward(**kwargs):
        return FiveDayDiscovery(
            signal_dates=tuple(kwargs["signal_dates"]),
            plans=(),
            rejection_counts={},
            incomplete_dates=(),
        )

    screen = build_five_day_forward_screen(
        freeze,
        test_review,
        signal_date,
        _forward_inputs(test_review, signal_date),
        discovery_builder=discover_forward,
    )

    assert screen.signal_date == signal_date
    assert screen.freeze_hash == freeze.freeze_hash
    assert screen.test_identity == five_day_test_payload(test_review)[
        "artifact_identity"
    ]
    assert screen.candidates == ()
    assert screen.risk_coverage_complete


def test_forward_screen_uses_only_eligible_profiles_and_keeps_top_three(
    tmp_path,
) -> None:
    from tests.unit.test_five_day_return_report import (
        _observation as report_observation,
        _test_lineage as report_test_lineage,
    )

    research, freeze, test_review, _, _ = report_test_lineage(tmp_path)
    signal_date = research.split.test[-1] + timedelta(days=1)
    plans = []
    for index in range(4):
        template = report_observation(
            signal_date,
            400 + index,
            net_return=Decimal("0.01"),
        ).plan
        plans.append(template)

    def discover_forward(**kwargs):
        return FiveDayDiscovery(
            signal_dates=tuple(kwargs["signal_dates"]),
            plans=tuple(reversed(plans)),
            rejection_counts={},
            incomplete_dates=(),
        )

    screen = build_five_day_forward_screen(
        freeze,
        test_review,
        signal_date,
        _forward_inputs(test_review, signal_date),
        discovery_builder=discover_forward,
    )

    assert len(screen.candidates) == 3
    assert tuple(value.candidate.code for value in screen.candidates) == (
        "600400",
        "600401",
        "600402",
    )
    assert {
        value.profile.profile_id for value in screen.candidates
    } == set(test_review.assessment.eligible_profile_ids)


@pytest.mark.parametrize(
    "mutation",
    ("test_date", "extra_date", "missing_date", "coverage", "fingerprint"),
)
def test_forward_screen_rejects_invalid_date_or_point_in_time_inputs(
    mutation: str,
) -> None:
    research, freeze, inputs, discover_test = _empty_test_lineage()
    test_review = build_five_day_test_review(
        freeze,
        research,
        inputs,
        discovery_builder=discover_test,
    )
    signal_date = research.split.test[-1] + timedelta(days=1)
    selected_date = (
        research.split.test[-1] if mutation == "test_date" else signal_date
    )
    forward_inputs = _forward_inputs(
        test_review,
        selected_date,
        complete=mutation != "coverage",
    )
    if mutation == "extra_date":
        forward_inputs = replace(
            forward_inputs,
            signal_dates=(selected_date, selected_date + timedelta(days=1)),
        )
    elif mutation == "missing_date":
        forward_inputs = replace(forward_inputs, signal_dates=())
    elif mutation == "fingerprint":
        forward_inputs = replace(
            forward_inputs,
            input_fingerprint="conflict",
        )

    with pytest.raises(ValueError, match="five-day forward screen"):
        build_five_day_forward_screen(
            freeze,
            test_review,
            selected_date,
            forward_inputs,
            discovery_builder=lambda **kwargs: FiveDayDiscovery(
                tuple(kwargs["signal_dates"]), (), {}, ()
            ),
        )


def _settlement_inputs(
    screen: FiveDayForwardScreen,
    outcome_cutoff: date,
) -> FiveDayRuntimeInputs:
    trading_dates = tuple(
        screen.signal_date + timedelta(days=index)
        for index in range((outcome_cutoff - screen.signal_date).days + 1)
    )
    bars_by_code = {}
    for plan in screen.candidates:
        bars_by_code[plan.candidate.code] = tuple(
            BuyPointBar(
                trade_date=trade_date,
                open=Decimal("10.00"),
                high=(
                    Decimal("10.00")
                    if trade_date == screen.signal_date + timedelta(days=1)
                    else Decimal("10.30")
                ),
                low=Decimal("9.90"),
                close=Decimal("10.20"),
                pct_chg=Decimal("0"),
                amount_qian=Decimal("200000"),
            )
            for trade_date in trading_dates
            if trade_date > screen.signal_date
        )
    return FiveDayRuntimeInputs(
        signal_dates=(screen.signal_date,),
        trading_dates=trading_dates,
        bars_by_code=bars_by_code,
        memberships=(),
        risk_flags=(),
        coverage_by_date={
            value: ReferenceCoverage(value, True, True, True)
            for value in trading_dates
        },
        market_snapshots={
            value: MarketSnapshot(3, 60.0, 1.0, True)
            for value in trading_dates
        },
        input_fingerprint=f"{screen.input_fingerprint}:settlement-fixture",
    )


def test_forward_settlement_requires_second_day_entry_plus_four_sessions(
    tmp_path,
) -> None:
    from tests.unit.test_five_day_return_report import (
        _forward_screen_lineage,
    )

    original = _forward_screen_lineage(tmp_path)[0]
    screen = replace(original, candidates=original.candidates[:1])
    complete_cutoff = screen.signal_date + timedelta(days=6)
    short_cutoff = complete_cutoff - timedelta(days=1)

    with pytest.raises(ValueError, match="five-day forward settlement"):
        build_five_day_forward_settlement(
            screen,
            _settlement_inputs(screen, short_cutoff),
            short_cutoff,
        )

    settlement = build_five_day_forward_settlement(
        screen,
        _settlement_inputs(screen, complete_cutoff),
        complete_cutoff,
    )

    assert settlement.outcome_cutoff == complete_cutoff
    assert settlement.outcomes[0].trade.entry_date == (
        screen.signal_date + timedelta(days=2)
    )
    assert settlement.outcomes[0].trade.exit.actual_exit_date == complete_cutoff
    assert settlement.candidates == screen.candidates


def test_forward_settlement_rejects_simulator_membership_changes(
    tmp_path,
) -> None:
    from tests.unit.test_five_day_return_report import (
        _forward_screen_lineage,
    )

    original = _forward_screen_lineage(tmp_path)[0]
    screen = replace(original, candidates=original.candidates[:1])
    cutoff = screen.signal_date + timedelta(days=6)

    def simulate_wrong_member(plan, bars, calendar, *, entry_blockers=None):
        return simulate_five_day_plan(
            replace(plan, structure_id="forged-structure"),
            bars,
            calendar,
            entry_blockers=entry_blockers,
        )

    with pytest.raises(ValueError, match="membership"):
        build_five_day_forward_settlement(
            screen,
            _settlement_inputs(screen, cutoff),
            cutoff,
            plan_simulator=simulate_wrong_member,
        )
