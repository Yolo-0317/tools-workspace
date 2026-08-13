from __future__ import annotations

from datetime import date

from stock_ai.limit_up_research.attribution import (
    ExplainResult,
    StrategySnapshot,
    build_selection_attributions,
    explain_limit_up_gene_result,
)
from stock_ai.limit_up_logic import LimitUpPaths, LimitUpResult, LimitUpScoreBreakdown


DATE = date(2026, 8, 13)


def test_persisted_candidate_keeps_original_rank_and_score() -> None:
    result = build_selection_attributions(
        trade_date=DATE,
        limit_up_codes=("601991",),
        snapshots={
            "combined": StrategySnapshot(
                ran=True,
                rows=({"代码": "601991", "总分": 78, "建议动作": "强势关注"},),
                retained_limit=5,
            )
        },
        explainers={},
    )

    row = result[0]
    assert row.attribution == "SELECTED"
    assert row.selected is True
    assert (row.rank_no, row.score, row.action) == (1, 78.0, "强势关注")


def test_candidate_below_retained_limit_is_ranked_out() -> None:
    rows = tuple({"代码": f"60000{i}", "总分": 90 - i} for i in range(6))

    result = build_selection_attributions(
        trade_date=DATE,
        limit_up_codes=("600005",),
        snapshots={"combined": StrategySnapshot(ran=True, rows=rows, retained_limit=5)},
        explainers={},
    )

    assert result[0].attribution == "RANKED_OUT"
    assert result[0].rank_no == 6
    assert result[0].first_reason_code == "BELOW_RETAINED_LIMIT"


def test_missing_lane_and_missing_explainer_are_not_hard_rejections() -> None:
    result = build_selection_attributions(
        trade_date=DATE,
        limit_up_codes=("601991",),
        snapshots={
            "combined": StrategySnapshot(ran=False, rows=()),
            "five_factor": StrategySnapshot(ran=True, rows=()),
        },
        explainers={},
    )

    assert [row.attribution for row in result] == [
        "STRATEGY_NOT_RUN",
        "EXPLAINER_UNAVAILABLE",
    ]


def test_deterministic_explainer_supplies_ordered_hard_rejection() -> None:
    def explain(code: str) -> ExplainResult:
        assert code == "601991"
        return ExplainResult(
            attribution="HARD_REJECTED",
            reason_codes=("SIGNAL_DAY_TOO_HOT", "NOT_MATURE_CONSOLIDATION"),
            evidence={"pct_chg": 10.02, "max": 3.0},
            rule_version="gene-1",
        )

    result = build_selection_attributions(
        trade_date=DATE,
        limit_up_codes=("601991",),
        snapshots={"limit_up_gene_watch": StrategySnapshot(ran=True, rows=())},
        explainers={"limit_up_gene_watch": explain},
    )

    row = result[0]
    assert row.first_reason_code == "SIGNAL_DAY_TOO_HOT"
    assert row.reason_codes == ("SIGNAL_DAY_TOO_HOT", "NOT_MATURE_CONSOLIDATION")
    assert row.evidence["pct_chg"] == 10.02


def test_gene_explainer_reports_signal_day_too_hot_without_ai_text() -> None:
    result = LimitUpResult(
        code="601991", name="大唐发电", identity="NORMAL_TREND", gene="STRONG",
        score=LimitUpScoreBreakdown(30, 25, 0, 0), paths=LimitUpPaths(10, 60, 30),
        drivers=(), prerequisites=(), suppressors=(), missing_fields=(), data_cutoff=DATE,
        recent_limit_up_count=1, post_limit_support_broken=False, post_limit_shrink=True,
        consolidation_high=6.5, distance_to_consolidation_high=-0.02,
        latest_pct_chg=10.02, days_since_last_limit_up=12, return5=0.01,
        distance_from_last_limit_close=0.02,
    )

    explanation = explain_limit_up_gene_result(
        result, amount_wan=50_000, base_filter_passed=True
    )

    assert explanation is not None
    assert explanation.reason_codes[0] == "SIGNAL_DAY_TOO_HOT"
