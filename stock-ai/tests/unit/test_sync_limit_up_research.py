from __future__ import annotations

from datetime import date, datetime
import inspect

import pytest

from scripts.analysis import sync_limit_up_research
from scripts.analysis.sync_limit_up_research import run_pipeline
from scripts.tools.selection_results import wechat_top5_strategies
from stock_ai.limit_up_research.attribution import StrategySnapshot


def test_pipeline_collects_persists_and_writes_same_date_reports(tmp_path) -> None:
    calls = []
    td = date(2026, 8, 13)
    top5_before = wechat_top5_strategies()

    result = run_pipeline(
        trade_date=td,
        selection_date=date(2026, 8, 12),
        output_dir=tmp_path,
        collector=lambda value: calls.append(("collect", value)) or {
            "zt": [{"c": "601991", "n": "大唐发电", "lbc": 2}], "zb": [], "dt": []
        },
        start_run=lambda value: calls.append(("start", value)) or 7,
        load_snapshots=lambda value: calls.append(("snapshots", value)) or {
            "combined": StrategySnapshot(ran=True, rows=({"代码": "601991", "总分": 80},), retained_limit=5)
        },
        load_labels=lambda facts: calls.append(
            ("labels", tuple(item.code for item in facts if item.pool_kind == "LIMIT_UP"))
        ) or (),
        save_bundle=lambda *args: calls.append(("save", args[0])) or {"pool": 1, "attributions": 1, "labels": 0},
        finish_run=lambda *args, **kwargs: calls.append(("finish", kwargs["status"])),
        now=lambda: datetime(2026, 8, 13, 15, 10),
    )

    assert result["run_id"] == 7
    assert (tmp_path / "2026-08-13.json").is_file()
    assert (tmp_path / "2026-08-13.md").is_file()
    assert [item[0] for item in calls] == [
        "start", "collect", "snapshots", "labels", "save", "finish"
    ]
    assert calls[2] == ("snapshots", date(2026, 8, 12))
    assert calls[3] == ("labels", ("601991",))
    assert wechat_top5_strategies() == top5_before


def test_collection_failure_records_failed_run_without_bundle_or_report(tmp_path) -> None:
    calls = []

    def fail(_):
        raise RuntimeError("eastmoney unavailable")

    with pytest.raises(RuntimeError, match="eastmoney unavailable"):
        run_pipeline(
            trade_date=date(2026, 8, 13),
            selection_date=date(2026, 8, 12),
            output_dir=tmp_path,
            collector=fail,
            start_run=lambda value: 8,
            load_snapshots=lambda value: {},
            load_labels=lambda facts: (),
            save_bundle=lambda *args: calls.append("save"),
            finish_run=lambda *args, **kwargs: calls.append(kwargs["status"]),
            now=lambda: datetime(2026, 8, 13, 15, 10),
        )

    assert calls == ["FAILED"]
    assert list(tmp_path.iterdir()) == []


def test_manual_entry_is_isolated_from_deprecated_diagnosis_and_schedulers() -> None:
    source = inspect.getsource(sync_limit_up_research)

    assert "eastmoney_sop_extract" not in source
    assert "eight_dimension" not in source
    assert "fetch_emotion_topic_pools_opencli" in source
    assert "cron" not in source
    assert "launchd" not in source
