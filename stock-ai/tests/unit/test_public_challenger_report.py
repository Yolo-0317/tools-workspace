from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json

import pytest

from stock_ai.buy_point_selection.public_challenger_report import (
    load_challenger_freeze,
    load_challenger_research,
    write_challenger_freeze,
    write_challenger_research,
    write_challenger_test_once,
    write_challenger_validation,
)
from stock_ai.buy_point_selection.public_challenger_signals import (
    CONTRARIAN_TRACK,
    EXECUTION_TRACK,
    RESIDUAL_TRACK,
)
from stock_ai.buy_point_selection.public_challenger_validation import (
    ChallengerAssessment,
    ChallengerPortfolioMetrics,
    ChallengerSegmentMetrics,
    PairedComparison,
    PublicChallengerFreezeReview,
    PublicChallengerResearchReview,
    PublicChallengerTestReview,
    PublicChallengerValidationReview,
)
from stock_ai.buy_point_selection.validation import ChronologicalSplit


def _weekday_dates(count: int) -> tuple[date, ...]:
    values: list[date] = []
    current = date(2023, 1, 3)
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current)
        current += timedelta(days=1)
    return tuple(values)


def _split() -> ChronologicalSplit:
    dates = _weekday_dates(630)
    return ChronologicalSplit(
        train=dates[:378],
        validation=dates[378:504],
        test=dates[504:],
    )


def _segment(segment: str = "VALIDATION") -> ChallengerSegmentMetrics:
    return ChallengerSegmentMetrics(
        segment=segment,
        triggered_resolved=40,
        net_expectancy=Decimal("0.01"),
        profit_factor=Decimal("1.50"),
        profitable_wilson_lower=Decimal("0.50"),
        stop_rate=Decimal("0.20"),
        positive_window_ratio=Decimal("0.70"),
        maximum_drawdown=Decimal("0.05"),
        qualifies=True,
        reasons=(),
    )


def _portfolio() -> ChallengerPortfolioMetrics:
    return ChallengerPortfolioMetrics(
        accepted_trades=40,
        maximum_drawdown=Decimal("0.05"),
        maximum_stock_trade_share=Decimal("0.05"),
        maximum_stock_profit_share=Decimal("0.10"),
        maximum_sector_trade_share=Decimal("0.20"),
        maximum_sector_profit_share=Decimal("0.25"),
        top5_profit_share=Decimal("0.20"),
        qualifies=True,
        reasons=(),
    )


def _assessment() -> ChallengerAssessment:
    return ChallengerAssessment(
        execution_metrics=_segment(),
        portfolio_metrics=_portfolio(),
        paired=PairedComparison(
            paired_dates=40,
            mean_difference=Decimal("0.002"),
            confidence_interval=(Decimal("-0.001"), Decimal("0.005")),
            jaccard=Decimal("0.30"),
            incremental_resolved=30,
            incremental_expectancy=Decimal("0.01"),
            incremental_profit_factor=Decimal("1.30"),
        ),
        verdict="COMPLEMENTARY",
        reasons=(),
    )


def _research_review() -> PublicChallengerResearchReview:
    metrics = _segment()
    return PublicChallengerResearchReview(
        split=_split(),
        input_fingerprint="a" * 64,
        track_metrics={
            CONTRARIAN_TRACK: metrics,
            RESIDUAL_TRACK: metrics,
            EXECUTION_TRACK: metrics,
        },
        validation_assessment=_assessment(),
        funnel_counts={"MARKET_CAPACITY": 2},
        point_in_time_complete=True,
    )


def test_research_payload_is_aggregate_only_and_byte_stable(tmp_path) -> None:
    first = write_challenger_research(_research_review(), tmp_path)
    initial = first.read_bytes()
    second = write_challenger_research(_research_review(), tmp_path)
    payload = json.loads(first.read_text(encoding="utf-8"))

    assert first == second
    assert first.read_bytes() == initial
    assert "600001" not in first.read_text(encoding="utf-8")
    assert "observations" not in payload
    assert payload["trade_permission"] == "NO-TRADE"
    assert payload["promotion_eligible"] is False
    assert payload["test_outcomes_read"] is False
    assert payload["evaluator_version"] == "public-challenger-evaluator-v2"


def test_same_identity_with_different_content_is_rejected(tmp_path) -> None:
    path = write_challenger_research(_research_review(), tmp_path)
    path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="immutable public challenger artifact conflict",
    ):
        write_challenger_research(_research_review(), tmp_path)


def test_research_loader_round_trips_strict_aggregate_review(tmp_path) -> None:
    path = write_challenger_research(_research_review(), tmp_path)

    loaded = load_challenger_research(path)

    assert loaded.review == _research_review()
    assert loaded.validation_eligible is True
    assert loaded.artifact_identity in path.name


def _validation_review(
    parent_research_identity: str,
    *,
    input_fingerprint: str = "a" * 64,
) -> PublicChallengerValidationReview:
    return PublicChallengerValidationReview(
        parent_research_identity=parent_research_identity,
        input_fingerprint=input_fingerprint,
        assessment=_assessment(),
        test_eligible=True,
        reasons=(),
    )


