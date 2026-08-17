from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest

from stock_ai.buy_point_selection.five_day_ranking_v3 import (
    V3_POLICY_IDS,
    V3_SELECTION_MODES,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_attribution import (
    ATTRIBUTION_SCHEMA,
    ATTRIBUTION_VERSION,
    MIN_MARKET_MEDIAN_MEMBERS,
    UNIVERSE_VERSION,
    AttributionMetrics,
    AttributionVariantReview,
    CoverageSummary,
    FiveDayRankingV3AttributionReview,
    RankCorrelationMetrics,
    RankPairMetrics,
)
from stock_ai.buy_point_selection.five_day_ranking_v3_attribution_report import (
    five_day_ranking_v3_attribution_payload,
    load_five_day_ranking_v3_attribution,
    write_five_day_ranking_v3_attribution,
)
from stock_ai.buy_point_selection.validation import ChronologicalSplit


FOLDS = ("train-fold-1", "train-fold-2", "train-combined")
RANK_BANDS = ("RANK_1", "RANK_2_3", "RANK_4_5", "RANK_6_PLUS")
STATUSES = (
    "STOPPED",
    "TIME_EXIT_GAIN",
    "TIME_EXIT_FLAT",
    "TIME_EXIT_LOSS",
)
FORBIDDEN_KEYS = (
    "observations",
    "selected_observations",
    "plans",
    "plan_keys",
    "ranked_plan_keys",
    "admitted_trade_keys",
    "code",
    "ts_code",
    "position",
    "holding",
    "order",
    "notification",
    "memory",
)


def _dates(count: int) -> tuple[date, ...]:
    start = date(2024, 1, 2)
    return tuple(start + timedelta(days=index) for index in range(count))


def _empty_metrics() -> AttributionMetrics:
    return AttributionMetrics(
        eligible_rows=0,
        completed_rows=0,
        excluded_rows=0,
        excluded_missing_coverage=0,
        mean_return=None,
        median_return=None,
        positive_ratio=None,
        positive_wilson_interval=None,
        mean_matched_index_return=None,
        median_matched_index_return=None,
        mean_market_median_return=None,
        median_market_median_return=None,
        mean_index_excess=None,
        median_index_excess=None,
        mean_market_median_excess=None,
        median_market_median_excess=None,
        mean_gross_return=None,
        mean_after_cost_drag=None,
        verdict="INCONCLUSIVE",
    )


def _one_metrics(*, gross: bool) -> AttributionMetrics:
    return AttributionMetrics(
        eligible_rows=1,
        completed_rows=1,
        excluded_rows=0,
        excluded_missing_coverage=0,
        mean_return=Decimal("0.04"),
        median_return=Decimal("0.04"),
        positive_ratio=Decimal("1"),
        positive_wilson_interval=(
            Decimal("0.2065493143772374273553130095"),
            Decimal("1"),
        ),
        mean_matched_index_return=Decimal("0"),
        median_matched_index_return=Decimal("0"),
        mean_market_median_return=Decimal("0"),
        median_market_median_return=Decimal("0"),
        mean_index_excess=Decimal("0.04"),
        median_index_excess=Decimal("0.04"),
        mean_market_median_excess=Decimal("0.04"),
        median_market_median_excess=Decimal("0.04"),
        mean_gross_return=Decimal("0.05") if gross else None,
        mean_after_cost_drag=Decimal("0.01") if gross else None,
        verdict="INCONCLUSIVE",
    )


def _review() -> FiveDayRankingV3AttributionReview:
    dates = _dates(630)
    empty = _empty_metrics()
    actual = _one_metrics(gross=True)
    fixed = _one_metrics(gross=False)
    variants = tuple(
        AttributionVariantReview(
            fold_id=fold_id,
            policy_id=policy_id,
            selection_mode=selection_mode,
            actual=actual,
            actual_by_status={
                "STOPPED": empty,
                "TIME_EXIT_GAIN": actual,
                "TIME_EXIT_FLAT": empty,
                "TIME_EXIT_LOSS": empty,
            },
            fixed_five_by_rank_band={
                "RANK_1": fixed,
                "RANK_2_3": empty,
                "RANK_4_5": empty,
                "RANK_6_PLUS": empty,
            },
            rank_pairs=RankPairMetrics(
                paired_dates=1,
                mean_raw_difference=Decimal("0.01"),
                median_raw_difference=Decimal("0.01"),
                mean_index_excess_difference=Decimal("0.01"),
                median_index_excess_difference=Decimal("0.01"),
                mean_market_excess_difference=Decimal("0.01"),
                median_market_excess_difference=Decimal("0.01"),
                rank_one_win_ratio=Decimal("1"),
                verdict="RANKER_INCONCLUSIVE",
            ),
            rank_correlations=RankCorrelationMetrics(
                eligible_dates=1,
                completed_dates=1,
                mean_raw_correlation=Decimal("1"),
                median_raw_correlation=Decimal("1"),
                mean_index_excess_correlation=Decimal("1"),
                median_index_excess_correlation=Decimal("1"),
                mean_market_excess_correlation=Decimal("1"),
                median_market_excess_correlation=Decimal("1"),
            ),
            funnel_counts={
                "ACTUAL_ATTRIBUTION_ELIGIBLE": 1,
                "ACTUAL_ATTRIBUTION_COMPLETED": 1,
                "ACTUAL_ATTRIBUTION_MISSING_COVERAGE": 0,
                "FIXED_FIVE_RANKED_ELIGIBLE": 1,
                "FIXED_FIVE_COMPLETED": 1,
                "FIXED_FIVE_MISSING_COVERAGE": 0,
                "FIXED_FIVE_WITHOUT_TRAIN_HORIZON": 0,
                "FIXED_FIVE_STOCK_ENDPOINT_MISSING": 0,
            },
        )
        for policy_id in V3_POLICY_IDS
        for selection_mode in V3_SELECTION_MODES
        for fold_id in FOLDS
    )
    return FiveDayRankingV3AttributionReview(
        schema=ATTRIBUTION_SCHEMA,
        attribution_version=ATTRIBUTION_VERSION,
        parent_train_identity="a" * 64,
        parent_research_identity="b" * 64,
        parent_input_fingerprint="c" * 64,
        split=ChronologicalSplit(
            train=dates[:378],
            validation=dates[378:504],
            test=dates[504:],
        ),
        market_data_fingerprint="d" * 64,
        coverage=CoverageSummary(
            attempted_intervals=144,
            completed_intervals=144,
            index_endpoint_missing_intervals=0,
            market_members_below_threshold_intervals=0,
            missing_endpoint_dates=(),
        ),
        variants=variants,
        status="COMPLETE",
        train_only=True,
        validation_outcomes_read=False,
        test_outcomes_read=False,
        promotion_eligible=False,
        trade_permission="NO-TRADE",
    )


def _content_hash(payload: dict[str, object]) -> str:
    content = {key: value for key, value in payload.items() if key != "artifact_identity"}
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _write_tampered(tmp_path: Path, payload: dict[str, object]) -> Path:
    payload["artifact_identity"] = _content_hash(payload)
    path = tmp_path / (
        f"ranking-v3-train-attribution-{payload['artifact_identity']}.json"
    )
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


def test_attribution_artifact_round_trip_is_canonical_and_idempotent(
    tmp_path: Path,
) -> None:
    first = write_five_day_ranking_v3_attribution(_review(), tmp_path)
    first_bytes = first.read_bytes()
    second = write_five_day_ranking_v3_attribution(_review(), tmp_path)
    artifact = load_five_day_ranking_v3_attribution(
        first,
        expected_parent_train_identity="a" * 64,
        expected_parent_research_identity="b" * 64,
    )

    assert second == first
    assert second.read_bytes() == first_bytes
    assert first.name == (
        f"ranking-v3-train-attribution-{artifact.artifact_identity}.json"
    )
    assert artifact.artifact_identity == _content_hash(dict(artifact.payload))
    assert len(artifact.payload["variants"]) == 72
    assert artifact.status == "COMPLETE"


def test_payload_freezes_benchmarks_and_safety_flags() -> None:
    payload = five_day_ranking_v3_attribution_payload(_review())

    assert payload["benchmark_definitions"] == {
        "actual_interval_basis": (
            "entry-date-close-to-exit-date-close-attribution-approximation-v1"
        ),
        "fixed_five_basis": (
            "signal-close-to-fifth-subsequent-train-close-v1"
        ),
        "matched_indexes": {
            "000|001|002|003": "sz.399001",
            "600|601|603|605": "sh.000001",
            "688": "sh.000688",
        },
        "minimum_market_members": MIN_MARKET_MEDIAN_MEMBERS,
        "universe_version": UNIVERSE_VERSION,
    }
    assert payload["train_only"] is True
    assert payload["validation_outcomes_read"] is False
    assert payload["test_outcomes_read"] is False
    assert payload["promotion_eligible"] is False
    assert payload["trade_permission"] == "NO-TRADE"


def test_payload_mutation_cannot_change_later_benchmark_contract() -> None:
    first = five_day_ranking_v3_attribution_payload(_review())
    first["benchmark_definitions"]["minimum_market_members"] = 1

    second = five_day_ranking_v3_attribution_payload(_review())

    assert (
        second["benchmark_definitions"]["minimum_market_members"]
        == MIN_MARKET_MEDIAN_MEMBERS
    )


@pytest.mark.parametrize("forbidden_key", FORBIDDEN_KEYS)
def test_loader_rejects_forbidden_nested_keys(
    tmp_path: Path,
    forbidden_key: str,
) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    payload["variants"][0]["actual"][forbidden_key] = []
    path = _write_tampered(tmp_path, payload)

    with pytest.raises(ValueError, match="invalid ranking v3 attribution artifact"):
        load_five_day_ranking_v3_attribution(path)


def test_loader_rejects_numeric_tamper_with_old_identity(tmp_path: Path) -> None:
    path = write_five_day_ranking_v3_attribution(_review(), tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["coverage"]["completed_intervals"] = 143
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid ranking v3 attribution artifact"):
        load_five_day_ranking_v3_attribution(path)


def test_loader_rejects_wrong_filename(tmp_path: Path) -> None:
    original = write_five_day_ranking_v3_attribution(_review(), tmp_path)
    wrong = tmp_path / "wrong.json"
    wrong.write_bytes(original.read_bytes())

    with pytest.raises(ValueError, match="invalid ranking v3 attribution artifact"):
        load_five_day_ranking_v3_attribution(wrong)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (("fold_id", "future"), ("policy_id", "future"), ("selection_mode", "future")),
)
def test_loader_rejects_unknown_variant_registry_value(
    tmp_path: Path,
    field: str,
    bad_value: str,
) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    payload["variants"][0][field] = bad_value

    with pytest.raises(ValueError, match="invalid ranking v3 attribution artifact"):
        load_five_day_ranking_v3_attribution(_write_tampered(tmp_path, payload))


def test_loader_rejects_unknown_rank_band(tmp_path: Path) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    bands = payload["variants"][0]["fixed_five_by_rank_band"]
    bands["RANK_FUTURE"] = bands.pop("RANK_1")

    with pytest.raises(ValueError, match="invalid ranking v3 attribution artifact"):
        load_five_day_ranking_v3_attribution(_write_tampered(tmp_path, payload))


def test_loader_rejects_complete_artifact_with_missing_aggregate(
    tmp_path: Path,
) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    del payload["variants"][0]["actual_by_status"]["STOPPED"]

    with pytest.raises(ValueError, match="invalid ranking v3 attribution artifact"):
        load_five_day_ranking_v3_attribution(_write_tampered(tmp_path, payload))


def test_loader_rejects_incomplete_artifact_with_causal_verdict(
    tmp_path: Path,
) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    payload["status"] = "MARKET_DATA_INCOMPLETE"
    payload["coverage"] = {
        "attempted_intervals": 145,
        "completed_intervals": 144,
        "index_endpoint_missing_intervals": 1,
        "market_members_below_threshold_intervals": 0,
        "missing_endpoint_dates": ["2024-01-02"],
    }
    payload["variants"][0]["actual"]["verdict"] = "MARKET_DRAG"

    with pytest.raises(ValueError, match="invalid ranking v3 attribution artifact"):
        load_five_day_ranking_v3_attribution(_write_tampered(tmp_path, payload))


def test_loader_rejects_completed_count_above_eligible(tmp_path: Path) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    payload["variants"][0]["actual"]["completed_rows"] = 2

    with pytest.raises(ValueError, match="invalid ranking v3 attribution artifact"):
        load_five_day_ranking_v3_attribution(_write_tampered(tmp_path, payload))


def test_loader_rejects_non_finite_decimal(tmp_path: Path) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    payload["variants"][0]["actual"]["mean_return"] = "NaN"

    with pytest.raises(ValueError, match="invalid ranking v3 attribution artifact"):
        load_five_day_ranking_v3_attribution(_write_tampered(tmp_path, payload))


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("train_only", False),
        ("validation_outcomes_read", True),
        ("test_outcomes_read", True),
        ("promotion_eligible", True),
        ("trade_permission", "TRADE"),
    ),
)
def test_loader_rejects_safety_flag_changes(
    tmp_path: Path,
    field: str,
    bad_value: object,
) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    payload[field] = bad_value

    with pytest.raises(ValueError, match="invalid ranking v3 attribution artifact"):
        load_five_day_ranking_v3_attribution(_write_tampered(tmp_path, payload))


def test_loader_rejects_expected_parent_identity_mismatch(tmp_path: Path) -> None:
    path = write_five_day_ranking_v3_attribution(_review(), tmp_path)

    with pytest.raises(ValueError, match="invalid ranking v3 attribution artifact"):
        load_five_day_ranking_v3_attribution(
            path,
            expected_parent_train_identity="f" * 64,
        )
    with pytest.raises(ValueError, match="invalid ranking v3 attribution artifact"):
        load_five_day_ranking_v3_attribution(
            path,
            expected_parent_research_identity="f" * 64,
        )


def test_writer_rejects_immutable_same_path_conflict(tmp_path: Path) -> None:
    path = write_five_day_ranking_v3_attribution(_review(), tmp_path)
    path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="immutable artifact conflict"):
        write_five_day_ranking_v3_attribution(_review(), tmp_path)
    assert path.read_text(encoding="utf-8") == "{}\n"
