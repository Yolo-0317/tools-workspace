#!/usr/bin/env python3
"""公众号完读钩子：段间过渡、节间桥接、末段悬念（sector/dragons/market/news/top5）。"""

from __future__ import annotations

import os
import re
from collections.abc import Callable

from scripts.tools.wechat_mp_market_polish import _section_paragraph

READER_HOOK_RE = re.compile(
    r"逐只|顺着|接下去|先读|接着拆|再拆|下一只|下一节|翻页|"
    r"若.{1,40}则|谁先|露馅|验证点|明日盯|读完.*再|"
    r"比.{1,8}更|差别在|才看得出|证伪"
)
_STOCK_LINE_RE = re.compile(r"^\d+\.\s+\S")
# 段间桥接行：用「·」轻标记，避免「往下看」「→」导流口吻
BRIDGE_MARK = "· "
_BRIDGE_LINE_RE = re.compile(r"^\s*·\s")
_LEGACY_ARROW_RE = re.compile(r"^\s*→")


def is_bridge_line(line: str) -> bool:
    s = (line or "").strip()
    return bool(_BRIDGE_LINE_RE.match(s) or _LEGACY_ARROW_RE.match(s))


def read_hooks_enabled(kind: str) -> bool:
    k = (kind or "").strip().lower()
    env_key = {
        "top5": "WECHAT_MP_TOP5_READ_HOOKS",
        "sector": "WECHAT_MP_SECTOR_READ_HOOKS",
        "dragons": "WECHAT_MP_DRAGONS_READ_HOOKS",
        "market": "WECHAT_MP_MARKET_READ_HOOKS",
        "news": "WECHAT_MP_NEWS_READ_HOOKS",
    }.get(k, f"WECHAT_MP_{k.upper()}_READ_HOOKS")
    specific = (os.getenv(env_key) or "").strip().lower()
    if specific:
        return specific not in ("0", "false", "no", "off")
    raw = (os.getenv("WECHAT_MP_READ_HOOKS") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def has_reader_hook(text: str) -> bool:
    return bool(READER_HOOK_RE.search(text or ""))


def _section_header_line(section: str) -> str:
    return f"> {section.strip()}"


def insert_after_section_title(body: str, section: str, block: list[str]) -> str:
    if _section_header_line(section) not in body:
        return body
    lines = body.splitlines()
    out: list[str] = []
    pending = [b for b in block if b]
    for line in lines:
        out.append(line)
        bare = line.strip().lstrip("> ").strip()
        if pending and bare == section.strip():
            out.extend(pending)
            pending = []
    return "\n".join(out)


def insert_before_section_title(body: str, section: str, block: list[str]) -> str:
    if _section_header_line(section) not in body:
        return body
    lines = body.splitlines()
    out: list[str] = []
    for line in lines:
        bare = line.strip().lstrip("> ").strip()
        if bare == section.strip():
            out.extend(block)
        out.append(line)
    return "\n".join(out)


def insert_section_bridges(body: str, bridges: dict[str, str]) -> str:
    """在指定节标题前插入桥接句（节名 → 钩子文案）。"""
    text = body
    for section, bridge in bridges.items():
        blob = _section_paragraph(text, section)
        if has_reader_hook(blob) or bridge[:14] in blob:
            continue
        text = insert_before_section_title(text, section, ["", bridge, ""])
    return text


def inject_transitions_in_section(
    body: str,
    section: str,
    *,
    line_re: re.Pattern[str] = _STOCK_LINE_RE,
    transitions: tuple[str, ...],
) -> str:
    """在节内、匹配行（如 `1. 股名`）之前插入过渡句。"""
    if _section_header_line(section) not in body:
        return body
    lines = body.splitlines()
    in_section = False
    match_indices: list[int] = []
    for i, line in enumerate(lines):
        bare = line.strip().lstrip("> ").strip()
        if bare == section.strip():
            in_section = True
            continue
        if in_section and line.strip().startswith("> ") and bare != section.strip():
            break
        if in_section and line_re.match(line.strip()):
            match_indices.append(i)
    if len(match_indices) < 2:
        return body

    offset = 0
    for j in range(len(match_indices) - 1):
        start = match_indices[j] + offset
        end = match_indices[j + 1] + offset
        between = [ln for ln in lines[start + 1 : end] if ln.strip()]
        if any(is_bridge_line(ln) or has_reader_hook(ln) for ln in between):
            continue
        hook = transitions[j % len(transitions)]
        insert_at = end
        lines[insert_at:insert_at] = ["", hook, ""]
        offset += 3
    return "\n".join(lines)


def append_to_section_end(
    body: str,
    section: str,
    closing: str,
    *,
    min_existing: int = 50,
) -> str:
    blob = _section_paragraph(body, section)
    if len(blob) >= min_existing and (
        "露馅" in blob or re.search(r"若.{2,40}则", blob)
    ):
        return body
    marker = _section_header_line(section)
    if marker not in body:
        return f"{body.rstrip()}\n\n{marker}\n\n{closing}"
    head, tail = body.split(marker, 1)
    tail_lines = tail.splitlines()
    insert_idx = len(tail_lines)
    for i in range(1, len(tail_lines)):
        if tail_lines[i].strip().startswith("> "):
            insert_idx = i
            break
    new_tail = tail_lines[:insert_idx] + ["", closing, ""] + tail_lines[insert_idx:]
    return head + marker + "\n".join(new_tail)


def normalize_hook_spacing(body: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def apply_if_enabled(kind: str, body: str, fn: Callable[[str], str]) -> str:
    if not read_hooks_enabled(kind) or not body.strip():
        return body
    return normalize_hook_spacing(fn(body))
