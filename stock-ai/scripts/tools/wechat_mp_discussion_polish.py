"""社会话题讨论稿：移动端扫读排版（一句一段）。"""

from __future__ import annotations

import os
import re

_FIG_LINE_RE = re.compile(r"^\[\[fig:")
_HL_LINE_RE = re.compile(r"^\[\[hl:(.+)\]\]\s*$")
_QUOTE_LINE_RE = re.compile(r"^>\s")


def discussion_scroll_enabled() -> bool:
    raw = (os.getenv("WECHAT_MP_DISCUSSION_SCROLL") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def finalize_discussion_body(text: str) -> str:
    """社会话题讨论稿正文定型：去小标题 + 一句一段（可关 WECHAT_MP_DISCUSSION_SCROLL）。"""
    from scripts.tools.wechat_mp_hotspot_polish import reflow_hotspot_body

    out = reflow_hotspot_body((text or "").strip())
    if discussion_scroll_enabled():
        out = reflow_discussion_layout(out)
    return out


def apply_discussion_format_env() -> None:
    """固化移动端扫读排版 + 讨论稿管线（定时批次调用）。"""
    os.environ.setdefault("WECHAT_MP_TV_PICK_MODE", "discussion")
    os.environ.setdefault("WECHAT_MP_TV_RESEARCH", "1")
    os.environ.setdefault("WECHAT_MP_DISCUSSION_SCROLL", "1")
    os.environ.setdefault("WECHAT_MP_DISCUSSION_FIGURES", "1")
    os.environ.setdefault("WECHAT_MP_DISCUSSION_REQUIRE_FIGURES", "1")
    os.environ.setdefault("WECHAT_MP_DISCUSSION_IMITATE_REWRITE", "1")


_OPEN_QUOTES = frozenset("「『“（(")
_CLOSE_QUOTES = frozenset("」』”）)")
_ASCII_QUOTES = frozenset("\"'")


def _split_sentences(text: str) -> list[str]:
    """按句号拆段，但不在引号内拆，避免「说完。」另起一行只剩后引号。"""
    from scripts.tools.wechat_mp_rich_html import (
        hold_inline_hl_markers,
        restore_inline_hl_markers,
    )

    raw = (text or "").strip()
    if not raw:
        return []
    raw, held = hold_inline_hl_markers(raw)
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    ascii_open = False
    for ch in raw:
        buf.append(ch)
        if ch in _OPEN_QUOTES:
            depth += 1
        elif ch in _CLOSE_QUOTES:
            depth = max(0, depth - 1)
        elif ch in _ASCII_QUOTES:
            ascii_open = not ascii_open
            depth += 1 if ascii_open else -1
            depth = max(0, depth)
        if ch in "。！？" and depth == 0:
            piece = "".join(buf).strip()
            if piece:
                parts.append(piece)
            buf = []
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    merged: list[str] = []
    for piece in parts or [raw]:
        if merged and piece[:1] in _CLOSE_QUOTES | _ASCII_QUOTES:
            merged[-1] = merged[-1] + piece
        else:
            merged.append(piece)
    return [restore_inline_hl_markers(p, held) for p in merged]


def reflow_discussion_layout(text: str) -> str:
    """长段按句号拆成单句段落，插图/引用/高亮行保持原样。"""
    paragraphs = [p.strip() for p in re.split(r"\n\n+", (text or "").strip()) if p.strip()]
    if not paragraphs:
        return text or ""

    out: list[str] = []
    for para in paragraphs:
        lines = [ln for ln in para.splitlines() if ln.strip()]
        if len(lines) > 1:
            for line in lines:
                stripped = line.strip()
                if (
                    _FIG_LINE_RE.match(stripped)
                    or _HL_LINE_RE.match(stripped)
                    or _QUOTE_LINE_RE.match(stripped)
                ):
                    out.append(stripped)
                    continue
                sents = _split_sentences(stripped)
                if len(sents) <= 1:
                    out.append(stripped)
                else:
                    out.extend(sents)
            continue

        if (
            _FIG_LINE_RE.match(para)
            or _HL_LINE_RE.match(para)
            or _QUOTE_LINE_RE.match(para)
        ):
            out.append(para)
            continue

        sentences = _split_sentences(para)
        # 开篇钩子常是两句一段；拆开后首句会被做成居中标题，钩子像丢了
        if not out and len(sentences) <= 2:
            out.append(para)
        elif len(sentences) <= 1:
            out.append(para)
        else:
            out.extend(sentences)

    return "\n\n".join(out)
