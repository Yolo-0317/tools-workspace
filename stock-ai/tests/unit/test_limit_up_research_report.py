from __future__ import annotations

from datetime import date, datetime

from stock_ai.limit_up_research.models import ForwardLabel, SelectionAttribution, normalize_topic_pools
from stock_ai.limit_up_research.report import build_research_report


def test_report_aggregates_ladder_coverage_and_reasons_without_trade_action() -> None:
    td = date(2026, 8, 13)
    snapshot = normalize_topic_pools(
        {
            "zt": [
                {"c": "601991", "n": "大唐发电", "lbc": 2, "hybk": "电力"},
                {"c": "600821", "n": "金开新能", "lbc": 1, "hybk": "电力"},
            ],
            "zb": [{"c": "600001", "n": "测试炸板"}],
            "dt": [],
        },
        td,
    )
    attributions = (
        SelectionAttribution(td, "601991", "combined", True, 1, 80, "关注", "SELECTED", None, (), {}, "v1"),
        SelectionAttribution(td, "600821", "combined", False, None, None, None, "HARD_REJECTED", "BASE_FILTER_FAILED", ("BASE_FILTER_FAILED",), {}, "v1"),
    )
    labels = (
        ForwardLabel(td, "601991", "T1", date(2026, 8, 14), 6.0, 6.6, 10.0, 10.0, 0.0, True, 3, True, ()),
    )

    payload, markdown = build_research_report(
        run_id=9,
        snapshot=snapshot,
        attributions=attributions,
        labels=labels,
        selection_date=date(2026, 8, 12),
        data_cutoff=datetime(2026, 8, 13, 15, 10),
    )

    assert payload["counts"] == {"LIMIT_UP": 2, "EXPLODED": 1, "LIMIT_DOWN": 0}
    assert payload["board_ladder"] == {"1": ["600821 金开新能"], "2": ["601991 大唐发电"]}
    assert payload["board_summary"] == {"first_board": 1, "multi_board": 1, "max_height": 2}
    assert payload["strategy_coverage"]["combined"] == {"selected": 1, "total": 2, "rate": 0.5}
    assert payload["miss_reasons"] == {"BASE_FILTER_FAILED": 1}
    assert payload["label_summary"]["T1"] == {"total": 1, "complete": 1}
    assert payload["selection_date"] == "2026-08-12"
    assert "归因基准日：2026-08-12" in markdown
    assert "首板：1；二板及以上：1；最高：2板" in markdown
    assert "T1：1 条（完整 1）" in markdown
    assert "买入" not in markdown
    assert "仓位" not in markdown
