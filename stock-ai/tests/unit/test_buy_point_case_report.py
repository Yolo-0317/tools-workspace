from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from stock_ai.buy_point_selection.case_report import (
    case_identity,
    case_payload,
    render_case_markdown,
    write_case_revision,
)
from stock_ai.buy_point_selection.case_review import (
    BuyableWinner,
    CaseCandidate,
    CaseOutcome,
    CaseReview,
    CaseSignalReplay,
    ConditionalShadowOpportunity,
    OpportunityEpisode,
)
from stock_ai.buy_point_selection.models import DetectedSetup, SetupType
from stock_ai.buy_point_selection.planning import PricePlan


SIGNAL_START = date(2026, 8, 3)
SIGNAL_END = date(2026, 8, 7)


def _candidate(
    signal_date: date,
    structure_id: str,
    *,
    code: str = "600001",
) -> CaseCandidate:
    setup = DetectedSetup(
        code,
        SetupType.TREND_PULLBACK,
        signal_date,
        SIGNAL_START,
        Decimal("9.99"),
        Decimal("9.10"),
        Decimal("0.40"),
        (),
        {},
    )
    return CaseCandidate(
        code,
        signal_date,
        setup,
        PricePlan(
            structure_id,
            code,
            setup.setup_type,
            signal_date,
            Decimal("9.80"),
            Decimal("10.00"),
            Decimal("9.00"),
            Decimal("12.00"),
            Decimal("1.00"),
            Decimal("2.00"),
            100,
            date(2026, 8, 5),
        ),
        "NEAR_MISS",
        "INSUFFICIENT_TWO_R_SPACE",
        (Decimal("0.25"), Decimal("-0.40"), Decimal("-200000"), code),
    )


def _review(
    *,
    outcomes: tuple[CaseOutcome, ...],
    cutoff: date = date(2026, 8, 14),
) -> CaseReview:
    return CaseReview(
        signal_dates=(SIGNAL_START, SIGNAL_END),
        outcome_cutoff=cutoff,
        rule_version="buy-point-selection-3.1.0",
        policy_hash="policy-hash",
        replay=CaseSignalReplay({}, ()),
        outcomes=outcomes,
        winners=(
            BuyableWinner(
                "600003",
                SIGNAL_END,
                Decimal("0.08"),
                date(2026, 8, 10),
                (),
                "NO_BUY_POINT_SETUP",
            ),
        ),
        risk_coverage_complete=False,
    )


def test_case_payload_is_deterministic_and_explicitly_non_trading() -> None:
    """Catches input order or a missing safety label changing the artifact."""
    first = CaseOutcome(
        "600002", SIGNAL_START, "NEAR_MISS", "CLOSED", Decimal("0.06"), Decimal("0.02")
    )
    second = CaseOutcome(
        "600001", SIGNAL_START, "STRICT_SHADOW", "PENDING", None, None
    )

    left = case_payload(_review(outcomes=(first, second)))
    right = case_payload(_review(outcomes=(second, first)))

    assert left == right
    assert left["status"] == "CASE_ANALYSIS_ONLY"
    assert left["trade_permission"] == "NO-TRADE"
    assert [value["code"] for value in left["outcomes"]] == ["600001", "600002"]
    assert "不能用于规则晋级或交易" in render_case_markdown(
        _review(outcomes=(first, second))
    )


def test_v2_schema_participates_in_immutable_case_identity() -> None:
    """Catches a v2 report colliding with the existing immutable v1 revision."""
    review = _review(outcomes=())

    payload = case_payload(review)

    assert payload["schema"] == "buy-point-case-review-v2"
    assert case_identity(
        review,
        schema="buy-point-case-review-v1",
    ) != case_identity(
        review,
        schema="buy-point-case-review-v2",
    )


