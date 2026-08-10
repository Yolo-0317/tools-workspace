#!/usr/bin/env python3
"""龙头稿成稿后处理：开篇数字、控长、利于完读。"""

from __future__ import annotations

import os
import re
from typing import Any

from scripts.tools.wechat_mp_market_polish import split_long_paragraphs


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def _opening_lede_from_hdr(hdr: dict[str, Any]) -> str:
    phase = hdr.get("phase") or "—"
    theme = hdr.get("main_theme") or "—"
    up = hdr.get("limit_up_count")
    down = hdr.get("limit_down_count")
    explode = hdr.get("explode_rate_pct")
    ratio = hdr.get("up_down_ratio")
    parts = []
    if up is not None and down is not None:
        parts.append(f"涨停{up}/跌停{down}")
    if explode is not None:
        parts.append(f"炸板率{explode}%")
    if ratio is not None:
        parts.append(f"涨跌比{ratio}")
    nums = "，".join(parts) if parts else "涨跌家数见下表"
    return (
        f"情绪阶段「{phase}」，主线围绕{theme}；{nums}。"
        f"我们认为，接力环境取决于梯队是否完整，而非单条消息。"
    )


def inject_dragons_opening_lede(body: str, *, hdr: dict[str, Any]) -> str:
    """在 > 情绪与盘面 后、首段前插入带数字的彩色开篇（若缺失）。"""
    marker = "> 情绪与盘面"
    if marker not in body:
        return body
    head, rest = body.split(marker, 1)
    rest_lines = rest.splitlines()
    # rest_lines[0] may be empty; find first substantive para
    insert_at = 0
    for i, line in enumerate(rest_lines):
        s = line.strip()
        if s and not s.startswith(">"):
            insert_at = i
            break
    lede = _opening_lede_from_hdr(hdr)
    # 若首段已含炸板率或涨停，不再插入
    blob = "\n".join(rest_lines[: insert_at + 3])
    if "炸板率" in blob and ("涨停" in blob or "涨跌比" in blob):
        return body
    block = ["", lede, ""]
    new_rest = rest_lines[:insert_at] + block + rest_lines[insert_at:]
    return head + marker + "\n".join(new_rest)


def cap_dragons_body_length(body: str, *, max_chars: int | None = None) -> str:
    limit = max_chars if max_chars is not None else _env_int("WECHAT_MP_DRAGON_MAX_CHARS", 3200)
    plain = re.sub(r"\s+", "", body)
    if len(plain) <= limit:
        return body
    # 优先保留前半（情绪+龙头拆解）
    acc = 0
    out: list[str] = []
    for line in body.splitlines():
        acc += len(re.sub(r"\s+", "", line))
        out.append(line)
        if acc >= limit:
            out.append("")
            out.append("（篇幅略长已截断尾部；完整梯队见次日更新。）")
            break
    return "\n".join(out).strip()


def _finalize_dragons_read_hooks(body: str, *, hdr: dict[str, Any]) -> str:
    from scripts.tools.wechat_mp_read_hooks import (
        append_to_section_end,
        has_reader_hook,
        inject_transitions_in_section,
        insert_after_section_title,
        insert_section_bridges,
        read_hooks_enabled,
        normalize_hook_spacing,
    )
    from scripts.tools.wechat_mp_prose import DRAGON_SECTION_TITLES

    if not read_hooks_enabled("dragons"):
        return body

    phase = str(hdr.get("phase") or "情绪").strip()
    theme = str(hdr.get("main_theme") or "主线").strip()[:10]
    s_emotion, s_breakdown, s_ladder, s_plan = DRAGON_SECTION_TITLES

    text = body
    blob = ""
    if f"> {s_emotion}" in text:
        from scripts.tools.wechat_mp_market_polish import _section_paragraph

        blob = _section_paragraph(text, s_emotion)
    if not has_reader_hook(blob):
        path = (
            f"情绪阶段「{phase}」围绕{theme}——正文按「盘面→龙头拆解→梯队→明日纪律」展开；"
            f"读完「明日计划与纪律」，才知道什么信号算退潮确认。"
        )
        text = insert_after_section_title(text, s_emotion, ["", path, ""])

    from scripts.tools.wechat_mp_read_hooks import BRIDGE_MARK

    bridges = {
        s_breakdown: f"{BRIDGE_MARK}龙头拆解才是情绪真正的试金石。",
        s_ladder: f"{BRIDGE_MARK}空间板断了以后，梯队怎么排，比单看高度更重要。",
        s_plan: f"{BRIDGE_MARK}次日用哪些公开数据核对，比口号更值得写进备忘录。",
    }
    text = insert_section_bridges(text, bridges)

    transitions = (
        f"{BRIDGE_MARK}这只和上一只比，谁在接力、谁在掉队，一眼能分。",
        f"{BRIDGE_MARK}下一只先盯板位，高度能不能稳住，比故事更重要。",
        f"{BRIDGE_MARK}若退潮，谁先断板，往往最先在这一档露馅。",
    )
    text = inject_transitions_in_section(text, s_breakdown, transitions=transitions)

    closing = (
        f"若次日炸板率抬升、空间板断板且跟风集体走弱，"
        f"情绪退潮才算确认；反之仅当梯队修复，才谈得上接力延续——"
        f"这是明日盘中的硬验证，不是今晚的口号。"
    )
    text = append_to_section_end(text, s_plan, closing)
    return normalize_hook_spacing(text)


def finalize_dragons_body(body: str, *, hdr: dict[str, Any]) -> str:
    text = split_long_paragraphs(body, max_chars=_env_int("WECHAT_MP_DRAGON_PARA_MAX", 160))
    text = inject_dragons_opening_lede(text, hdr=hdr)
    text = _finalize_dragons_read_hooks(text, hdr=hdr)
    return cap_dragons_body_length(text)
