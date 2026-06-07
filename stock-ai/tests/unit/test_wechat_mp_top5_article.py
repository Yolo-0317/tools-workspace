"""公众号 Top5 分析稿。"""

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
from scripts.tools.wechat_mp_top5_article import (
    generate_top5_trader_body,
    sanitize_top5_analysis_text,
    strip_top5_title_echo,
)


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
    assert "> 筛选名单" in body
    assert "一、筛选名单" not in body
    assert "> 个股拆解" in body
    assert "> 待验证事项" in body
    assert "逻辑归属" in body
    assert "待核实" in body
    assert "评分" not in body
    assert "观察为主" not in body
    assert "82分" not in body


def test_strip_top5_title_echo_removes_title_line() -> None:
    title = "锐科激光领衔5只！收盘信号出炉，明日盯啥？"
    body = (
        "> 筛选名单\n"
        f"{title}\n"
        "6月4日收盘后，5 只标的与当日主线相关。\n"
        "> 个股拆解\n"
        "1. 锐科激光（300747）"
    )
    out = strip_top5_title_echo(body, title=title)
    assert title not in out
    assert "6月4日收盘后" in out
    assert "> 筛选名单" in out


def test_sanitize_top5_strips_scores_and_opinions() -> None:
    raw = (
        "1. 测试股（000001）\n"
        "   地位：评分 82；建议 观察买入\n"
        "   结论：低吸试错\n"
        "   量价结构：换手放大。"
    )
    out = sanitize_top5_analysis_text(raw)
    assert "评分" not in out
    assert "观察买入" not in out
    assert "结论" not in out
    assert "量价结构" in out


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
