"""sector evening 同批去重：关 Top10 表、避开 news 头条票。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_hot_stocks import HotStockRow
from scripts.tools.wechat_mp_sector_stocks import (
    collect_sector_sample_stocks,
    news_hot_exclude_codes,
    pick_hot_stock_for_sector_title,
    sector_evening_dedup_enabled,
    sector_hot_watch_top_n,
)


def test_sector_evening_dedup_defaults_from_news_batch(monkeypatch) -> None:
    monkeypatch.delenv("WECHAT_MP_SECTOR_EVENING_DEDUP", raising=False)
    monkeypatch.setenv("WECHAT_MP_NEWS_BATCH", "evening")
    assert sector_evening_dedup_enabled() is True
    monkeypatch.setenv("WECHAT_MP_NEWS_BATCH", "weekend")
    assert sector_evening_dedup_enabled() is False


def test_sector_hot_watch_top_n_zero_when_evening_dedup(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_SECTOR_EVENING_DEDUP", "1")
    monkeypatch.delenv("WECHAT_MP_SECTOR_HOT_WATCH_TOP_N", raising=False)
    assert sector_hot_watch_top_n() == 0
    monkeypatch.setenv("WECHAT_MP_SECTOR_HOT_WATCH_TOP_N", "5")
    assert sector_hot_watch_top_n() == 5


def test_collect_sector_sample_stocks_excludes_news_hot_codes() -> None:
    board_rows = [
        {
            "sector": "半导体",
            "sector_chg": 3.2,
            "leader_name": "工业富联",
            "leader_chg": 7.5,
            "code": "601138",
        },
        {
            "sector": "半导体",
            "sector_chg": 3.2,
            "leader_name": "北方华创",
            "leader_chg": 5.1,
            "code": "002371",
        },
    ]
    stocks = collect_sector_sample_stocks(
        ["半导体"],
        board_rows=board_rows,
        hot_rows=[],
        industry_map={},
        exclude_codes={"601138"},
    )
    codes = [s.code for s in stocks]
    assert "601138" not in codes
    assert "002371" in codes


def test_pick_hot_stock_for_sector_title_skips_excluded() -> None:
    rows = [
        HotStockRow(1, "601138", "工业富联", 7.5),
        HotStockRow(2, "603986", "兆易创新", 7.3),
    ]
    assert pick_hot_stock_for_sector_title(rows, exclude_codes={"601138"}) == "兆易创新"


def test_apply_batch_env_evening_sets_sector_dedup(monkeypatch) -> None:
    from scripts.tools.wechat_mp_draft_batch import _apply_batch_env

    monkeypatch.delenv("WECHAT_MP_SECTOR_EVENING_DEDUP", raising=False)
    monkeypatch.delenv("WECHAT_MP_SECTOR_HOT_WATCH_TOP_N", raising=False)
    _apply_batch_env("evening")
    assert os.environ.get("WECHAT_MP_SECTOR_EVENING_DEDUP") == "1"
    assert os.environ.get("WECHAT_MP_SECTOR_HOT_WATCH_TOP_N") == "0"


def test_news_hot_exclude_codes_reads_top_n(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_MP_SECTOR_EVENING_DEDUP", "1")
    monkeypatch.setenv("WECHAT_MP_SECTOR_EXCLUDE_NEWS_HOT_N", "2")

    def fake_rows(*, top_n: int):
        return [
            HotStockRow(1, "601138", "工业富联", 7.5),
            HotStockRow(2, "603986", "兆易创新", 7.3),
            HotStockRow(3, "600667", "太极实业", 10.0),
        ][:top_n]

    monkeypatch.setattr(
        "scripts.tools.wechat_mp_hot_stocks.fetch_hot_stock_rows",
        fake_rows,
    )
    assert news_hot_exclude_codes() == {"601138", "603986"}
