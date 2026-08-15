from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest

from stock_ai.buy_point_selection.five_day_return_execution import (
    COST_VERSION,
    EVALUATOR_VERSION,
    FiveDayExit,
    FiveDayTrade,
)
from stock_ai.buy_point_selection.five_day_return_profiles import (
    SIZING_VERSION,
    build_five_day_return_profiles,
    five_day_profile_hash,
)
from stock_ai.buy_point_selection.five_day_return_report import (
    five_day_forward_screen_payload,
    five_day_forward_settlement_payload,
    five_day_freeze_payload,
    five_day_research_payload,
    five_day_test_payload,
    load_five_day_forward_screen,
    load_five_day_forward_settlement,
    load_five_day_freeze,
    load_five_day_research,
    load_five_day_test,
    write_five_day_freeze,
    write_five_day_forward_screen,
    write_five_day_forward_settlement,
    write_five_day_research,
    write_five_day_test_once,
)
from stock_ai.buy_point_selection.five_day_return_runtime import (
    FiveDayForwardScreen,
    FiveDayForwardSettlement,
    FiveDayResearchReview,
    FiveDaySignalCandidate,
    FiveDaySignalPlan,
    FiveDayTestReview,
)
from stock_ai.buy_point_selection.five_day_return_validation import (
    FiveDayObservation,
    _resolved_count,
    _segment_metrics_from_observations,
    build_five_day_calibrations,
    build_five_day_portfolio_metrics,
    evaluate_frozen_test,
    evaluate_validation_freeze,
)
from stock_ai.buy_point_selection.models import (
    DetectedSetup,
    SelectionPolicy,
    SetupType,
)
from stock_ai.buy_point_selection.validation import (
    chronological_split,
    policy_hash,
)


START = date(2024, 1, 1)
PROFILE = "BREAKOUT_TRIGGER__FIXED_3_PERCENT"


def _dates() -> tuple[date, ...]:
    return tuple(START + timedelta(days=index) for index in range(630))


def _observation(
    signal_date: date,
    index: int,
    *,
    net_return: Decimal,
) -> FiveDayObservation:
    profile = build_five_day_return_profiles()[0]
    code = f"{600000 + index:06d}"
    setup = DetectedSetup(
        code=code,
        setup_type=SetupType.PRE_BREAKOUT,
        analysis_date=signal_date,
        structure_start=signal_date - timedelta(days=10),
        structure_high=Decimal("10.00"),
        structure_low=Decimal("9.50"),
        quality=Decimal("0.80"),
        reasons=("FIXTURE",),
        metrics={"width": Decimal("0.05")},
    )
    candidate = FiveDaySignalCandidate(
        code=code,
        signal_date=signal_date,
        setup=setup,
        market_status="ALLOW",
        sector_code=f"80{index % 3 + 1:04d}",
        sector_resonating=True,
        anti_chase_passed=True,
        average_amount5_qian=Decimal("200000"),
        valid_through_trade_date=signal_date + timedelta(days=2),
    )
    plan = FiveDaySignalPlan(
        candidate=candidate,
        profile=profile,
        structure_id=f"structure-{index}",
        signal_close=Decimal("10.00"),
        breakout_trigger=Decimal("10.01"),
        structure_stop=Decimal("9.50"),
        reference_entry=Decimal("10.01"),
        resistance_basis="NO_RELIABLE_LEVEL",
        resistance_effective_r=None,
    )
    exit_value = FiveDayExit(
        planned_exit_date=signal_date + timedelta(days=6),
        actual_exit_date=signal_date + timedelta(days=6),
        price=Decimal("10.10"),
        reason=("TIME_EXIT_GAIN" if net_return > 0 else "TIME_EXIT_LOSS"),
        fees=Decimal("10"),
        delayed=False,
    )
    trade = FiveDayTrade(
        profile_id=profile.profile_id,
        structure_id=plan.structure_id,
        code=code,
        signal_date=signal_date,
        status=("TIME_EXIT_GAIN" if net_return > 0 else "TIME_EXIT_LOSS"),
        entry_date=signal_date + timedelta(days=1),
        entry_price=Decimal("10.00"),
        stop_price=Decimal("9.70"),
        evaluation_target_notional=Decimal("10000"),
        evaluation_shares=1000,
        evaluation_notional=Decimal("10000"),
        entry_fees=Decimal("10"),
        exit=exit_value,
        net_pnl=net_return * Decimal("10000"),
        net_return=net_return,
        mfe=Decimal("0.03"),
        mae=Decimal("0.01"),
        intraday_order_ambiguous=False,
        reasons=(),
    )
    return FiveDayObservation(plan, trade, exit_value.actual_exit_date)


