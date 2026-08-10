"""Local modern Chinese fairy-tale TXT for cloud TTS narration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_STORIES_DIR = Path(__file__).resolve().parent.parent / "data" / "story_txt" / "zh"

# Voice aliases → stem (filename without .txt)
_ALIASES: dict[str, str] = {
    # 外国童话
    "灰姑娘": "灰姑娘",
    "辛德瑞拉": "灰姑娘",
    "cinderella": "灰姑娘",
    "小红帽": "小红帽",
    "小紅帽": "小红帽",
    "red riding hood": "小红帽",
    "睡美人": "睡美人",
    "玫瑰公主": "睡美人",
    "briar rose": "睡美人",
    "白雪公主": "白雪公主",
    "snow white": "白雪公主",
    "青蛙王子": "青蛙王子",
    "frog prince": "青蛙王子",
    "三只小猪": "三只小猪",
    "三隻小豬": "三只小猪",
    "three little pigs": "三只小猪",
    "穿靴子的猫": "穿靴子的猫",
    "穿靴的猫": "穿靴子的猫",
    "穿靴子的貓": "穿靴子的猫",
    "puss in boots": "穿靴子的猫",
    # 中国经典
    "孔融让梨": "孔融让梨",
    "让梨": "孔融让梨",
    "司马光砸缸": "司马光砸缸",
    "司马光": "司马光砸缸",
    "砸缸": "司马光砸缸",
    "曹冲称象": "曹冲称象",
    "称象": "曹冲称象",
    "愚公移山": "愚公移山",
    "愚公": "愚公移山",
    "女娲补天": "女娲补天",
    "女娲": "女娲补天",
    "后羿射日": "后羿射日",
    "后羿": "后羿射日",
    "射日": "后羿射日",
    "嫦娥奔月": "嫦娥奔月",
    "嫦娥": "嫦娥奔月",
    "奔月": "嫦娥奔月",
    "牛郎织女": "牛郎织女",
    "牛郎": "牛郎织女",
    "织女": "牛郎织女",
    "七夕": "牛郎织女",
    "精卫填海": "精卫填海",
    "精卫": "精卫填海",
    "狐假虎威": "狐假虎威",
}

_XIYOU_HINT_RE = re.compile(r"西游记|西遊記|美猴王出世")
_XIYOU_CH_RE = re.compile(
    r"第\s*([0-9一二三四五六七八九十百]+)\s*[回集章]|回\s*([0-9]+)|chapter\s*([0-9]+)",
    re.I,
)
_CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _cn_number(text: str) -> int | None:
    s = (text or "").strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s in _CN_DIGITS:
        return _CN_DIGITS[s]
    if s == "十":
        return 10
    m = re.fullmatch(r"([一二三四五六七八九])?十([一二三四五六七八九])?", s)
    if m:
        tens = _CN_DIGITS.get(m.group(1) or "一", 1)
        ones = _CN_DIGITS.get(m.group(2) or "零", 0)
        return tens * 10 + ones
    m = re.fullmatch(r"([一二三四五六七八九])百([零一二三四五六七八九十]+)?", s)
    if m:
        hundreds = _CN_DIGITS[m.group(1)] * 100
        rest = m.group(2)
        if not rest or rest == "零":
            return hundreds
        sub = _cn_number(rest)
        return hundreds + (sub or 0)
    return None


@dataclass(frozen=True)
class LocalStory:
    id: str
    title: str
    path: Path
    body: str
    char_count: int


def _norm(text: str) -> str:
    return re.sub(r"[\s_\-]+", "", (text or "").strip().lower())


@lru_cache(maxsize=1)
def _story_files() -> dict[str, Path]:
    if not _STORIES_DIR.is_dir():
        return {}
    out: dict[str, Path] = {}
    for path in sorted(_STORIES_DIR.glob("*.txt")):
        out[path.stem] = path
    return out


def clear_local_story_cache() -> None:
    _story_files.cache_clear()
    load_story.cache_clear()


def list_story_titles() -> list[dict[str, str]]:
    clear_local_story_cache()
    rows = []
    for stem, path in _story_files().items():
        rows.append({"id": stem, "title": stem, "filename": path.name})
    return rows


def _strip_meta(raw: str) -> tuple[str, str]:
    """Return (title, body for TTS). Drop 说明/来源 header before ——."""
    text = (raw or "").strip()
    if "——" in text:
        head, _, tail = text.partition("——")
        title = head.strip().splitlines()[0].strip() if head.strip() else ""
        body = tail.strip()
    else:
        lines = text.splitlines()
        title = lines[0].strip() if lines else ""
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else text
    cleaned: list[str] = []
    skipping_meta = True
    for line in body.splitlines():
        s = line.strip()
        if skipping_meta and (
            not s
            or s.startswith("说明")
            or s.startswith("来源")
            or s.startswith("版权")
            or s.startswith("原作")
        ):
            continue
        skipping_meta = False
        cleaned.append(line)
    body = "\n".join(cleaned).strip()
    return title or "故事", body


@lru_cache(maxsize=32)
def load_story(story_id: str) -> LocalStory | None:
    path = _story_files().get(story_id)
    if path is None or not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8")
    title, body = _strip_meta(raw)
    if not body:
        return None
    return LocalStory(
        id=story_id,
        title=title or story_id,
        path=path,
        body=body,
        char_count=len(body),
    )


def _match_xiyouji(query: str) -> str | None:
    """西游记第N回 → 西游记第NN回.txt；未指定回目则第01回。"""
    raw = (query or "").strip()
    if not raw or not _XIYOU_HINT_RE.search(raw):
        return None
    files = _story_files()
    n = 1
    m = _XIYOU_CH_RE.search(raw)
    if m:
        token = next((g for g in m.groups() if g), None)
        parsed = _cn_number(token or "")
        if parsed is not None:
            n = parsed
    stem = f"西游记第{n:02d}回"
    if stem in files:
        return stem
    alt = f"西游记第{n}回"
    if alt in files:
        return alt
    return None


def match_story_id(query: str) -> str | None:
    """Match user utterance to a local story id."""
    raw = (query or "").strip()
    if not raw:
        return None
    xiyou = _match_xiyouji(raw)
    if xiyou:
        return xiyou

    norm = _norm(raw)
    files = _story_files()

    alias_rows = sorted(_ALIASES.items(), key=lambda kv: len(_norm(kv[0])), reverse=True)
    for alias, stem in alias_rows:
        if stem not in files:
            continue
        an = _norm(alias)
        if an and an in norm:
            return stem

    stems = sorted(files.keys(), key=lambda s: len(_norm(s)), reverse=True)
    for stem in stems:
        sn = _norm(stem)
        if sn and sn in norm:
            return stem
    return None


def resolve_local_story(query: str) -> dict:
    clear_local_story_cache()
    story_id = match_story_id(query)
    if not story_id:
        return {
            "success": False,
            "query": query,
            "error": "no_local_story",
            "available": [r["title"] for r in list_story_titles()],
            "instruction": "Say resource missing only for this fairy-tale list; Quark audio is separate.",
        }
    story = load_story(story_id)
    if story is None:
        return {"success": False, "query": query, "error": "story_file_empty"}
    return {
        "success": True,
        "query": query,
        "story_id": story.id,
        "title": story.title,
        "char_count": story.char_count,
        "body": story.body,
        "playback_mode": "cloud_tts_narrate",
        "instruction": (
            "Read body aloud to the child via normal TTS speech. "
            "Do NOT call self.audio.play_url. "
            "Do not summarize — narrate the story text."
        ),
    }
