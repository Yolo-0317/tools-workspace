"""晚间三篇主线对齐 + 标题优化。"""

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
from scripts.tools.wechat_mp_content import _dragon_title, _top5_title
from scripts.tools.wechat_mp_dragons_article import dragons_write_max
from scripts.tools.wechat_mp_dragons_polish import inject_dragons_opening_lede
from scripts.tools.wechat_mp_evening_align import dragons_title_phase_label


def test_dragons_title_phase_label() -> None:
    assert dragons_title_phase_label("退潮") == "情绪退潮"
    assert dragons_title_phase_label("启动") == "情绪启动"


def test_dragon_title_prefers_souyisou_pattern() -> None:
    hdr = {"phase": "退潮", "main_theme": "电力"}
    dragons = [
        {
            "ts_code": "000001.SZ",
            "name": "粤电力Ａ",
            "board_height": 4,
        }
    ]
    title = _dragon_title(hdr, dragons, trade_date=date(2026, 6, 3))
    assert "怎么玩" in title
    assert "还在榜" in title or "？" in title
    assert "粤电力" in title or "电力" in title


def test_top5_title_leading_stock_first() -> None:
    picks = [
        SelectionPick(
            code="600160",
            name="巨化股份",
            close=1.0,
            change_pct=1.0,
            score=1.0,
            label="x",
            action="",
            in_holdings=False,
        ),
        SelectionPick(
            code="600161",
            name="其他",
            close=1.0,
            change_pct=1.0,
            score=1.0,
            label="x",
            action="",
            in_holdings=False,
        ),
    ]
    title = _top5_title(picks, trade_date=date(2026, 6, 3))
    assert "巨化股份" in title and ("领衔" in title or "A股选股" in title)


def test_dragons_write_max_default_two() -> None:
    assert dragons_write_max() == 2


@patch("scripts.tools.wechat_mp_top5_article.is_llm_configured", return_value=False)
@patch("scripts.tools.wechat_mp_top5_article.collect_wechat_sop_packs", return_value=[])
@patch(
    "scripts.tools.wechat_mp_evening_align.sector_primary_label",
    return_value="动力煤",
)
def test_top5_template_mentions_sector_primary(_m1, _m2, _m3) -> None:
    from scripts.tools.wechat_mp_top5_article import generate_top5_trader_body

    picks = [
        SelectionPick(
            code="000001",
            name="测试股",
            close=10.0,
            change_pct=1.0,
            score=1.0,
            label="趋势",
            action="",
            in_holdings=False,
        )
    ]
    body = generate_top5_trader_body(picks, trade_date=date(2026, 6, 3))
    assert "动力煤" in body


def test_inject_dragons_opening_lede() -> None:
    hdr = {
        "phase": "冰点",
        "main_theme": "动力煤",
        "limit_up_count": 40,
        "limit_down_count": 10,
        "explode_rate_pct": 35,
        "up_down_ratio": "0.9",
    }
    body = "> 情绪与盘面\n\n盘面定性：情绪一般。\n"
    out = inject_dragons_opening_lede(body, hdr=hdr)
    assert "炸板率" in out
    assert "涨停40" in out or "涨停40/" in out or "40/跌停" in out
