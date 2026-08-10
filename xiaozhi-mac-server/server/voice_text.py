"""Normalize ASR output for Chinese story keywords."""

from __future__ import annotations

import re

# Common tiny-model misreads for kids' story requests.
_ASR_REPLACEMENTS = (
    ("奇元", "奇缘"),
    ("其缘", "奇缘"),
    ("奇原", "奇缘"),
    ("冰血", "冰雪"),
    ("冰学", "冰雪"),
    ("哈里波特", "哈利波特"),
    ("小致", "小智"),
    ("alpha blocks", "alphablocks"),
    ("alpha block", "alphablocks"),
    ("儿童故事", "儿童故事"),
    ("哈利波特", "哈利波特"),
)

_FILLER_PREFIX = re.compile(
    r"^(请|帮我|给我|那个|嗯|啊|呃|就是|我想|想要|要听|想听一下|听一下|播放一下|播放|播|听)+"
)

# Markdown / list markers that TTS would read aloud (e.g. "**" -> "星号").
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_MD_UNDERSCORE = re.compile(r"__(.+?)__")
_MD_LIST = re.compile(r"^\s*(?:\d+[.)、]|[\-*•])\s+", re.MULTILINE)
_MD_HEADING = re.compile(r"^#+\s*", re.MULTILINE)


def truncate_for_voice(reply: str, *, max_chars: int = 90) -> str:
    """Keep kid-facing spoken replies short so TTS finishes before the next listen window."""
    text = (reply or "").strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    if "，" in cut[20:]:
        return cut.rsplit("，", 1)[0] + "。"
    if "。" in cut:
        return cut.rsplit("。", 1)[0] + "。"
    return cut + "。"


def sanitize_for_speech(text: str) -> str:
    """Strip markdown and list formatting before TTS."""
    raw = (text or "").strip()
    if not raw:
        return ""
    raw = _MD_BOLD.sub(r"\1", raw)
    raw = _MD_ITALIC.sub(r"\1", raw)
    raw = _MD_UNDERSCORE.sub(r"\1", raw)
    raw = raw.replace("*", "").replace("_", "").replace("`", "")
    raw = _MD_HEADING.sub("", raw)
    raw = _MD_LIST.sub("", raw)
    raw = re.sub(r"\n+", "，", raw)
    raw = re.sub(r"[，,]{2,}", "，", raw)
    raw = re.sub(r"\s{2,}", " ", raw)
    raw = truncate_for_voice(raw.strip("，, "))
    return raw.strip("，, ")


def fix_asr_text(text: str) -> str:
    """Apply ASR typo fixes only; keep filler words for downstream handling."""
    raw = (text or "").strip()
    if not raw:
        return ""
    for old, new in _ASR_REPLACEMENTS:
        raw = raw.replace(old, new)
    return raw.strip()


def normalize_transcript(text: str) -> str:
    raw = fix_asr_text(text)
    if not raw:
        return ""
    cleaned = _FILLER_PREFIX.sub("", raw).strip(" ，。！？!?.")
    if cleaned:
        return cleaned.strip()
    # Short filler-only clips ("嗯""啊") should not vanish before intent routing.
    return raw


def wants_video_keyword(keyword: str) -> bool:
    """Deprecated: media type comes from LLM intent_router media_hint."""
    _ = keyword
    return False