def _segment_observations(
    sessions: tuple[date, ...], count: int, offset: int
) -> tuple[FiveDayObservation, ...]:
    step = max(1, (len(sessions) - 7) // count)
    return tuple(
        _observation(
            sessions[index * step],
            offset + index,
            net_return=(
                Decimal("0.01")
                if index % 10 < 7
                else Decimal("-0.005")
            ),
        )
        for index in range(count)
    )


def _review() -> FiveDayResearchReview:
    split = chronological_split(_dates())
    train = _segment_observations(split.train, 40, 0)
    validation = _segment_observations(split.validation, 30, 100)
    observations = (*train, *validation)
    train_calibrations = build_five_day_calibrations(
        train, trading_dates=split.train
    )
    metrics = tuple(
        _segment_metrics_from_observations(
            profile_id=profile.profile_id,
            segment="validation",
            observations=validation,
            trading_dates=split.validation,
            ranking_calibrations=train_calibrations,
            cumulative_samples=_resolved_count(
                observations,
                profile.profile_id,
                data_end=split.validation[-1],
            ),
            required_cumulative_samples=70,
        )
        for profile in build_five_day_return_profiles()
    )
    qualified = frozenset(value.profile_id for value in metrics if value.qualifies)
    combined = tuple(
        value
        for value in validation
        if value.plan.profile.profile_id in qualified
    )
    portfolio = build_five_day_portfolio_metrics(
        tuple(value.plan for value in combined),
        combined,
        train_calibrations,
    )
    policy = SelectionPolicy()
    return FiveDayResearchReview(
        split=split,
        input_fingerprint="f" * 64,
        formal_rule_version=policy.rule_version,
        formal_policy_hash=policy_hash(policy),
        profile_matrix_hash=five_day_profile_hash(
            build_five_day_return_profiles()
        ),
        sizing_version=SIZING_VERSION,
        evaluator_version=EVALUATOR_VERSION,
        cost_version=COST_VERSION,
        observations=observations,
        train_calibrations=train_calibrations,
        validation_metrics=metrics,
        validation_portfolio=portfolio,
        point_in_time_complete=True,
        test_outcomes_read=False,
    )


def _executable_share_values(value: object) -> list[object]:
    found: list[object] = []
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            found.extend(
                child
                for key, child in item.items()
                if key == "executable_shares"
            )
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return found


def test_research_payload_is_canonical_safe_and_contains_no_test_results() -> None:
    review = _review()
    payload = five_day_research_payload(review)

    assert payload["schema"] == "buy-point-five-day-return-shadow-v1"
    assert payload["stage"] == "research"
    assert payload["status"] == "CASE_ANALYSIS_ONLY"
    assert payload["trade_permission"] == "NO-TRADE"
    assert payload["retrospective"] is True
    assert payload["promotion_eligible"] is False
    assert payload["split"]["train"]["count"] == 378
    assert payload["split"]["validation"]["count"] == 126
    assert payload["split"]["test"]["count"] == 126
    assert payload["split"]["test"]["dates"][-1] == _dates()[-1].isoformat()
    assert payload["test_outcomes_read"] is False
    assert len(payload["observations"]) == 70
    assert all(
        row["plan"]["candidate"]["signal_date"]
        not in payload["split"]["test"]["dates"]
        for row in payload["observations"]
    )
    assert _executable_share_values(payload)
    assert set(_executable_share_values(payload)) == {0}
    assert "test_candidates" not in payload
    assert "test_trades" not in payload
    assert "test_metrics" not in payload
    assert "test_calibrations" not in payload
    assert len(payload["artifact_identity"]) == 64
    assert len(payload["content_revision"]) == 64


def test_research_writer_is_exclusive_and_loader_recomputes_raw_rows(
    tmp_path: Path,
) -> None:
    review = _review()
    path = write_five_day_research(review, tmp_path)

    assert write_five_day_research(review, tmp_path) == path
    loaded = load_five_day_research(path)
    assert loaded == review

    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="immutable artifact content mismatch"):
        write_five_day_research(review, tmp_path)


