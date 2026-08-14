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
from stock_ai.buy_point_selection.resistance_research import (
    LEGACY_ANY_HIGH,
    LOCAL_PIVOT_HIGH,
    REPEATED_PIVOT_CLUSTER,
    ResistanceVariantProfile,
    SignificantResistanceProfile,
)


SIGNAL_START = date(2026, 8, 3)
SIGNAL_END = date(2026, 8, 7)


def _candidate(
    signal_date: date,
    structure_id: str,
    *,
    code: str = "600001",
    setup_type: SetupType = SetupType.TREND_PULLBACK,
) -> CaseCandidate:
    setup = DetectedSetup(
        code,
        setup_type,
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


def test_v4_schema_participates_in_immutable_case_identity() -> None:
    """Catches a v4 report colliding with an existing immutable revision."""
    review = _review(outcomes=())

    payload = case_payload(review)

    assert payload["schema"] == "buy-point-case-review-v4"
    assert case_identity(
        review,
        schema="buy-point-case-review-v3",
    ) != case_identity(
        review,
        schema="buy-point-case-review-v4",
    )


def test_v4_payload_serializes_resistance_evidence() -> None:
    candidate = _candidate(SIGNAL_START, "structure-first")
    review = replace(
        _review(outcomes=()),
        episodes=(
            OpportunityEpisode(
                "episode-1",
                candidate,
                (SIGNAL_START,),
                (candidate.tier,),
            ),
        ),
        resistance_profiles=(
            SignificantResistanceProfile(
                "episode-1",
                candidate.code,
                candidate.signal_date,
                candidate.plan.structure_id,
                candidate.setup.setup_type.value,
                Decimal("0.20"),
                Decimal("0.10"),
                True,
                (
                    ResistanceVariantProfile(
                        LEGACY_ANY_HIGH,
                        Decimal("10.20"),
                        Decimal("0.20"),
                        False,
                        1,
                    ),
                    ResistanceVariantProfile(
                        LOCAL_PIVOT_HIGH,
                        Decimal("12.20"),
                        Decimal("2.20"),
                        True,
                        1,
                    ),
                    ResistanceVariantProfile(
                        REPEATED_PIVOT_CLUSTER,
                        None,
                        None,
                        True,
                        0,
                    ),
                ),
            ),
        ),
    )

    payload = case_payload(review)

    assert payload["resistance_profiles"][0]["variants"][0] == {
        "variant": "LEGACY_ANY_HIGH",
        "level": "10.20",
        "effective_resistance_r": "0.20",
        "passes_two_r": False,
        "touch_count": 1,
        "evidence_basis": "LEVEL_BELOW_2R",
    }
    assert payload["resistance_profiles"][0]["variants"][2][
        "evidence_basis"
    ] == "NO_LEVEL"
    assert {
        "candidates",
        "outcomes",
        "opportunity_episodes",
        "conditional_two_r_shadow",
        "resistance_profiles",
        "resistance_comparison",
        "metrics",
    } <= payload.keys()


def test_resistance_comparison_uses_only_passing_exact_representatives() -> None:
    first = _candidate(
        SIGNAL_START,
        "structure-first",
        code="600001",
        setup_type=SetupType.FIRST_LAUNCH_PULLBACK,
    )
    second = _candidate(
        SIGNAL_START,
        "structure-second",
        code="600002",
        setup_type=SetupType.FIRST_LAUNCH_PULLBACK,
    )
    trend = _candidate(
        SIGNAL_START,
        "structure-trend",
        code="600003",
        setup_type=SetupType.TREND_PULLBACK,
    )

    def profile(episode_id: str, candidate: CaseCandidate) -> SignificantResistanceProfile:
        return SignificantResistanceProfile(
            episode_id,
            candidate.code,
            candidate.signal_date,
            candidate.plan.structure_id,
            candidate.setup.setup_type.value,
            Decimal("0.20"),
            Decimal("0.10"),
            True,
            (
                ResistanceVariantProfile(
                    LEGACY_ANY_HIGH, Decimal("10.20"), Decimal("0.20"), False, 1
                ),
                ResistanceVariantProfile(
                    LOCAL_PIVOT_HIGH, Decimal("12.20"), Decimal("2.20"), True, 1
                ),
                ResistanceVariantProfile(
                    REPEATED_PIVOT_CLUSTER,
                    Decimal("12.15"),
                    Decimal("2.15"),
                    True,
                    2,
                ),
            ),
        )

    candidates = (first, second, trend)
    episodes = tuple(
        OpportunityEpisode(
            f"episode-{index}",
            candidate,
            (candidate.signal_date,),
            (candidate.tier,),
        )
        for index, candidate in enumerate(candidates, start=1)
    )
    outcomes = (
        CaseOutcome(
            first.code,
            first.signal_date,
            first.tier,
            "CLOSED",
            Decimal("0.09"),
            Decimal("0.02"),
            trigger_date=date(2026, 8, 4),
            net_return=Decimal("0.06"),
            structure_id=first.plan.structure_id,
        ),
        CaseOutcome(
            second.code,
            second.signal_date,
            second.tier,
            "EXPIRED",
            None,
            None,
            structure_id=second.plan.structure_id,
        ),
        CaseOutcome(
            trend.code,
            trend.signal_date,
            trend.tier,
            "CLOSED",
            Decimal("0.02"),
            Decimal("0.08"),
            trigger_date=date(2026, 8, 4),
            net_return=Decimal("-0.05"),
            stop_first=True,
            structure_id=trend.plan.structure_id,
        ),
    )
    review = replace(
        _review(outcomes=outcomes),
        episodes=episodes,
        resistance_profiles=tuple(
            profile(episode.episode_id, episode.representative)
            for episode in episodes
        ),
    )

    payload = case_payload(review)
    comparison = {
        (value.pop("setup_type"), value.pop("variant")): value
        for value in payload["resistance_comparison"]
    }

    assert comparison[("FIRST_LAUNCH_PULLBACK", LOCAL_PIVOT_HIGH)] == {
        "complete_profiles": 2,
        "variant_passes": 2,
        "triggered": 1,
        "resolved": 2,
        "successes": 1,
        "stop_first": 0,
        "mean_net_return": "0.06",
        "mean_mfe": "0.09",
        "mean_mae": "0.02",
        "codes": ["600001", "600002"],
        "episode_ids": ["episode-1", "episode-2"],
    }
    assert comparison[("TREND_PULLBACK", LOCAL_PIVOT_HIGH)] == {
        "complete_profiles": 1,
        "variant_passes": 1,
        "triggered": 1,
        "resolved": 1,
        "successes": 0,
        "stop_first": 1,
        "mean_net_return": "-0.05",
        "mean_mfe": "0.02",
        "mean_mae": "0.08",
        "codes": ["600003"],
        "episode_ids": ["episode-3"],
    }
    markdown = render_case_markdown(review)
    assert "## 显著阻力影子对照" in markdown
    assert "假设通过仅用于研究，不能生成正式计划" in markdown
    assert "CASE_ANALYSIS_ONLY" in markdown
    assert "NO-TRADE" in markdown


def test_resistance_evidence_comparison_does_not_mix_no_level_passes() -> None:
    """Catches absent resistance being reported as observed 2R resistance."""
    level_candidate = _candidate(
        SIGNAL_START,
        "structure-level",
        code="600001",
        setup_type=SetupType.FIRST_LAUNCH_PULLBACK,
    )
    absent_candidate = _candidate(
        SIGNAL_START,
        "structure-absent",
        code="600002",
        setup_type=SetupType.FIRST_LAUNCH_PULLBACK,
    )
    episodes = (
        OpportunityEpisode(
            "episode-level",
            level_candidate,
            (SIGNAL_START,),
            (level_candidate.tier,),
        ),
        OpportunityEpisode(
            "episode-absent",
            absent_candidate,
            (SIGNAL_START,),
            (absent_candidate.tier,),
        ),
    )

    def profile(
        episode_id: str,
        candidate: CaseCandidate,
        repeated_level: Decimal | None,
    ) -> SignificantResistanceProfile:
        repeated = (
            ResistanceVariantProfile(
                REPEATED_PIVOT_CLUSTER,
                None,
                None,
                True,
                0,
            )
            if repeated_level is None
            else ResistanceVariantProfile(
                REPEATED_PIVOT_CLUSTER,
                repeated_level,
                Decimal("2.20"),
                True,
                2,
            )
        )
        return SignificantResistanceProfile(
            episode_id,
            candidate.code,
            candidate.signal_date,
            candidate.plan.structure_id,
            candidate.setup.setup_type.value,
            Decimal("0.20"),
            Decimal("0.10"),
            True,
            (
                ResistanceVariantProfile(
                    LEGACY_ANY_HIGH, Decimal("10.20"), Decimal("0.20"), False, 1
                ),
                ResistanceVariantProfile(
                    LOCAL_PIVOT_HIGH, Decimal("10.40"), Decimal("0.40"), False, 1
                ),
                repeated,
            ),
        )

    review = replace(
        _review(
            outcomes=(
                CaseOutcome(
                    level_candidate.code,
                    level_candidate.signal_date,
                    level_candidate.tier,
                    "CLOSED",
                    Decimal("0.09"),
                    Decimal("0.02"),
                    trigger_date=date(2026, 8, 4),
                    net_return=Decimal("0.06"),
                    structure_id=level_candidate.plan.structure_id,
                ),
                CaseOutcome(
                    absent_candidate.code,
                    absent_candidate.signal_date,
                    absent_candidate.tier,
                    "EXPIRED",
                    None,
                    None,
                    structure_id=absent_candidate.plan.structure_id,
                ),
            )
        ),
        episodes=episodes,
        resistance_profiles=(
            profile("episode-level", level_candidate, Decimal("12.20")),
            profile("episode-absent", absent_candidate, None),
        ),
    )

    payload = case_payload(review)
    rows = {
        (value["setup_type"], value["variant"], value["evidence_basis"]): value
        for value in payload["resistance_evidence_comparison"]
    }
    level_row = rows[
        (
            "FIRST_LAUNCH_PULLBACK",
            REPEATED_PIVOT_CLUSTER,
            "LEVEL_AT_OR_ABOVE_2R",
        )
    ]
    no_level_row = rows[
        ("FIRST_LAUNCH_PULLBACK", REPEATED_PIVOT_CLUSTER, "NO_LEVEL")
    ]

    assert level_row["complete_profiles"] == 2
    assert level_row["cohort_opportunities"] == 1
    assert level_row["triggered"] == 1
    assert level_row["resolved"] == 1
    assert level_row["successes"] == 1
    assert level_row["mean_net_return"] == "0.06"
    assert level_row["codes"] == ["600001"]
    assert no_level_row["complete_profiles"] == 2
    assert no_level_row["cohort_opportunities"] == 1
    assert no_level_row["triggered"] == 0
    assert no_level_row["resolved"] == 1
    assert no_level_row["successes"] == 0
    assert no_level_row["mean_net_return"] is None
    assert no_level_row["codes"] == ["600002"]
    markdown = render_case_markdown(review)
    assert "## 显著阻力证据拆分" in markdown
    assert "未发现阻力不等于已证明上涨空间" in markdown
    assert "CASE_ANALYSIS_ONLY" in markdown
    assert "NO-TRADE" in markdown


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
