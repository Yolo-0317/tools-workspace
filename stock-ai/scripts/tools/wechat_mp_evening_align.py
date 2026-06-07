#!/usr/bin/env python3
"""晚间三篇对齐：sector 东财行业榜 → top5 / dragons 同日引用（非龙头池主线）。"""

from __future__ import annotations

from scripts.tools.wechat_mp_hot_theme import (
    discover_sector_hot_themes,
    pick_focus_themes,
)
from scripts.tools.wechat_mp_sector_article import sector_title_hook


def dragons_title_phase_label(phase: str) -> str:
    """搜一搜友好：情绪阶段带「情绪」前缀。"""
    p = str(phase or "").strip()
    if not p:
        return "情绪"
    if p.startswith("情绪"):
        return p
    return f"情绪{p}"


def evening_focus_themes(*, edition: str = "close"):
    """与行业研究稿相同：东财行业板块榜排名。"""
    report = discover_sector_hot_themes(edition=edition)
    return pick_focus_themes(report, edition=edition)


def sector_primary_label(*, edition: str = "close") -> str:
    return discover_sector_hot_themes(edition=edition).primary


def sector_alignment_prompt_block(*, edition: str = "close") -> str:
    """注入 top5 / dragons LLM prompt。"""
    report = discover_sector_hot_themes(edition=edition)
    themes = report.themes[:2]
    if not themes:
        return ""
    from scripts.tools.wechat_mp_sector_article import (
        format_sector_trade_label,
        resolve_sector_trade_date,
    )

    day_label = format_sector_trade_label(
        resolve_sector_trade_date(report), edition=report.edition
    )
    primary = themes[0].name
    hook = sector_title_hook(themes)
    secondary = themes[1].name if len(themes) > 1 else ""
    sec_line = f"；榜二 {secondary}" if secondary else ""
    board_note = (
        "eastmoney_industry_board"
        if "eastmoney_industry_board" in (themes[0].sources or [])
        else (themes[0].sources[0] if themes[0].sources else "行业榜")
    )
    return f"""
## {day_label} 行业主线（东财行业板块涨幅榜前列，与 sector 行业稿一致）
数据日：{report.trade_date}。榜一：{primary}{sec_line}（钩子：{hook}；来源 {board_note}）
- 每只/每段分析须点明与「{primary}」的关系：同属产业链、分化、或仅个股独立逻辑
- **勿**用情绪周期龙头池主线替代行业榜；龙头稿标题可保留个股，但逻辑归属应呼应榜一行业
"""