@pytest.mark.parametrize(
    "mutation",
    ("net_return", "profile", "split", "shares"),
)
def test_research_loader_rejects_tampering(
    tmp_path: Path, mutation: str
) -> None:
    payload = five_day_research_payload(_review())
    if mutation == "net_return":
        payload["observations"][0]["trade"]["net_return"] = "0.99"
    elif mutation == "profile":
        payload["observations"][0]["plan"]["profile"]["profile_id"] = "FORGED"
    elif mutation == "split":
        payload["split"]["validation"]["dates"][0] = "2020-01-01"
    else:
        payload["observations"][0]["trade"]["executable_shares"] = 100
    path = tmp_path / f"tampered-{mutation}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="five-day research artifact"):
        load_five_day_research(path)


def test_freeze_round_trip_recomputes_research_and_preserves_parent_identity(
    tmp_path: Path,
) -> None:
    review = _review()
    research_path = write_five_day_research(review, tmp_path)
    research_identity = five_day_research_payload(review)["artifact_identity"]
    freeze = evaluate_validation_freeze(
        review.observations,
        train_dates=review.split.train,
        validation_dates=review.split.validation,
        profile_matrix_hash=review.profile_matrix_hash,
        research_identity=research_identity,
    )

    payload = five_day_freeze_payload(freeze)
    freeze_path = write_five_day_freeze(freeze, tmp_path)

    assert not freeze.empty
    assert [value["profile_id"] for value in payload["profiles"]] == [PROFILE]
    assert payload["parent_research_identity"] == research_identity
    assert load_five_day_freeze(freeze_path, research_path) == freeze


def test_empty_freeze_is_a_valid_recomputed_artifact(tmp_path: Path) -> None:
    review = _review()
    empty_calibrations = build_five_day_calibrations(
        (), trading_dates=review.split.train
    )
    empty_metrics = tuple(
        _segment_metrics_from_observations(
            profile_id=profile.profile_id,
            segment="validation",
            observations=(),
            trading_dates=review.split.validation,
            ranking_calibrations=empty_calibrations,
            cumulative_samples=0,
            required_cumulative_samples=70,
        )
        for profile in build_five_day_return_profiles()
    )
    empty_portfolio = build_five_day_portfolio_metrics((), (), {})
    empty_review = replace(
        review,
        observations=(),
        train_calibrations=empty_calibrations,
        validation_metrics=empty_metrics,
        validation_portfolio=empty_portfolio,
    )
    research_path = write_five_day_research(empty_review, tmp_path)
    research_identity = five_day_research_payload(empty_review)[
        "artifact_identity"
    ]
    freeze = evaluate_validation_freeze(
        (),
        train_dates=empty_review.split.train,
        validation_dates=empty_review.split.validation,
        profile_matrix_hash=empty_review.profile_matrix_hash,
        research_identity=research_identity,
    )
    freeze_path = write_five_day_freeze(freeze, tmp_path)

    assert freeze.empty
    assert five_day_freeze_payload(freeze)["profiles"] == []
    assert load_five_day_freeze(freeze_path, research_path) == freeze


