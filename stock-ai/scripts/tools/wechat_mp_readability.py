#!/usr/bin/env python3
"""公众号正文移动端可读性：控段长、序号列表逐项换行。"""

from __future__ import annotations

import os
import re

# 约半屏（15px 字号、单行 ~22 字 ≈ 5～6 行）
DEFAULT_PARA_MAX_CHARS = 120

_INLINE_ORDERED_RE = re.compile(
    r"(?:(?<=^)|(?<=\s)|(?<=[。！？；;：:]))(\d{1,2})[.、．]\s*"
)
_INLINE_PAREN_ORDERED_RE = re.compile(
    r"(?:(?<=^)|(?<=\s))(?:[（(])(\d{1,2})[)）]\s*"
)
_TOP5_FIELD_SPLIT_RE = re.compile(
    r"(?<=[。；;！？\s])(?=(?:逻辑归属|量价结构|技术位置|待核实|AI点评)[：:])"
)

_SKIP_LINE_PREFIXES = (">", "[[fig:")


def para_max_chars() -> int:
    raw = (os.getenv("WECHAT_MP_PARA_MAX_CHARS") or "").strip()
    if not raw:
        return DEFAULT_PARA_MAX_CHARS
    try:
        return max(60, min(240, int(raw)))
    except ValueError:
        return DEFAULT_PARA_MAX_CHARS


def _should_skip_line(stripped: str) -> bool:
    if not stripped:
        return True
    if any(stripped.startswith(p) for p in _SKIP_LINE_PREFIXES):
        return True
    if stripped.startswith("```"):
        return True
    return False


def _split_one_paragraph(para: str, *, max_chars: int) -> list[str]:
    if len(para) <= max_chars:
        return [para]
    parts: list[str] = []
    buf = ""
    for ch in para:
        buf += ch
        if ch in "。！？" and len(buf.strip()) >= 32:
            parts.append(buf.strip())
            buf = ""
    if buf.strip():
        parts.append(buf.strip())
    if len(parts) <= 1 and len(para) > max_chars:
        bits = re.split(r"(?<=[；;])", para)
        parts = [b.strip() for b in bits if b.strip()]
    if len(parts) <= 1 and len(para) > max_chars:
        bits = re.split(r"(?<=[，,])", para)
        acc: list[str] = []
        chunk = ""
        for b in bits:
            b = b.strip()
            if not b:
                continue
            if len(chunk) + len(b) + 1 <= max_chars:
                chunk = f"{chunk}{b}" if not chunk else f"{chunk}，{b}"
            else:
                if chunk:
                    acc.append(chunk)
                chunk = b
        if chunk:
            acc.append(chunk)
        parts = acc or parts
    return parts if parts else [para]


def split_long_paragraphs(body: str, *, max_chars: int | None = None) -> str:
    """超长单行在句号/分号/逗号处拆成多段（空行分隔）。"""
    limit = max_chars if max_chars is not None else para_max_chars()
    out: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if _should_skip_line(stripped) or len(stripped) <= limit:
            out.append(line)
            continue
        if re.match(r"^\d{1,2}[.、．]\s", stripped) and len(stripped) <= limit + 40:
            # 个股标题行略放宽，避免把「1. 名（代码）」硬拆
            out.append(line)
            continue
        chunks = _split_one_paragraph(stripped, max_chars=limit)
        for i, chunk in enumerate(chunks):
            out.append(chunk)
            if i < len(chunks) - 1:
                out.append("")
    return "\n".join(out)


def _count_inline_ordinals(stripped: str) -> int:
    n = len(_INLINE_ORDERED_RE.findall(stripped))
    n += len(_INLINE_PAREN_ORDERED_RE.findall(stripped))
    return n


def _split_inline_ordinals_on_line(line: str) -> list[str]:
    stripped = line.strip()
    if _should_skip_line(stripped) or _count_inline_ordinals(stripped) < 2:
        return [line]

    indices: list[int] = []
    for m in _INLINE_ORDERED_RE.finditer(stripped):
        indices.append(m.start())
    for m in _INLINE_PAREN_ORDERED_RE.finditer(stripped):
        indices.append(m.start())
    indices = sorted(set(indices))
    if len(indices) < 2:
        return [line]

    parts: list[str] = []
    if indices[0] > 0:
        lead = stripped[: indices[0]].strip()
        if lead:
            parts.append(lead)
    for i, start in enumerate(indices):
        end = indices[i + 1] if i + 1 < len(indices) else len(stripped)
        seg = stripped[start:end].strip()
        if seg:
            parts.append(seg)
    return parts if parts else [line]


def _split_top5_field_labels_on_line(line: str) -> list[str]:
    stripped = line.strip()
    if _should_skip_line(stripped):
        return [line]
    parts = re.split(_TOP5_FIELD_SPLIT_RE, stripped)
    parts = [p.strip() for p in parts if p and p.strip()]
    if len(parts) < 2:
        return [line]
    indent = line[: len(line) - len(line.lstrip())]
    return [f"{indent}{p}" if indent else p for p in parts]


def reflow_inline_numbered_lists(body: str) -> str:
    """同一行内多个「1. 2.」或分项字段标签 → 每项一行。"""
    out: list[str] = []
    for line in body.splitlines():
        expanded: list[str] = [line]
        for _ in range(3):
            next_pass: list[str] = []
            for ln in expanded:
                next_pass.extend(_split_inline_ordinals_on_line(ln))
            expanded = next_pass
        for ln in expanded:
            out.extend(_split_top5_field_labels_on_line(ln))
    return "\n".join(out)


def polish_mobile_readability(body: str, *, max_chars: int | None = None) -> str:
    """序号列表换行 + 控段长（全稿型通用）。"""
    if not body or not body.strip():
        return body
    text = reflow_inline_numbered_lists(body)
    text = split_long_paragraphs(text, max_chars=max_chars)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
