#!/usr/bin/env python3
"""影视稿排版：纯段落、无 `> ` 小标题（对齐热点深评）。"""

from __future__ import annotations

import re

from scripts.tools.wechat_mp_prose import strip_hotspot_subheadings

TV_PARA_MAX_CHARS = 220
TV_PARA_MIN_CHARS = 100
_BULLET_LINE_RE = re.compile(r"^·\s*")
_SCENE_LABEL_RE = re.compile(r"^[^：:\n]{2,12}[：:]")


def merge_tv_bullets_to_prose(text: str) -> str:
    """把分场 bullet 熔进段落，避免「> 标题 + 一条 bullet」的清单感。"""
    paragraphs = [p.strip() for p in re.split(r"\n\n+", (text or "").strip()) if p.strip()]
    if not paragraphs:
        return text or ""
    out: list[str] = []
    for para in paragraphs:
        lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
        bullets = [ln for ln in lines if _BULLET_LINE_RE.match(ln)]
        prose = [ln for ln in lines if not _BULLET_LINE_RE.match(ln)]
        if prose:
            out.append("\n".join(prose))
        for b in bullets:
            body = _BULLET_LINE_RE.sub("", b).strip()
            if body:
                out.append(body if body.endswith("。") else body + "。")
    return "\n\n".join(out).strip()


def reflow_tv_layout(text: str, *, max_chars: int = TV_PARA_MAX_CHARS) -> str:
    """长段按句号拆成移动端短段。"""
    paragraphs = [p.strip() for p in re.split(r"\n\n+", (text or "").strip()) if p.strip()]
    if not paragraphs:
        return text or ""
    out: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            out.append(para)
            continue
        sentences = [s for s in re.split(r"(?<=[。！？])", para) if s.strip()]
        if len(sentences) <= 1:
            out.append(para)
            continue
        buf = ""
        for sent in sentences:
            if len(buf) + len(sent) <= max_chars or not buf:
                buf += sent
                if len(buf) >= max_chars:
                    out.append(buf.strip())
                    buf = ""
            else:
                out.append(buf.strip())
                buf = sent
        if buf.strip():
            out.append(buf.strip())
    return "\n\n".join(out).strip()


def merge_tv_short_paragraphs(
    text: str,
    *,
    min_chars: int = TV_PARA_MIN_CHARS,
    max_chars: int = TV_PARA_MAX_CHARS,
) -> str:
    """合并单句/过短段到上一段，但合并后不得超过 max_chars。"""
    paragraphs = [p.strip() for p in re.split(r"\n\n+", (text or "").strip()) if p.strip()]
    if len(paragraphs) <= 1:
        return text or ""
    out: list[str] = []
    for i, para in enumerate(paragraphs):
        sentences = [s for s in re.split(r"(?<=[。！？])", para) if s.strip()]
        short = len(para) < min_chars or len(sentences) < 2
        is_last = i == len(paragraphs) - 1
        if (
            short
            and out
            and not is_last
            and not _SCENE_LABEL_RE.match(para)
            and len(out[-1]) + len(para) <= max_chars
        ):
            out[-1] = out[-1] + para
        else:
            out.append(para)
    return "\n\n".join(out).strip()


def finalize_tv_review_body(text: str) -> str:
    """去掉小标题、bullet 改叙述、段落重排。"""
    out = strip_hotspot_subheadings((text or "").strip())
    out = merge_tv_bullets_to_prose(out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = reflow_tv_layout(out)
    return merge_tv_short_paragraphs(out)