def test_freeze_loader_rejects_an_incomplete_point_in_time_parent(
    tmp_path: Path,
) -> None:
    review = replace(_review(), point_in_time_complete=False)
    research_path = write_five_day_research(review, tmp_path)
    research_identity = five_day_research_payload(review)["artifact_identity"]
    freeze = evaluate_validation_freeze(
        review.observations,
        train_dates=review.split.train,
        validation_dates=review.split.validation,
        profile_matrix_hash=review.profile_matrix_hash,
        research_identity=research_identity,
    )
    freeze_path = write_five_day_freeze(freeze, tmp_path)

    with pytest.raises(ValueError, match="five-day freeze artifact"):
        load_five_day_freeze(freeze_path, research_path)


@pytest.mark.parametrize(
    "mutation",
    ("metric", "samples", "rank", "version", "parent", "shares"),
)
def test_freeze_loader_rejects_tampering(
    tmp_path: Path, mutation: str
) -> None:
    review = _review()
    research_path = write_five_day_research(review, tmp_path)
    research_identity = five_day_research_payload(review)["artifact_identity"]
    freeze = evaluate_validation_freeze(
        review.observations,
        train_dates=review.split.train,
        validation_dates=review.split.validation,
        profile_matrix_hash=review.profile_matrix_hash,
        research_identity=research_identity,
    )
    payload = five_day_freeze_payload(freeze)
    if mutation == "metric":
        payload["profiles"][0]["validation_metrics"]["net_expectancy"] = "9"
    elif mutation == "samples":
        payload["profiles"][0]["train_validation_samples"] = 999
    elif mutation == "rank":
        payload["profiles"][0]["rank"] = 2
    elif mutation == "version":
        payload["evaluator_version"] = "forged"
    elif mutation == "parent":
        payload["parent_research_identity"] = "0" * 64
    else:
        payload["executable_shares"] = 100
    path = tmp_path / f"freeze-tampered-{mutation}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="five-day freeze artifact"):
        load_five_day_freeze(path, research_path)


def _test_lineage(tmp_path: Path):
    review = _review()
    research_path = write_five_day_research(review, tmp_path)
    research_identity = str(
        five_day_research_payload(review)["artifact_identity"]
    )
    freeze = evaluate_validation_freeze(
        review.observations,
        train_dates=review.split.train,
        validation_dates=review.split.validation,
        profile_matrix_hash=review.profile_matrix_hash,
        research_identity=research_identity,
    )
    freeze_path = write_five_day_freeze(freeze, tmp_path)
    observations = _segment_observations(review.split.test, 30, 200)
    assessment = evaluate_frozen_test(
        freeze,
        observations,
        test_dates=review.split.test,
    )
    test_review = FiveDayTestReview(
        signal_dates=review.split.test,
        research_identity=research_identity,
        freeze_hash=freeze.freeze_hash,
        input_fingerprint=f"{review.input_fingerprint}:test-fixture",
        observations=observations,
        assessment=assessment,
        sizing_version=freeze.sizing_version,
        evaluator_version=freeze.evaluator_version,
        cost_version=freeze.cost_version,
    )
    return review, freeze, test_review, research_path, freeze_path


def test_test_payload_is_canonical_safe_and_records_final_eligibility(
    tmp_path: Path,
) -> None:
    _, _, review, _, _ = _test_lineage(tmp_path)

    payload = five_day_test_payload(review)

    assert payload["schema"] == "buy-point-five-day-return-shadow-v1"
    assert payload["stage"] == "test"
    assert payload["status"] == "CASE_ANALYSIS_ONLY"
    assert payload["trade_permission"] == "NO-TRADE"
    assert payload["retrospective"] is True
    assert payload["promotion_eligible"] is False
    assert payload["test_consumed"] is True
    assert payload["parent_research_identity"] == review.research_identity
    assert payload["parent_freeze_hash"] == review.freeze_hash
    assert payload["signal_dates"]["count"] == 126
    assert len(payload["observations"]) == 30
    assert payload["forward_eligible_profile_ids"] == [PROFILE]
    assert payload["profile_metrics"][0]["segment"] == "test"
    assert payload["portfolio_metrics"]["qualifies"] is True
    assert _executable_share_values(payload)
    assert set(_executable_share_values(payload)) == {0}
    assert len(payload["artifact_identity"]) == 64
    assert len(payload["content_revision"]) == 64


