#!/usr/bin/env python3
"""Top5 成稿后处理：开篇/段间/末段「吊胃口」钩子（提高完读率）。"""

from __future__ import annotations

import os
import re
from datetime import date
from scripts.tools.selection_watchlist import SelectionPick, next_trading_day
from scripts.tools.wechat_mp_market_polish import _section_paragraph

_STOCK_LINE_RE = re.compile(r"^\d+\.\s+\S")
_SECTION_LIST = "筛选名单"
_SECTION_BREAKDOWN = "个股拆解"
_SECTION_COMBO = "组合特征"
_SECTION_VERIFY = "待验证事项"

from scripts.tools.wechat_mp_read_hooks import BRIDGE_MARK, is_bridge_line

_TRANSITIONS = (
    f"{BRIDGE_MARK}和上一只比，谁更贴主线、谁更像独立脉冲，差别往往在量价。",
    f"{BRIDGE_MARK}下一只把换手和结构放在一起看，比单看涨幅更有意义。",
    f"{BRIDGE_MARK}若板块退潮，谁先掉速，往往最先在这一档露馅。",
    f"{BRIDGE_MARK}压力区更近的那只，明日更容易先给出结构答案。",
)


def top5_read_hooks_enabled() -> bool:
    from scripts.tools.wechat_mp_read_hooks import read_hooks_enabled

    return read_hooks_enabled("top5")


def _has_reader_hook(text: str) -> bool:
    from scripts.tools.wechat_mp_read_hooks import has_reader_hook

    return has_reader_hook(text)


def _trade_day_label(d: date) -> str:
    return f"{d.month}月{d.day}日"


def _synthesize_opening_hook(
    picks: list[SelectionPick],
    *,
    trade_date: date,
    sector_primary: str,
) -> str:
    n = len(picks)
    lead = (picks[0].name or picks[0].code).strip()
    sector = (sector_primary or "当日行业榜主线").strip()[:12]
    td = _trade_day_label(trade_date)
    return (
        f"{td}收盘后 {n} 只标的进名单，主线围绕「{sector}」。"
        f"先分清谁跟榜一同向、谁只是个股脉冲——下文从 {lead} 起逐只拆量价；"
        f"读完「组合特征」再对照「待验证事项」，看明日量能谁先说话。"
    )


def _list_to_breakdown_bridge() -> str:
    return (
        "名单扫一眼只解决「有谁」；逐只拆量价，才看得出结构与主线是否真的一致。"
    )


def _combo_to_verify_bridge(sector_primary: str) -> str:
    sector = (sector_primary or "主线板块").strip()[:10]
    return (
        f"五只放在一起看，强弱排序已经露头；"
        f"最后对照「待验证事项」——若「{sector}」缩量，谁先掉速会最先在量能上给答案。"
    )


def _closing_suspense(*, watch_label: str, sector_primary: str) -> str:
    sector = (sector_primary or "主线").strip()[:10]
    return (
        f"结构跟踪日（{watch_label}）若板块承接走弱，"
        f"名单里谁先掉速，往往最先在换手与收盘位置上露馅——"
        f"这是对全名单的硬验证，而不是单票猜测。"
    )


def inject_top5_opening_hook(
    body: str,
    picks: list[SelectionPick],
    *,
    trade_date: date,
    sector_primary: str = "",
) -> str:
    blob = _section_paragraph(body, _SECTION_LIST)
    if _has_reader_hook(blob) and len(blob) >= 60:
        return body
    hook = _synthesize_opening_hook(
        picks, trade_date=trade_date, sector_primary=sector_primary
    )
    lines = body.splitlines()
    out: list[str] = []
    pending = hook
    for line in lines:
        out.append(line)
        bare = line.strip().lstrip("> ").strip()
        if pending and bare == _SECTION_LIST:
            out.extend(["", pending, ""])
            pending = ""
    return "\n".join(out)


