from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.analysis.merge_dual_pool_selection import run_dual_pool_selection
from stock_ai.news_impact import NewsEvent
from stock_ai.news_impact.providers import NewsCoverage


NOW = datetime(2026, 8, 12, 18, 0, tzinfo=timezone(timedelta(hours=8)))


def _event() -> NewsEvent:
    return NewsEvent(
        event_id="coreweave-capex",
        title="CoreWeave上调资本开支",
        summary="AI云厂商提高数据中心资本开支",
        published_at=NOW - timedelta(hours=2),
        observed_at=NOW,
        source_url="https://example.com/coreweave",
        source_name="公司官网",
        source_tier="official",
        market="US",
        country="US",
        subjects=("CoreWeave",),
        event_type="capex",
        direction="positive",
        confirmation_state="official",
        scope="overseas",
        evidence="资本开支上调",
    )


def test_run_writes_enriched_csv_and_non_actionable_event_watch_lane(tmp_path, monkeypatch):
    technical = pd.DataFrame(
        [
            {
                "代码": "003816",
                "名称": "中国广核",
                "所属行业": "电力",
                "总分": 72,
                "建议动作": "继续观察",
            }
        ]
    )
    saved: dict[str, list[dict[str, object]]] = {}

    monkeypatch.setattr(
        "scripts.analysis.merge_dual_pool_selection.merge_selection_strategies_df",
        lambda **_kwargs: (date(2026, 8, 12), technical, "merge[combined]"),
    )
    monkeypatch.setattr(
        "scripts.analysis.merge_dual_pool_selection.load_news_coverage",
        lambda **_kwargs: NewsCoverage((_event(),), ("verified_cache",), (), NOW),
    )

    def fake_save(_trade_date, rows, *, strategy):
        saved[strategy] = list(rows)
        return len(rows)

    monkeypatch.setattr(
        "scripts.analysis.merge_dual_pool_selection.save_selection_daily_results",
        fake_save,
    )
    output = tmp_path / "dual-pool.csv"

    summary = run_dual_pool_selection(
        trade_date=date(2026, 8, 12),
        output_path=output,
        write_db=True,
        now=NOW,
    )

    frame = pd.read_csv(output, encoding="utf-8-sig", dtype={"代码": str})
    assert list(frame["代码"]) == ["003816"]
    assert frame.iloc[0]["候选池来源"] == "technical"
    assert summary.event_watch_count > 0
    assert "dual_pool" in saved
    assert "news_event_watch" in saved
    assert all(row["建议动作"] == "消息观察，等待技术确认" for row in saved["news_event_watch"])
    assert all(row["交易资格"] == "无技术信号，不进入可执行Top5" for row in saved["news_event_watch"])


def test_no_db_mode_does_not_persist(tmp_path, monkeypatch):
    technical = pd.DataFrame([{"代码": "003816", "名称": "中国广核", "总分": 72}])
    monkeypatch.setattr(
        "scripts.analysis.merge_dual_pool_selection.merge_selection_strategies_df",
        lambda **_kwargs: (date(2026, 8, 12), technical, "merge[combined]"),
    )
    monkeypatch.setattr(
        "scripts.analysis.merge_dual_pool_selection.load_news_coverage",
        lambda **_kwargs: NewsCoverage((), (), ("overseas_company",), NOW),
    )

    def fail_save(*_args, **_kwargs):
        raise AssertionError("--no-db must not persist")

    monkeypatch.setattr(
        "scripts.analysis.merge_dual_pool_selection.save_selection_daily_results",
        fail_save,
    )

    summary = run_dual_pool_selection(
        output_path=tmp_path / "no-db.csv",
        write_db=False,
        now=NOW,
    )

    assert summary.technical_count == 1
    assert summary.coverage_status == "不足"