def test_test_writer_consumes_each_freeze_identity_only_once(
    tmp_path: Path,
) -> None:
    _, _, review, _, _ = _test_lineage(tmp_path)

    path = write_five_day_test_once(review, tmp_path)

    assert path.exists()
    with pytest.raises(ValueError, match="test already exists"):
        write_five_day_test_once(review, tmp_path)


def test_test_loader_recomputes_frozen_metrics_and_parent_lineage(
    tmp_path: Path,
) -> None:
    _, _, review, research_path, freeze_path = _test_lineage(tmp_path)
    test_path = write_five_day_test_once(review, tmp_path)

    assert load_five_day_test(test_path, freeze_path, research_path) == review


@pytest.mark.parametrize(
    "mutation",
    (
        "freeze",
        "outcome",
        "summary",
        "eligibility",
        "version",
        "shares",
        "research",
    ),
)
def test_test_loader_rejects_tampering(
    tmp_path: Path, mutation: str
) -> None:
    _, _, review, research_path, freeze_path = _test_lineage(tmp_path)
    payload = five_day_test_payload(review)
    if mutation == "freeze":
        payload["parent_freeze_hash"] = "0" * 64
    elif mutation == "outcome":
        payload["observations"][0]["trade"]["net_return"] = "0.99"
    elif mutation == "summary":
        payload["profile_metrics"][0]["net_expectancy"] = "9"
    elif mutation == "eligibility":
        payload["forward_eligible_profile_ids"] = []
    elif mutation == "version":
        payload["cost_version"] = "forged"
    elif mutation == "shares":
        payload["observations"][0]["plan"]["executable_shares"] = 100
    else:
        payload["parent_research_identity"] = "0" * 64
    path = tmp_path / f"test-tampered-{mutation}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="five-day test artifact"):
        load_five_day_test(path, freeze_path, research_path)


def _forward_screen_lineage(tmp_path: Path):
    review, freeze, test_review, research_path, freeze_path = _test_lineage(
        tmp_path
    )
    test_path = write_five_day_test_once(test_review, tmp_path)
    signal_date = review.split.test[-1] + timedelta(days=1)
    candidates = tuple(
        _observation(
            signal_date,
            400 + index,
            net_return=Decimal("0.01"),
        ).plan
        for index in range(3)
    )
    screen = FiveDayForwardScreen(
        signal_date=signal_date,
        freeze_hash=freeze.freeze_hash,
        test_identity=str(
            five_day_test_payload(test_review)["artifact_identity"]
        ),
        input_fingerprint=f"{test_review.input_fingerprint}:forward-fixture",
        candidates=candidates,
        risk_coverage_complete=True,
    )
    return screen, research_path, freeze_path, test_path


def _recursive_keys(value: object) -> set[str]:
    keys: set[str] = set()
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            keys.update(str(key) for key in item)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return keys


def test_forward_screen_payload_contains_candidates_but_no_outcomes(
    tmp_path: Path,
) -> None:
    screen, _, _, _ = _forward_screen_lineage(tmp_path)

    payload = five_day_forward_screen_payload(screen)

    assert payload["stage"] == "forward-screen"
    assert payload["status"] == "CASE_ANALYSIS_ONLY"
    assert payload["trade_permission"] == "NO-TRADE"
    assert len(payload["candidates"]) == 3
    assert tuple(
        value["candidate"]["code"] for value in payload["candidates"]
    ) == ("600400", "600401", "600402")
    assert "outcomes" not in payload
    assert {
        "entry_date",
        "exit",
        "net_return",
        "net_pnl",
    }.isdisjoint(_recursive_keys(payload))
    assert set(_executable_share_values(payload)) == {0}
    assert len(payload["artifact_identity"]) == 64


