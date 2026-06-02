"""公众号 Top5 交易员成稿。"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.selection_watchlist import SelectionPick
from scripts.tools.wechat_mp_sop_fast import TOP5_SOP_PROFILE, load_sop_cache, save_sop_cache
from scripts.tools.wechat_mp_top5_article import generate_top5_trader_body


def _picks() -> list[SelectionPick]:
    return [
        SelectionPick(
            code="000001",
            name="平安银行",
            close=10.5,
            change_pct=1.2,
            score=82,
            label="趋势",
            action="观察",
            in_holdings=False,
        )
    ]


@patch("scripts.tools.wechat_mp_top5_article.is_llm_configured", return_value=False)
@patch("scripts.tools.wechat_mp_top5_article.collect_wechat_sop_packs", return_value=[])
def test_generate_top5_template(_mock_sop, _mock_llm) -> None:
    body = generate_top5_trader_body(_picks(), trade_date=date(2026, 6, 2))
    assert "一、观察名单" in body
    assert "二、个股拆解" in body
    assert "四、次日跟踪" in body


def test_top5_cache_isolated(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_sop_fast.ROOT",
        tmp_path,
    )
    profile = TOP5_SOP_PROFILE
    save_sop_cache(profile, "000001", "2026-06-02", "快采", "MA5")
    hit = load_sop_cache(profile, "000001", "2026-06-02")
    assert hit is not None
    assert (tmp_path / "output" / "wechat_mp_top5_sop" / "2026-06-02" / "000001_fast.md").is_file()
