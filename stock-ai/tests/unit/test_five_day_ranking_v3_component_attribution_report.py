from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3 import V3_POLICY_IDS
from stock_ai.buy_point_selection.five_day_ranking_v3_attribution import (
    wilson_interval,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_component_attribution import (
    AblationDelta,
    ComponentCorrelationAuditTotals,
    ComponentCorrelationMetrics,
    ComponentCorrelationReview,
    CoverageComparison,
    FiveDayRankingV3ComponentAttributionReview,
    FoldExperimentReview,
    PolicyComponentEffect,
    RankMetricAuditTotals,
    RobustRankMetrics,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_component_attribution_report import (
    five_day_ranking_v3_component_attribution_payload,
    load_five_day_ranking_v3_component_attribution,
    write_five_day_ranking_v3_component_attribution,
)


FOLDS = ("train-fold-1", "train-fold-2")
EXPERIMENTS = (
    "BASELINE",
    "WITHOUT_CONSISTENCY",
    "WITHOUT_STRUCTURE",
    "WITHOUT_DOWNSIDE",
)
COMPONENTS = ("EDGE", "CONSISTENCY", "STRUCTURE", "DOWNSIDE")


def _metrics() -> RobustRankMetrics:
    return RobustRankMetrics(
        candidate_rows=150,
        boundary_ties=0,
        paired_dates=30,
        correlation_eligible_dates=30,
        correlation_dates=30,
        audit=RankMetricAuditTotals(
            raw_difference_sum=Decimal("0.30"),
            index_excess_difference_sum=Decimal("0.30"),
            market_excess_difference_sum=Decimal("0.30"),
            rank_one_win_dates=15,
            raw_correlation_sum=Decimal("15"),
            index_excess_correlation_sum=Decimal("15"),
            market_excess_correlation_sum=Decimal("15"),
        ),
        mean_raw_difference=Decimal("0.01"),
        median_raw_difference=Decimal("0.01"),
        mean_index_excess_difference=Decimal("0.01"),
        median_index_excess_difference=Decimal("0.01"),
        mean_market_excess_difference=Decimal("0.01"),
        median_market_excess_difference=Decimal("0.01"),
        rank_one_win_ratio=Decimal("0.5"),
        rank_one_win_interval=wilson_interval(15, 30),
        mean_raw_correlation=Decimal("0.5"),
        median_raw_correlation=Decimal("0.5"),
        mean_index_excess_correlation=Decimal("0.5"),
        median_index_excess_correlation=Decimal("0.5"),
        mean_market_excess_correlation=Decimal("0.5"),
        median_market_excess_correlation=Decimal("0.5"),
    )


def _correlations() -> tuple[ComponentCorrelationMetrics, ...]:
    return tuple(
        ComponentCorrelationMetrics(
            component_id=component_id,
            eligible_dates=30,
            completed_dates=30,
            audit=ComponentCorrelationAuditTotals(
                raw_correlation_sum=Decimal("15"),
                index_excess_correlation_sum=Decimal("15"),
                market_excess_correlation_sum=Decimal("15"),
            ),
            mean_raw_correlation=Decimal("0.5"),
            median_raw_correlation=Decimal("0.5"),
            mean_index_excess_correlation=Decimal("0.5"),
            median_index_excess_correlation=Decimal("0.5"),
            mean_market_excess_correlation=Decimal("0.5"),
            median_market_excess_correlation=Decimal("0.5"),
        )
        for component_id in COMPONENTS
    )


def _coverage(fold_id: str, policy_id: str) -> CoverageComparison:
    return CoverageComparison(
        candidate_rows=150 if fold_id != "train-combined" else 300,
        eligible_outcomes=150 if fold_id != "train-combined" else 300,
        excluded_without_train_horizon=0,
        excluded_missing_coverage=0,
        population_fingerprint=(
            (fold_id + policy_id).encode().hex() + "0" * 64
        )[:64],
        benchmark_fingerprint="d" * 64,
    )


def _review() -> FiveDayRankingV3ComponentAttributionReview:
    fold_experiments = tuple(
        FoldExperimentReview(
            fold_id=fold_id,
            policy_id=policy_id,
            experiment_id=experiment_id,
            coverage=_coverage(fold_id, policy_id),
            metrics=_metrics(),
            status="COMPLETE",
        )
        for policy_id in V3_POLICY_IDS
        for fold_id in FOLDS
        for experiment_id in EXPERIMENTS
    )
    combined_experiments = tuple(
        FoldExperimentReview(
            fold_id="train-combined",
            policy_id=policy_id,
            experiment_id=experiment_id,
            coverage=_coverage("train-combined", policy_id),
            metrics=RobustRankMetrics(
                **{
                    **_metrics().__dict__,
                    "candidate_rows": 300,
                    "paired_dates": 60,
                    "correlation_eligible_dates": 60,
                    "correlation_dates": 60,
                    "audit": RankMetricAuditTotals(
                        raw_difference_sum=Decimal("0.60"),
                        index_excess_difference_sum=Decimal("0.60"),
                        market_excess_difference_sum=Decimal("0.60"),
                        rank_one_win_dates=30,
                        raw_correlation_sum=Decimal("30"),
                        index_excess_correlation_sum=Decimal("30"),
                        market_excess_correlation_sum=Decimal("30"),
                    ),
                    "rank_one_win_interval": wilson_interval(30, 60),
                }
            ),
            status="COMPLETE",
        )
        for policy_id in V3_POLICY_IDS
        for experiment_id in EXPERIMENTS
    )
    fold_correlations = tuple(
        ComponentCorrelationReview(
            fold_id=fold_id,
            policy_id=policy_id,
            population_fingerprint=_coverage(
                fold_id, policy_id
            ).population_fingerprint,
            metrics=_correlations(),
        )
        for policy_id in V3_POLICY_IDS
        for fold_id in FOLDS
    )
    combined_correlations = tuple(
        ComponentCorrelationReview(
            fold_id="train-combined",
            policy_id=policy_id,
            population_fingerprint=_coverage(
                "train-combined", policy_id
            ).population_fingerprint,
            metrics=tuple(
                ComponentCorrelationMetrics(
                    **{
                        **value.__dict__,
                        "eligible_dates": 60,
                        "completed_dates": 60,
                        "audit": ComponentCorrelationAuditTotals(
                            raw_correlation_sum=Decimal("30"),
                            index_excess_correlation_sum=Decimal("30"),
                            market_excess_correlation_sum=Decimal("30"),
                        ),
                    }
                )
                for value in _correlations()
            ),
        )
        for policy_id in V3_POLICY_IDS
    )
    zero = AblationDelta(
        paired_dates=30,
        correlation_dates=30,
        boundary_ties=0,
        median_raw_difference_delta=Decimal("0"),
        rank_one_win_ratio_delta=Decimal("0"),
        mean_raw_correlation_delta=Decimal("0"),
        mean_index_excess_difference_delta=Decimal("0"),
        mean_market_excess_difference_delta=Decimal("0"),
    )
    effects = tuple(
        PolicyComponentEffect(
            policy_id=policy_id,
            component_id=component_id,
            fold1=zero,
            fold2=zero,
            label="INCONCLUSIVE",
        )
        for policy_id in V3_POLICY_IDS
        for component_id in ("CONSISTENCY", "STRUCTURE", "DOWNSIDE")
    )
    return FiveDayRankingV3ComponentAttributionReview(
        schema="five-day-ranking-v3-component-attribution-v1",
        component_attribution_version="score-component-ablation-v1",
        parent_train_identity="a" * 64,
        parent_research_identity="b" * 64,
        parent_input_fingerprint="c" * 64,
        parent_attribution_identity="e" * 64,
        market_data_fingerprint="d" * 64,
        train_split_identity="f" * 64,
        fold_experiments=fold_experiments,
        combined_experiments=combined_experiments,
        fold_component_correlations=fold_correlations,
        combined_component_correlations=combined_correlations,
        component_effects=effects,
        status="COMPLETE",
        train_only=True,
        validation_outcomes_read=False,
        test_outcomes_read=False,
        promotion_eligible=False,
        trade_permission="NO-TRADE",
    )


def test_component_attribution_round_trip_is_canonical_and_idempotent(
    tmp_path,
) -> None:
    review = _review()

    first = write_five_day_ranking_v3_component_attribution(review, tmp_path)
    first_bytes = first.read_bytes()
    second = write_five_day_ranking_v3_component_attribution(review, tmp_path)
    payload = five_day_ranking_v3_component_attribution_payload(review)
    loaded = load_five_day_ranking_v3_component_attribution(
        first,
        expected_parent_train_identity="a" * 64,
        expected_parent_research_identity="b" * 64,
        expected_parent_attribution_identity="e" * 64,
    )

    assert first == second
    assert first.name == (
        "ranking-v3-component-attribution-"
        f"{payload['artifact_identity']}.json"
    )
    assert first_bytes == second.read_bytes()
    assert first_bytes == (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    assert loaded.artifact_identity == payload["artifact_identity"]
    assert loaded.status == "COMPLETE"
    assert payload["train_split_identity"] == "f" * 64


def _write_rehashed_payload(payload: dict[str, object], directory):
    content = {
        key: value for key, value in payload.items() if key != "artifact_identity"
    }
    identity = hashlib.sha256(
        json.dumps(
            content,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    payload["artifact_identity"] = identity
    path = directory / f"ranking-v3-component-attribution-{identity}.json"
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("path", "replacement"),
    (
        (("schema",), "old-schema"),
        (("train_split_identity",), "not-a-digest"),
        (("policy_set_hash",), "0" * 64),
        (("score_formula_version",), "old-formula"),
        (("validation_outcomes_read",), True),
        (("status",), "LINEAGE_INVALID"),
        (("fold_experiments", 0, "policy_id"), "UNKNOWN"),
        (
            (
                "fold_experiments",
                0,
                "coverage",
                "population_fingerprint",
            ),
            "0" * 64,
        ),
        (("fold_experiments", 0, "metrics", "candidate_rows"), 149),
        (
            (
                "fold_experiments",
                0,
                "metrics",
                "audit",
                "raw_difference_sum",
            ),
            "0.31",
        ),
        (("fold_experiments", 0, "metrics", "mean_raw_difference"), "0.02"),
        (
            ("fold_experiments", 0, "metrics", "median_raw_difference"),
            "0.02",
        ),
        (("fold_experiments", 0, "metrics", "rank_one_win_ratio"), "0.6"),
        (
            ("fold_experiments", 0, "metrics", "rank_one_win_interval", 0),
            "0",
        ),
        (
            (
                "fold_component_correlations",
                0,
                "metrics",
                "mean_raw_correlation",
            ),
            "0.4",
        ),
        (
            (
                "component_effects",
                0,
                "fold1",
                "mean_raw_correlation_delta",
            ),
            "1",
        ),
        (("component_effects", 0, "label"), "CONSISTENTLY_HARMFUL"),
    ),
)
def test_strict_loader_rejects_rehashed_internal_tampering(
    tmp_path,
    path: tuple[object, ...],
    replacement: object,
) -> None:
    payload = deepcopy(
        five_day_ranking_v3_component_attribution_payload(_review())
    )
    target: object = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    artifact = _write_rehashed_payload(payload, tmp_path)

    with pytest.raises(ValueError, match="invalid ranking v3"):
        load_five_day_ranking_v3_component_attribution(artifact)


def test_strict_loader_rejects_missing_registry_member(tmp_path) -> None:
    payload = deepcopy(
        five_day_ranking_v3_component_attribution_payload(_review())
    )
    payload["fold_experiments"].pop()
    artifact = _write_rehashed_payload(payload, tmp_path)

    with pytest.raises(ValueError, match="invalid ranking v3"):
        load_five_day_ranking_v3_component_attribution(artifact)


def test_strict_loader_rejects_forbidden_nested_key(tmp_path) -> None:
    payload = deepcopy(
        five_day_ranking_v3_component_attribution_payload(_review())
    )
    payload["fold_experiments"][0]["rows"] = []
    artifact = _write_rehashed_payload(payload, tmp_path)

    with pytest.raises(ValueError, match="invalid ranking v3"):
        load_five_day_ranking_v3_component_attribution(artifact)


def test_strict_loader_checks_filename_and_all_expected_parents(
    tmp_path,
) -> None:
    artifact = write_five_day_ranking_v3_component_attribution(
        _review(), tmp_path
    )
    wrong_name = tmp_path / "wrong.json"
    wrong_name.write_bytes(artifact.read_bytes())

    with pytest.raises(ValueError, match="invalid ranking v3"):
        load_five_day_ranking_v3_component_attribution(wrong_name)
    with pytest.raises(ValueError, match="invalid ranking v3"):
        load_five_day_ranking_v3_component_attribution(
            artifact,
            expected_parent_train_identity="0" * 64,
        )
    with pytest.raises(ValueError, match="invalid ranking v3"):
        load_five_day_ranking_v3_component_attribution(
            artifact,
            expected_parent_research_identity="0" * 64,
        )
    with pytest.raises(ValueError, match="invalid ranking v3"):
        load_five_day_ranking_v3_component_attribution(
            artifact,
            expected_parent_attribution_identity="0" * 64,
        )


def test_strict_loader_rejects_wrong_outer_identity(tmp_path) -> None:
    payload = five_day_ranking_v3_component_attribution_payload(_review())
    payload["artifact_identity"] = "0" * 64
    artifact = tmp_path / (
        "ranking-v3-component-attribution-" + "0" * 64 + ".json"
    )
    artifact.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid ranking v3"):
        load_five_day_ranking_v3_component_attribution(artifact)


def test_writer_rejects_immutable_path_conflict(tmp_path) -> None:
    review = _review()
    artifact = write_five_day_ranking_v3_component_attribution(
        review, tmp_path
    )
    artifact.write_text("conflict\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="immutable artifact conflict"):
        write_five_day_ranking_v3_component_attribution(review, tmp_path)


@pytest.mark.parametrize("replacement", ("NaN", "0.500", 0.5))
def test_strict_loader_rejects_nonfinite_or_noncanonical_decimal(
    tmp_path,
    replacement: object,
) -> None:
    payload = deepcopy(
        five_day_ranking_v3_component_attribution_payload(_review())
    )
    payload["fold_experiments"][0]["metrics"][
        "mean_raw_correlation"
    ] = replacement
    artifact = _write_rehashed_payload(payload, tmp_path)

    with pytest.raises(ValueError, match="invalid ranking v3"):
        load_five_day_ranking_v3_component_attribution(artifact)


def test_strict_loader_recomputes_combined_experiment_from_folds(
    tmp_path,
) -> None:
    payload = deepcopy(
        five_day_ranking_v3_component_attribution_payload(_review())
    )
    metrics = payload["combined_experiments"][0]["metrics"]
    metrics["audit"]["raw_difference_sum"] = "0.66"
    metrics["mean_raw_difference"] = "0.011"
    metrics["median_raw_difference"] = "0.011"
    metrics["audit"]["median_raw_difference"] = "0.011"
    artifact = _write_rehashed_payload(payload, tmp_path)

    with pytest.raises(ValueError, match="invalid ranking v3"):
        load_five_day_ranking_v3_component_attribution(artifact)


def test_strict_loader_recomputes_combined_correlations_from_folds(
    tmp_path,
) -> None:
    payload = deepcopy(
        five_day_ranking_v3_component_attribution_payload(_review())
    )
    metrics = payload["combined_component_correlations"][0]["metrics"]
    metrics["audit"]["raw_correlation_sum"] = "24"
    metrics["mean_raw_correlation"] = "0.4"
    metrics["median_raw_correlation"] = "0.4"
    metrics["audit"]["median_raw_correlation"] = "0.4"
    artifact = _write_rehashed_payload(payload, tmp_path)

    with pytest.raises(ValueError, match="invalid ranking v3"):
        load_five_day_ranking_v3_component_attribution(artifact)


def test_failure_artifact_omits_all_metrics_and_component_labels(
    tmp_path,
) -> None:
    review = _review()
    failed = FiveDayRankingV3ComponentAttributionReview(
        **{
            **review.__dict__,
            "fold_experiments": (),
            "combined_experiments": (),
            "fold_component_correlations": (),
            "combined_component_correlations": (),
            "component_effects": (),
            "status": "LINEAGE_INVALID",
        }
    )

    artifact = write_five_day_ranking_v3_component_attribution(
        failed, tmp_path
    )
    loaded = load_five_day_ranking_v3_component_attribution(artifact)

    assert loaded.status == "LINEAGE_INVALID"
    assert loaded.payload["component_effects"] == []
