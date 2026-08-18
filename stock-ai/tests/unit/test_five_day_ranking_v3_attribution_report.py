from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
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
    AttributedReturn,
    AttributionAuditTotals,
    AttributionMetrics,
    AttributionVariantReview,
    CoverageSummary,
    FiveDayRankingV3AttributionReview,
    RankCorrelationMetrics,
    RankPairMetrics,
    summarize_attributed_returns,
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


def _empty_metrics(*, gross: bool) -> AttributionMetrics:
    return AttributionMetrics(
        eligible_rows=0,
        completed_rows=0,
        excluded_rows=0,
        excluded_missing_coverage=0,
        audit_totals=AttributionAuditTotals(
            positive_rows=0,
            raw_return_sum=Decimal("0"),
            matched_index_return_sum=Decimal("0"),
            market_median_return_sum=Decimal("0"),
            gross_return_sum=Decimal("0") if gross else None,
        ),
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
        audit_totals=AttributionAuditTotals(
            positive_rows=1,
            raw_return_sum=Decimal("0.04"),
            matched_index_return_sum=Decimal("0"),
            market_median_return_sum=Decimal("0"),
            gross_return_sum=Decimal("0.05") if gross else None,
        ),
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


def _recurring_cost_drag_metrics() -> AttributionMetrics:
    raw_returns = (
        Decimal("0.0135792468135792468135792468"),
        Decimal("-0.0246801357924680135792468013"),
        Decimal("0.0379135792468013579246801357"),
    )
    gross_returns = (
        Decimal("0.0148138147037027036025915924"),
        Decimal("-0.0234455679023445567902344557"),
        Decimal("0.0391481471369248147136924813"),
    )
    rows = tuple(
        AttributedReturn(
            raw_return=raw,
            matched_index_return=Decimal("0"),
            market_median_return=Decimal("0"),
            index_excess=raw,
            market_median_excess=raw,
            market_members=1000,
        )
        for raw in raw_returns
    )
    return summarize_attributed_returns(
        rows,
        eligible_rows=3,
        excluded_missing_coverage=0,
        gross_returns=gross_returns,
    )


def _review() -> FiveDayRankingV3AttributionReview:
    dates = _dates(630)
    actual_empty = _empty_metrics(gross=True)
    fixed_empty = _empty_metrics(gross=False)
    actual = _one_metrics(gross=True)
    fixed = _one_metrics(gross=False)
    variants = tuple(
        AttributionVariantReview(
            fold_id=fold_id,
            policy_id=policy_id,
            selection_mode=selection_mode,
            actual=actual,
            actual_by_status={
                "STOPPED": actual_empty,
                "TIME_EXIT_GAIN": actual,
                "TIME_EXIT_FLAT": actual_empty,
                "TIME_EXIT_LOSS": actual_empty,
            },
            fixed_five_by_rank_band={
                "RANK_1": fixed,
                "RANK_2_3": fixed_empty,
                "RANK_4_5": fixed_empty,
                "RANK_6_PLUS": fixed_empty,
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


def test_recurring_decimal_audit_totals_survive_strict_round_trip(
    tmp_path: Path,
) -> None:
    base = _review()
    metrics = _recurring_cost_drag_metrics()
    empty = _empty_metrics(gross=True)
    variants = tuple(
        replace(
            variant,
            actual=metrics,
            actual_by_status={
                "STOPPED": empty,
                "TIME_EXIT_GAIN": metrics,
                "TIME_EXIT_FLAT": empty,
                "TIME_EXIT_LOSS": empty,
            },
            funnel_counts={
                **variant.funnel_counts,
                "ACTUAL_ATTRIBUTION_ELIGIBLE": 3,
                "ACTUAL_ATTRIBUTION_COMPLETED": 3,
            },
        )
        for variant in base.variants
    )
    review = replace(
        base,
        coverage=replace(
            base.coverage,
            attempted_intervals=288,
            completed_intervals=288,
        ),
        variants=variants,
    )

    path = write_five_day_ranking_v3_attribution(review, tmp_path)
    artifact = load_five_day_ranking_v3_attribution(
        path,
        expected_parent_train_identity="a" * 64,
        expected_parent_research_identity="b" * 64,
    )
    actual = artifact.payload["variants"][0]["actual"]

    assert actual["audit_totals"] == {
        "positive_rows": 2,
        "raw_return_sum": "0.0268126902679125911590125812",
        "matched_index_return_sum": "0",
        "market_median_return_sum": "0",
        "gross_return_sum": "0.0305163939382829615260496180",
    }
    assert actual["mean_after_cost_drag"] == (
        "0.0012345678901234567890123456"
    )


def test_zero_positive_actual_status_survives_strict_round_trip(
    tmp_path: Path,
) -> None:
    row = AttributedReturn(
        raw_return=Decimal("-0.04"),
        matched_index_return=Decimal("0"),
        market_median_return=Decimal("0"),
        index_excess=Decimal("-0.04"),
        market_median_excess=Decimal("-0.04"),
        market_members=1000,
    )
    metrics = summarize_attributed_returns(
        (row,),
        eligible_rows=1,
        excluded_missing_coverage=0,
        gross_returns=(Decimal("-0.03"),),
    )
    base = _review()
    empty = _empty_metrics(gross=True)
    variants = tuple(
        replace(
            variant,
            actual=metrics,
            actual_by_status={
                "STOPPED": metrics,
                "TIME_EXIT_GAIN": empty,
                "TIME_EXIT_FLAT": empty,
                "TIME_EXIT_LOSS": empty,
            },
        )
        for variant in base.variants
    )
    review = replace(base, variants=variants)

    path = write_five_day_ranking_v3_attribution(review, tmp_path)
    artifact = load_five_day_ranking_v3_attribution(path)

    assert artifact.status == "COMPLETE"
    assert artifact.payload["variants"][0]["actual"]["positive_ratio"] == "0"
    assert artifact.payload["variants"][0]["actual"][
        "positive_wilson_interval"
    ][0] == "0"


def test_payload_freezes_benchmarks_and_safety_flags() -> None:
    payload = five_day_ranking_v3_attribution_payload(_review())

    assert payload["schema"] == "five-day-ranking-v3-train-attribution-v2"
    assert payload["attribution_version"] == (
        "dual-benchmark-exact-aggregate-v2"
    )
    assert payload["variants"][0]["actual"]["audit_totals"] == {
        "positive_rows": 1,
        "raw_return_sum": "0.04",
        "matched_index_return_sum": "0",
        "market_median_return_sum": "0",
        "gross_return_sum": "0.05",
    }
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


def test_loader_rejects_mean_not_derived_from_audit_total(
    tmp_path: Path,
) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    metric = payload["variants"][0]["fixed_five_by_rank_band"]["RANK_1"]
    metric["mean_return"] = "0.041"
    metric["mean_index_excess"] = "0.041"
    metric["mean_market_median_excess"] = "0.041"

    with pytest.raises(ValueError):
        load_five_day_ranking_v3_attribution(
            _write_tampered(tmp_path, payload)
        )


def test_loader_rejects_status_audit_total_mismatch(tmp_path: Path) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    actual = payload["variants"][0]["actual"]
    actual["audit_totals"]["raw_return_sum"] = "0.05"
    actual["mean_return"] = "0.05"
    actual["mean_index_excess"] = "0.05"
    actual["mean_market_median_excess"] = "0.05"
    actual["mean_after_cost_drag"] = "0"

    with pytest.raises(ValueError):
        load_five_day_ranking_v3_attribution(
            _write_tampered(tmp_path, payload)
        )


def test_v2_loader_rejects_v1_attribution_schema(tmp_path: Path) -> None:
    payload = deepcopy(five_day_ranking_v3_attribution_payload(_review()))
    payload["schema"] = "five-day-ranking-v3-train-attribution-v1"
    payload["attribution_version"] = "dual-benchmark-train-attribution-v1"

    with pytest.raises(ValueError):
        load_five_day_ranking_v3_attribution(
            _write_tampered(tmp_path, payload)
        )


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
