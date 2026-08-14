from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

from stock_ai.buy_point_selection.case_report import (
    case_payload,
    render_case_markdown,
    write_case_revision,
)
from stock_ai.buy_point_selection.case_review import (
    BuyableWinner,
    CaseOutcome,
    CaseReview,
    CaseSignalReplay,
)


SIGNAL_START = date(2026, 8, 3)
SIGNAL_END = date(2026, 8, 7)


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