def inject_list_to_breakdown_bridge(body: str) -> str:
    if _SECTION_BREAKDOWN not in body:
        return body
    blob = _section_paragraph(body, _SECTION_LIST)
    if _has_reader_hook(blob) and "逐只" in blob:
        return body
    lines = body.splitlines()
    out: list[str] = []
    for line in lines:
        bare = line.strip().lstrip("> ").strip()
        if bare == _SECTION_BREAKDOWN:
            out.append("")
            out.append(_list_to_breakdown_bridge())
            out.append("")
        out.append(line)
    return "\n".join(out)


def inject_stock_transition_hooks(body: str) -> str:
    lines = body.splitlines()
    in_breakdown = False
    stock_indices: list[int] = []
    for i, line in enumerate(lines):
        bare = line.strip().lstrip("> ").strip()
        if bare == _SECTION_BREAKDOWN:
            in_breakdown = True
            continue
        if in_breakdown and line.strip().startswith("> ") and bare != _SECTION_BREAKDOWN:
            break
        if in_breakdown and _STOCK_LINE_RE.match(line.strip()):
            stock_indices.append(i)
    if len(stock_indices) < 2:
        return body

    offset = 0
    for j in range(len(stock_indices) - 1):
        start = stock_indices[j] + offset
        end = stock_indices[j + 1] + offset
        between = [ln for ln in lines[start + 1 : end] if ln.strip()]
        if any(is_bridge_line(ln) or _has_reader_hook(ln) for ln in between):
            continue
        hook = _TRANSITIONS[j % len(_TRANSITIONS)]
        insert_at = end
        lines[insert_at:insert_at] = ["", hook, ""]
        offset += 3
    return "\n".join(lines)


def inject_combo_teaser(body: str, *, sector_primary: str = "") -> str:
    blob = _section_paragraph(body, _SECTION_COMBO)
    if not blob:
        return body
    if _has_reader_hook(blob) and "待验证" in blob:
        return body
    lines = body.splitlines()
    out: list[str] = []
    in_combo = False
    inserted = False
    for line in lines:
        bare = line.strip().lstrip("> ").strip()
        if bare == _SECTION_COMBO:
            in_combo = True
            out.append(line)
            continue
        if in_combo and not inserted and line.strip().startswith("> "):
            out.append("")
            out.append(_combo_to_verify_bridge(sector_primary))
            out.append("")
            inserted = True
            in_combo = False
        out.append(line)
    if in_combo and not inserted:
        out.extend(["", _combo_to_verify_bridge(sector_primary), ""])
    return "\n".join(out)


def inject_closing_suspense(
    body: str,
    *,
    watch_date: date,
    sector_primary: str = "",
) -> str:
    blob = _section_paragraph(body, _SECTION_VERIFY)
    if len(blob) >= 50 and (
        "露馅" in blob or re.search(r"若.{2,40}则", blob)
    ):
        return body
    watch = _trade_day_label(watch_date)
    line = _closing_suspense(watch_label=watch, sector_primary=sector_primary)
    marker = f"> {_SECTION_VERIFY}"
    if marker not in body:
        return f"{body.rstrip()}\n\n{marker}\n\n{line}"

    head, tail = body.split(marker, 1)
    tail_lines = tail.splitlines()
    insert_idx = len(tail_lines)
    for i in range(1, len(tail_lines)):
        if tail_lines[i].strip().startswith("> "):
            insert_idx = i
            break
    new_tail = tail_lines[:insert_idx] + ["", line, ""] + tail_lines[insert_idx:]
    return head + marker + "\n".join(new_tail)


def finalize_top5_body(
    body: str,
    picks: list[SelectionPick],
    *,
    trade_date: date,
    sector_primary: str = "",
) -> str:
    if not top5_read_hooks_enabled() or not body.strip():
        return body

    watch = next_trading_day(trade_date)
    text = inject_top5_opening_hook(
        body, picks, trade_date=trade_date, sector_primary=sector_primary
    )
    text = inject_list_to_breakdown_bridge(text)
    text = inject_stock_transition_hooks(text)
    text = inject_combo_teaser(text, sector_primary=sector_primary)
    text = inject_closing_suspense(
        text, watch_date=watch, sector_primary=sector_primary
    )
    return re.sub(r"\n{3,}", "\n\n", text).strip()
