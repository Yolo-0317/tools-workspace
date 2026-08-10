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


def _split_sentences(text: str) -> list[str]:
    parts = [s.strip() for s in re.split(r"(?<=[。！？])", text) if s.strip()]
    return parts or [text.strip()]


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
        if len(sentences) <= 1:
            out.append(para)
        else:
            out.extend(sentences)

    return "\n\n".join(out)
