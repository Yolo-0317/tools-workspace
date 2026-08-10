#!/usr/bin/env python3
"""行业稿完读钩子。"""

from __future__ import annotations

import re
from datetime import date

from scripts.tools.wechat_mp_read_hooks import (
    BRIDGE_MARK,
    append_to_section_end,
    apply_if_enabled,
    has_reader_hook,
    insert_after_section_title,
    insert_section_bridges,
    read_hooks_enabled,
    normalize_hook_spacing,
)
from scripts.tools.wechat_mp_market_polish import _section_paragraph
from scripts.tools.wechat_mp_prose import SECTOR_SECTION_TITLES, _strip_emojis

# 读者正文勿出现（与 wechat_mp_eval.BANNED_AI_PHRASES / news 稿对齐）
_SECTOR_READER_BANNED: tuple[str, ...] = (
    "流水线",
    "综上所述",
    "值得注意的是",
    "值得一提的是",
    "赋能",
    "链路",
    "一站式",
)

_TRANSITION_REWRITES: tuple[tuple[str, str], ...] = (
    ("首先，", "先，"),
    ("首先", "先"),
    ("其次，", "再，"),
    ("其次", "再"),
    ("最后，", "随后，"),
    ("最后", "随后"),
    ("综上，", "总的来说，"),
    ("综上", "总的来说"),
)

_SECTION_WHY = SECTOR_SECTION_TITLES[0]
_SECTION_FORWARD = SECTOR_SECTION_TITLES[-1]

_SECTION_BRIDGES = {
    SECTOR_SECTION_TITLES[1]: (
        f"{BRIDGE_MARK}价格传导往往比新闻标题慢半拍，产业链拆开才看得清。"
    ),
    SECTOR_SECTION_TITLES[2]: (
        f"{BRIDGE_MARK}谁在量价上表态，比概念名单更重要。"
    ),
    SECTOR_SECTION_TITLES[3]: (
        f"{BRIDGE_MARK}行业强不等于个股强，指数情绪这一段值得对照着读。"
    ),
    SECTOR_SECTION_TITLES[4]: (
        f"{BRIDGE_MARK}向后看里留验证点，明日用什么数据证伪今天的判断。"
    ),
}


def _opening_path_hook(*, trade_label: str, theme: str) -> str:
    theme = (theme or "当日主线").strip()[:12]
    return (
        f"{trade_label}聚焦「{theme}」——正文按「为什么看→产业链→盘面→联动→验证」"
        f"五节展开；读完最后一节，才知道明日该盯哪条数据链。"
    )


def _closing_suspense(*, trade_label: str, theme: str) -> str:
    theme = (theme or "主线").strip()[:10]
    return (
        f"若「{theme}」次日承接走弱，"
        f"产业链里谁先掉速，往往最先在代表股的换手与收盘位置上露馅——"
        f"这是对整条逻辑链的硬验证，而不是单条新闻的复述。"
    )


def sanitize_sector_reader_voice(text: str) -> str:
    """去 AI 味触发词、后台术语与 emoji（推稿门禁 sector 专用）。"""
    if not text:
        return text
    out = text
    for phrase in _SECTOR_READER_BANNED:
        out = out.replace(phrase, "")
    for old, new in _TRANSITION_REWRITES:
        out = out.replace(old, new)
    out = _strip_emojis(out)
    out = re.sub(r"[；;，,]{2,}", "，", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def sanitize_sector_llm_leaks(text: str) -> str:
    """去掉 LLM 把 prompt 上下文当成「你提供的数据」的元叙述。"""
    if not text:
        return text
    patterns: list[tuple[str, str]] = [
        (r"根据[您你]提供的[^。\n]{0,80}[。]?", ""),
        (r"根据(上文|下文|上下文|以下数据|上述数据)[，,]?[^。\n]{0,40}[。]?", ""),
        (r"[您你]提供的(?:\d+月\d+日)?指数[^。\n]{0,60}[。]?", ""),
        (r"基于[您你]提供的[^。\n]{0,60}[。]?", ""),
    ]
    out = text
    for pat, repl in patterns:
        out = re.sub(pat, repl, out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def inject_hot_stock_watch_section(
    body: str,
    *,
    trade_label: str = "",
    rows: list | None = None,
) -> str:
    from scripts.tools.wechat_mp_sector_stocks import (
        HOT_WATCH_SECTION_TITLE,
        fetch_hot_stock_watch_rows,
        format_hot_stock_watch_section,
        sector_hot_watch_top_n,
    )
    from scripts.tools.wechat_mp_read_hooks import insert_before_section_title

    if sector_hot_watch_top_n() <= 0:
        return body
    if f"> {HOT_WATCH_SECTION_TITLE}" in body:
        return body
    watch_rows = rows if rows is not None else fetch_hot_stock_watch_rows()
    section = format_hot_stock_watch_section(watch_rows, trade_label=trade_label)
    if not section:
        return body
    link_section = SECTOR_SECTION_TITLES[3]
    return insert_before_section_title(body, link_section, ["", section, ""])


def finalize_sector_body(
    body: str,
    *,
    trade_label: str = "",
    primary_theme: str = "",
    hot_watch_rows: list | None = None,
) -> str:
    body = sanitize_sector_llm_leaks(body)
    body = sanitize_sector_reader_voice(body)
    body = inject_hot_stock_watch_section(
        body, trade_label=trade_label, rows=hot_watch_rows
    )
    if not read_hooks_enabled("sector"):
        return body

    def _run(text: str) -> str:
        marker = f"> {_SECTION_WHY}"
        intro = text.split(marker, 1)[0] if marker in text else text[:400]
        if not has_reader_hook(intro) and not has_reader_hook(
            _section_paragraph(text, _SECTION_WHY)
        ):
            hook = _opening_path_hook(
                trade_label=trade_label or "本稿",
                theme=primary_theme,
            )
            if f"> {_SECTION_WHY}" in text:
                text = insert_after_section_title(text, _SECTION_WHY, ["", hook, ""])
            else:
                text = f"{hook}\n\n{text}"
        text = insert_section_bridges(text, _SECTION_BRIDGES)
        text = append_to_section_end(
            text,
            _SECTION_FORWARD,
            _closing_suspense(trade_label=trade_label, theme=primary_theme),
        )
        return text

    return apply_if_enabled("sector", body, _run)