def _freeze_review(
    parent_research_identity: str,
    split_identity: str,
    *,
    input_fingerprint: str = "a" * 64,
) -> PublicChallengerFreezeReview:
    return PublicChallengerFreezeReview(
        parent_research_identity=parent_research_identity,
        input_fingerprint=input_fingerprint,
        split_identity=split_identity,
        frozen_rule_hash="b" * 64,
        test_eligible=True,
        reasons=(),
    )


def _test_review(
    parent_freeze_identity: str,
    parent_research_identity: str,
    *,
    input_fingerprint: str = "a" * 64,
) -> PublicChallengerTestReview:
    return PublicChallengerTestReview(
        parent_freeze_identity=parent_freeze_identity,
        parent_research_identity=parent_research_identity,
        input_fingerprint=input_fingerprint,
        assessment=_assessment(),
    )


def _write_parent_chain(tmp_path):
    research = load_challenger_research(
        write_challenger_research(_research_review(), tmp_path)
    )
    validation = write_challenger_validation(
        _validation_review(research.artifact_identity),
        tmp_path,
    )
    freeze_path = write_challenger_freeze(
        _freeze_review(research.artifact_identity, research.split_identity),
        tmp_path,
    )
    return research, validation, freeze_path


def test_freeze_loader_recomputes_identity_and_rejects_tampering(tmp_path) -> None:
    _, _, path = _write_parent_chain(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["residual_fraction"] = "0.15"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact identity mismatch"):
        load_challenger_freeze(path)


def test_freeze_round_trip_preserves_parent_lineage(tmp_path) -> None:
    research, _, path = _write_parent_chain(tmp_path)

    loaded = load_challenger_freeze(path)

    assert loaded.parent_research_identity == research.artifact_identity
    assert loaded.input_fingerprint == research.input_fingerprint
    assert loaded.split_identity == research.split_identity
    assert loaded.test_eligible is True
    assert loaded.payload["trade_permission"] == "NO-TRADE"


def test_loader_rejects_unknown_field_even_with_recomputed_identity(tmp_path) -> None:
    path = write_challenger_research(_research_review(), tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    content = {key: value for key, value in payload.items() if key != "artifact_identity"}
    identity = hashlib.sha256(
        json.dumps(
            content,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    payload["artifact_identity"] = identity
    forged = tmp_path / f"public-short-term-challenger-research-{identity}.json"
    forged.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fields invalid"):
        load_challenger_research(forged)


def test_validation_writer_rejects_parent_or_input_mismatch(tmp_path) -> None:
    research = load_challenger_research(
        write_challenger_research(_research_review(), tmp_path)
    )

    with pytest.raises(ValueError, match="parent lineage mismatch"):
        write_challenger_validation(
            _validation_review("f" * 64),
            tmp_path,
        )
    with pytest.raises(ValueError, match="input fingerprint mismatch"):
        write_challenger_validation(
            _validation_review(
                research.artifact_identity,
                input_fingerprint="c" * 64,
            ),
            tmp_path,
        )


def test_test_writer_rejects_parent_or_input_fingerprint_mismatch(tmp_path) -> None:
    research, _, freeze_path = _write_parent_chain(tmp_path)
    freeze = load_challenger_freeze(freeze_path)

    with pytest.raises(ValueError, match="parent lineage mismatch"):
        write_challenger_test_once(
            _test_review("wrong", research.artifact_identity),
            tmp_path,
        )
    with pytest.raises(ValueError, match="input fingerprint mismatch"):
        write_challenger_test_once(
            _test_review(
                freeze.artifact_identity,
                research.artifact_identity,
                input_fingerprint="c" * 64,
            ),
            tmp_path,
        )


def test_test_writer_is_no_trade_and_consumes_freeze_once(tmp_path) -> None:
    research, _, freeze_path = _write_parent_chain(tmp_path)
    freeze = load_challenger_freeze(freeze_path)
    review = _test_review(freeze.artifact_identity, research.artifact_identity)

    path = write_challenger_test_once(review, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.name == f"public-short-term-challenger-test-{freeze.artifact_identity}.json"
    assert payload["trade_permission"] == "NO-TRADE"
    assert payload["promotion_eligible"] is False
    with pytest.raises(ValueError, match="test artifact already exists"):
        write_challenger_test_once(review, tmp_path)


def test_writer_rejects_non_digest_input_fingerprint(tmp_path) -> None:
    with pytest.raises(ValueError, match="input fingerprint invalid"):
        write_challenger_research(
            replace(_research_review(), input_fingerprint="not-a-digest"),
            tmp_path,
        )


def test_freeze_writer_rejects_non_hex_rule_hash(tmp_path) -> None:
    research = load_challenger_research(
        write_challenger_research(_research_review(), tmp_path)
    )
    write_challenger_validation(
        _validation_review(research.artifact_identity),
        tmp_path,
    )

    with pytest.raises(ValueError, match="frozen rule hash invalid"):
        write_challenger_freeze(
            replace(
                _freeze_review(
                    research.artifact_identity,
                    research.split_identity,
                ),
                frozen_rule_hash="z" * 64,
            ),
            tmp_path,
        )