def test_forward_screen_writer_preserves_old_content_on_changed_rerun(
    tmp_path: Path,
) -> None:
    screen, _, _, _ = _forward_screen_lineage(tmp_path)
    first = write_five_day_forward_screen(screen, tmp_path)
    original = first.read_bytes()

    assert write_five_day_forward_screen(screen, tmp_path) == first
    changed = write_five_day_forward_screen(
        replace(screen, candidates=screen.candidates[:-1]),
        tmp_path,
    )

    assert changed != first
    assert first.read_bytes() == original


def test_forward_screen_loader_validates_parent_and_frozen_order(
    tmp_path: Path,
) -> None:
    screen, research_path, freeze_path, test_path = _forward_screen_lineage(
        tmp_path
    )
    path = write_five_day_forward_screen(screen, tmp_path)

    loaded = load_five_day_forward_screen(
        path,
        freeze_path,
        test_path,
        research_path,
    )

    assert loaded == screen


@pytest.mark.parametrize(
    "mutation",
    ("order", "shares", "test", "freeze", "date", "coverage"),
)
def test_forward_screen_loader_rejects_tampering(
    tmp_path: Path,
    mutation: str,
) -> None:
    screen, research_path, freeze_path, test_path = _forward_screen_lineage(
        tmp_path
    )
    payload = five_day_forward_screen_payload(screen)
    if mutation == "order":
        payload["candidates"][0], payload["candidates"][1] = (
            payload["candidates"][1],
            payload["candidates"][0],
        )
    elif mutation == "shares":
        payload["candidates"][0]["executable_shares"] = 100
    elif mutation == "test":
        payload["parent_test_identity"] = "0" * 64
    elif mutation == "freeze":
        payload["parent_freeze_hash"] = "0" * 64
    elif mutation == "date":
        payload["signal_date"] = "2020-01-01"
    else:
        payload["risk_coverage_complete"] = False
    path = tmp_path / f"forward-screen-tampered-{mutation}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="five-day forward screen artifact"):
        load_five_day_forward_screen(
            path,
            freeze_path,
            test_path,
            research_path,
        )


def _forward_settlement_lineage(tmp_path: Path):
    screen, research_path, freeze_path, test_path = _forward_screen_lineage(
        tmp_path
    )
    screen_path = write_five_day_forward_screen(screen, tmp_path)
    outcomes = tuple(
        _observation(
            screen.signal_date,
            400 + index,
            net_return=(
                Decimal("0.01")
                if index < 2
                else Decimal("-0.005")
            ),
        )
        for index in range(3)
    )
    settlement = FiveDayForwardSettlement(
        parent_screen_identity=str(
            five_day_forward_screen_payload(screen)["artifact_identity"]
        ),
        signal_date=screen.signal_date,
        outcome_cutoff=screen.signal_date + timedelta(days=6),
        freeze_hash=screen.freeze_hash,
        test_identity=screen.test_identity,
        input_fingerprint=f"{screen.input_fingerprint}:settlement-fixture",
        candidates=screen.candidates,
        outcomes=outcomes,
        risk_coverage_complete=True,
    )
    return (
        settlement,
        screen_path,
        research_path,
        freeze_path,
        test_path,
    )


def test_forward_settlement_payload_preserves_exact_screen_membership(
    tmp_path: Path,
) -> None:
    settlement, _, _, _, _ = _forward_settlement_lineage(tmp_path)

    payload = five_day_forward_settlement_payload(settlement)

    assert payload["stage"] == "forward-settlement"
    assert payload["parent_screen_identity"] == (
        settlement.parent_screen_identity
    )
    assert len(payload["candidates"]) == len(payload["outcomes"]) == 3
    assert tuple(
        value["structure_id"] for value in payload["candidates"]
    ) == tuple(
        value["plan"]["structure_id"] for value in payload["outcomes"]
    )
    assert set(_executable_share_values(payload)) == {0}
    assert all(
        value["trade"]["status"] != "PENDING"
        for value in payload["outcomes"]
    )


