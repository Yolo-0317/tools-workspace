"""投顾周五周复盘 — 单元测试（无 MySQL）。"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from stock_ai.advisor_weekly_review import (
    build_weekly_review_report,
    public_weekly_review_row,
    save_weekly_review,
)


@pytest.fixture
def mock_portfolio(monkeypatch):
    acct = MagicMock(
        total_assets=52000.0,
        position_ratio=0.82,
        holding_pnl=-1200.0,
        available_cash=8000.0,
    )
    pos = MagicMock(code="600519", name="贵州茅台", shares=100, cost=1800.0)

    monkeypatch.setattr(
        "scripts.tools.portfolio_db.load_account",
        lambda: acct,
        raising=False,
    )
    monkeypatch.setattr(
        "scripts.tools.portfolio_db.load_positions",
        lambda: [pos],
        raising=False,
    )
    monkeypatch.setattr(
        "scripts.tools.portfolio_db.load_latest_closes",
        lambda codes: {"600519": 1750.0},
        raising=False,
    )
    monkeypatch.setattr(
        "stock_ai.advisor_weekly_review._week_account_stats",
        lambda end: {
            "week_start": "2026-05-26",
            "week_end": "2026-06-01",
            "assets_start": 51000.0,
            "assets_end": 52000.0,
            "assets_delta": 1000.0,
            "assets_delta_pct": 1.96,
            "position_start_pct": 84.0,
            "position_end_pct": 82.0,
            "position_delta_pp": -2.0,
            "snapshots": 5,
        },
    )


def test_build_weekly_review_report(mock_portfolio):
    report = build_weekly_review_report(review_date=date(2026, 6, 1), with_ai=False)
    assert report["week_end_date"] == "2026-06-01"
    assert report["phase"] >= 0
    assert "周复盘" in report["title"]
    assert "投顾交付摘要" in report["report_md"]
    assert "本周必做对照" in report["report_md"]
    assert report["report_json"]["week_stats"]["assets_delta"] == 1000.0


def test_public_weekly_review_row_strips_json():
    row = {
        "week_end_date": "2026-06-01",
        "phase": 0,
        "title": "2026年第22周复盘",
        "health_score": 62,
        "report_md": "# hello",
        "report_json": {"week_stats": {"assets_delta": 100}, "ai_summary": "小结"},
        "created_at": "2026-06-01 20:30:00",
    }
    pub = public_weekly_review_row(row)
    assert pub["ai_summary"] == "小结"
    assert pub["week_stats"]["assets_delta"] == 100
    assert "report_json" not in pub


def test_save_weekly_review_calls_db(mock_portfolio, monkeypatch):
    saved = {}

    def _save(**kwargs):
        saved.update(kwargs)

    monkeypatch.setattr(
        "scripts.tools.portfolio_db.save_advisor_weekly_review",
        _save,
        raising=False,
    )
    report = build_weekly_review_report(review_date=date(2026, 6, 1), with_ai=False)
    save_weekly_review(report)
    assert saved["week_end_date"] == date(2026, 6, 1)
    assert saved["report_md"]
    assert saved["report_json"]["week_end_date"] == "2026-06-01"