def test_v2_payload_preserves_raw_rows_and_adds_episode_and_shadow_rows() -> None:
    """Catches opportunity reporting deleting raw audit evidence or becoming tradable."""
    first = _candidate(SIGNAL_START, "structure-first")
    second = _candidate(date(2026, 8, 4), "structure-second")
    episode = OpportunityEpisode(
        "episode-1",
        first,
        (SIGNAL_START, date(2026, 8, 4)),
        ("NEAR_MISS",),
    )
    review = replace(
        _review(
            outcomes=(
                CaseOutcome(
                    "600001",
                    SIGNAL_START,
                    "NEAR_MISS",
                    "CLOSED",
                    Decimal("0.06"),
                    Decimal("0.02"),
                    structure_id="structure-first",
                ),
                CaseOutcome(
                    "600001",
                    date(2026, 8, 4),
                    "NEAR_MISS",
                    "CLOSED",
                    Decimal("0.07"),
                    Decimal("0.02"),
                    structure_id="structure-second",
                ),
            )
        ),
        replay=CaseSignalReplay({}, (), (), (first, second)),
        episodes=(episode,),
        conditional_two_r_shadow=(
            ConditionalShadowOpportunity(
                "episode-1",
                first,
                Decimal("1.50"),
            ),
        ),
    )

    payload = case_payload(review)

    assert len(payload["candidates"]) == 2
    assert len(payload["outcomes"]) == 2
    assert payload["opportunity_episodes"] == [
        {
            "episode_id": "episode-1",
            "representative": {
                "code": "600001",
                "signal_date": "2026-08-03",
                "tier": "NEAR_MISS",
                "structure_id": "structure-first",
            },
            "member_signal_dates": ["2026-08-03", "2026-08-04"],
            "member_tiers": ["NEAR_MISS"],
            "outcome": payload["outcomes"][0],
        }
    ]
    assert payload["conditional_two_r_shadow"] == [
        {
            "episode_id": "episode-1",
            "code": "600001",
            "signal_date": "2026-08-03",
            "tier": "TWO_R_CONDITIONAL_SHADOW",
            "effective_resistance_r": "1.50",
            "executable_shares": 0,
        }
    ]
    assert payload["metrics"]["raw_candidates"] == 2
    assert payload["metrics"]["opportunity_episodes"] == 1
    assert payload["metrics"]["raw_outcome_successes"] == 2
    assert payload["metrics"]["episode_outcome_successes"] == 1
    assert payload["metrics"]["episode_outcome_resolved"] == 1
    assert payload["metrics"]["conditional_episodes"] == 1
    assert payload["metrics"]["conditional_outcome_resolved"] == 1
    assert payload["metrics"]["conditional_outcome_successes"] == 1
    markdown = render_case_markdown(review)
    assert "## 原始信号（可能重复）" in markdown
    assert "## 去重交易机会" in markdown
    assert "## 1.5R—2R 条件影子组" in markdown
    assert "CASE_ANALYSIS_ONLY" in markdown
    assert "NO-TRADE" in markdown
    assert "不能用于规则晋级或交易" in markdown


def test_episode_without_exact_outcome_is_not_counted_as_resolved() -> None:
    """Catches absent representative results being converted into failures."""
    candidate = _candidate(SIGNAL_START, "structure-first")
    review = replace(
        _review(outcomes=()),
        replay=CaseSignalReplay({}, (), (), (candidate,)),
        episodes=(
            OpportunityEpisode(
                "episode-1",
                candidate,
                (SIGNAL_START,),
                ("NEAR_MISS",),
            ),
        ),
    )

    metrics = case_payload(review)["metrics"]

    assert metrics["opportunity_episodes"] == 1
    assert metrics["episode_outcome_resolved"] == 0
    assert metrics["episode_outcome_successes"] == 0


def test_episode_metrics_summarize_only_representative_trades() -> None:
    """Catches raw duplicate outcomes contaminating episode execution statistics."""
    candidates = tuple(
        _candidate(
            SIGNAL_START,
            f"structure-{index}",
            code=f"60000{index}",
        )
        for index in range(1, 4)
    )
    episodes = tuple(
        OpportunityEpisode(
            f"episode-{index}",
            candidate,
            (SIGNAL_START,),
            ("NEAR_MISS",),
        )
        for index, candidate in enumerate(candidates, start=1)
    )
    outcomes = (
        CaseOutcome(
            "600001",
            SIGNAL_START,
            "NEAR_MISS",
            "CLOSED",
            Decimal("0.12"),
            Decimal("0.02"),
            trigger_date=date(2026, 8, 4),
            net_return=Decimal("0.10"),
            structure_id="structure-1",
        ),
        CaseOutcome(
            "600002",
            SIGNAL_START,
            "NEAR_MISS",
            "EXPIRED",
            None,
            None,
            structure_id="structure-2",
        ),
        CaseOutcome(
            "600003",
            SIGNAL_START,
            "NEAR_MISS",
            "CLOSED",
            Decimal("0.01"),
            Decimal("0.05"),
            trigger_date=date(2026, 8, 4),
            net_return=Decimal("-0.04"),
            stop_first=True,
            structure_id="structure-3",
        ),
    )
    review = replace(
        _review(outcomes=outcomes),
        replay=CaseSignalReplay({}, (), (), candidates),
        episodes=episodes,
    )

    metrics = case_payload(review)["metrics"]

    assert metrics["episode_triggered"] == 2
    assert metrics["episode_expired"] == 1
    assert metrics["episode_stop_first"] == 1
    assert metrics["episode_mean_net_return"] == "0.03"
    assert metrics["episode_mean_mfe"] == "0.065"
    assert metrics["episode_mean_mae"] == "0.035"


def test_incomplete_signal_dates_do_not_report_a_recall_fraction() -> None:
    """Catches incomplete traces being misreported as zero captured winners."""
    review = replace(
        _review(outcomes=()),
        replay=CaseSignalReplay({}, (SIGNAL_START,)),
    )

    assert "可买上涨股召回：不可计算（信号日数据不完整）" in render_case_markdown(
        review
    )


def test_later_cutoff_writes_a_new_immutable_revision(tmp_path) -> None:
    """Catches a partial snapshot being overwritten by a later outcome cutoff."""
    outcome = CaseOutcome(
        "600001", SIGNAL_START, "STRICT_SHADOW", "PENDING", None, None
    )

    early = write_case_revision(
        _review(outcomes=(outcome,), cutoff=date(2026, 8, 13)),
        tmp_path,
    )
    late = write_case_revision(
        _review(outcomes=(outcome,), cutoff=date(2026, 8, 14)),
        tmp_path,
    )

    assert early != late
    assert all(path.exists() for path in (*early, *late))