@pytest.mark.parametrize("mutation", ("status", "member"))
def test_forward_settlement_payload_rejects_forged_terminal_rows(
    tmp_path: Path,
    mutation: str,
) -> None:
    settlement, _, _, _, _ = _forward_settlement_lineage(tmp_path)
    first = settlement.outcomes[0]
    changed_trade = (
        replace(first.trade, status="FORGED_TERMINAL")
        if mutation == "status"
        else replace(first.trade, structure_id="forged-structure")
    )
    changed = replace(
        settlement,
        outcomes=(
            replace(first, trade=changed_trade),
            *settlement.outcomes[1:],
        ),
    )

    with pytest.raises(ValueError, match="settlement safety"):
        five_day_forward_settlement_payload(changed)


def test_forward_settlement_never_rewrites_screen_and_is_single_content(
    tmp_path: Path,
) -> None:
    settlement, screen_path, _, _, _ = _forward_settlement_lineage(tmp_path)
    before = hashlib.sha256(screen_path.read_bytes()).hexdigest()

    path = write_five_day_forward_settlement(settlement, tmp_path)

    assert write_five_day_forward_settlement(settlement, tmp_path) == path
    assert hashlib.sha256(screen_path.read_bytes()).hexdigest() == before
    with pytest.raises(ValueError, match="immutable artifact content mismatch"):
        write_five_day_forward_settlement(
            replace(
                settlement,
                input_fingerprint=f"{settlement.input_fingerprint}:changed",
            ),
            tmp_path,
        )


def test_forward_settlement_loader_validates_screen_and_outcome_membership(
    tmp_path: Path,
) -> None:
    settlement, screen_path, research_path, freeze_path, test_path = (
        _forward_settlement_lineage(tmp_path)
    )
    path = write_five_day_forward_settlement(settlement, tmp_path)

    loaded = load_five_day_forward_settlement(
        path,
        screen_path,
        freeze_path,
        test_path,
        research_path,
    )

    assert loaded == settlement


@pytest.mark.parametrize(
    "mutation",
    (
        "parent",
        "candidate_order",
        "outcome_order",
        "member",
        "pending",
        "return",
        "shares",
        "freeze",
        "test",
        "cutoff",
    ),
)
def test_forward_settlement_loader_rejects_tampering(
    tmp_path: Path,
    mutation: str,
) -> None:
    settlement, screen_path, research_path, freeze_path, test_path = (
        _forward_settlement_lineage(tmp_path)
    )
    payload = five_day_forward_settlement_payload(settlement)
    if mutation == "parent":
        payload["parent_screen_identity"] = "0" * 64
    elif mutation == "candidate_order":
        payload["candidates"][0], payload["candidates"][1] = (
            payload["candidates"][1],
            payload["candidates"][0],
        )
    elif mutation == "outcome_order":
        payload["outcomes"][0], payload["outcomes"][1] = (
            payload["outcomes"][1],
            payload["outcomes"][0],
        )
    elif mutation == "member":
        payload["outcomes"][0]["plan"]["structure_id"] = "forged"
    elif mutation == "pending":
        payload["outcomes"][0]["trade"]["status"] = "PENDING"
    elif mutation == "return":
        payload["outcomes"][0]["trade"]["net_return"] = "0.99"
    elif mutation == "shares":
        payload["outcomes"][0]["trade"]["executable_shares"] = 100
    elif mutation == "freeze":
        payload["parent_freeze_hash"] = "0" * 64
    elif mutation == "test":
        payload["parent_test_identity"] = "0" * 64
    else:
        payload["outcome_cutoff"] = settlement.signal_date.isoformat()
    path = tmp_path / f"forward-settlement-tampered-{mutation}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="five-day forward settlement artifact",
    ):
        load_five_day_forward_settlement(
            path,
            screen_path,
            freeze_path,
            test_path,
            research_path,
        )
