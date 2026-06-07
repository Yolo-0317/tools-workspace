"""Top5 完读钩子后处理。"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.tools.selection_watchlist import SelectionPick
from scripts.tools.wechat_mp_top5_polish import (
    finalize_top5_body,
    inject_stock_transition_hooks,
    inject_top5_opening_hook,
)


def _picks() -> list[SelectionPick]:
    return [
        SelectionPick(
            code="300747",
            name="锐科激光",
            close=25.0,
            change_pct=3.1,
            score=80,
            label="趋势",
            action="观察",
        ),
        SelectionPick(
            code="002258",
            name="新安股份",
            close=10.0,
            change_pct=1.2,
            score=75,
            label="突破",
            action="观察",
        ),
    ]


def _minimal_body() -> str:
    return (
        "> 筛选名单\n"
        "数据日 2026-06-04。\n"
        "\n"
        "> 个股拆解\n"
        "1. 锐科激光（300747）\n"
        "   逻辑归属：测试\n"
        "2. 新安股份（002258）\n"
        "   逻辑归属：测试\n"
        "\n"
        "> 组合特征\n"
        "五只分布说明。\n"
        "\n"
        "> 待验证事项\n"
        "核对量能。\n"
    )


def test_inject_opening_hook_when_section_thin() -> None:
    out = inject_top5_opening_hook(
        _minimal_body(),
        _picks(),
        trade_date=date(2026, 6, 4),
        sector_primary="化工",
    )
    assert "逐只" in out
    assert "往下看" not in out
    assert "化工" in out


def test_inject_transitions_between_stocks() -> None:
    out = inject_stock_transition_hooks(_minimal_body())
    assert out.count("·") >= 1
    assert "往下看" not in out
    assert "2. 新安股份" in out


def test_finalize_top5_adds_closing_suspense() -> None:
    out = finalize_top5_body(
        _minimal_body(),
        _picks(),
        trade_date=date(2026, 6, 4),
        sector_primary="化工",
    )
    assert "若" in out and "露馅" in out
    assert "组合特征" in out
