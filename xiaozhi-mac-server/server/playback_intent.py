"""Fast-path intents for playback memory (continue / next / replay)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_RESUME_RE = re.compile(
    r"^(继续|接着播|继续播|继续播放|接着播放|从上次|续播).*$"
)
_NEXT_RE = re.compile(
    r"^(下一集|下一首|换一集|换一首|下集|下一段|下一个).*$"
)
_REPLAY_RE = re.compile(
    r"^(重新播放|再播一遍|再听一遍|重播|刚才那个|刚才的|上次那个|播放刚才).*$"
)
_MEMORY_QUERY_RE = re.compile(
    r"^(刚才播|刚才听|上次播|播放记录|播了什么|在播什么).*$"
)


@dataclass(frozen=True)
class PlaybackIntent:
    action: str  # resume | next | replay | memory_query
    user_text: str


def match_playback_intent(text: str) -> PlaybackIntent | None:
    raw = (text or "").strip()
    if not raw:
        return None
    cleaned = re.sub(r"[。！？!?.\s]+$", "", raw)
    if _RESUME_RE.match(cleaned):
        return PlaybackIntent("resume", raw)
    if _NEXT_RE.match(cleaned):
        return PlaybackIntent("next", raw)
    if _REPLAY_RE.match(cleaned):
        return PlaybackIntent("replay", raw)
    if _MEMORY_QUERY_RE.match(cleaned):
        return PlaybackIntent("memory_query", raw)
    return None
