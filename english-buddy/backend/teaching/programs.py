"""Themed read-along programs (Elsa · Ultraman)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from teaching.free_chat_kickoffs import FREE_CHAT_KICKOFFS

PROGRAMS_DIR = Path(__file__).resolve().parent / "programs"
DEFAULT_PROGRAM_ID = "elsa_snow"

# Old clients / bookmarks
_PROGRAM_ALIASES = {
    "girls_elsa_judy": "elsa_snow",
    "boys_spidey_ultra": "ultra_hero",
    "boys_paw_patrol": "ultra_hero",
}


@dataclass(frozen=True)
class Program:
    id: str
    title: str
    subtitle: str
    emoji: str
    audience: str
    characters: tuple[str, ...]
    tts_voice: str
    sample_material: str
    kickoff_read_along: str
    kickoff_free: tuple[str, ...]
    theme: dict[str, str]
    page: dict[str, object]
    cast: tuple[dict[str, str], ...]
    tts_backend: str = ""
    tts_rate: str = ""
    tts_pitch: str = ""

    def persona_addon(self) -> str:
        path = PROGRAMS_DIR / f"{self.id}.md"
        if not path.is_file():
            return ""
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return ""
        body = (
            "\n\n## Today's show (character program — follow strictly)\n"
            + text
        )
        if self.id == "elsa_snow":
            cur = PROGRAMS_DIR.parent / "elsa_curriculum.md"
            if cur.is_file():
                body += "\n\n" + cur.read_text(encoding="utf-8").strip()
        return body


PROGRAMS: dict[str, Program] = {
    "elsa_snow": Program(
        id="elsa_snow",
        title="冰雪艾莎",
        subtitle="艾莎",
        emoji="👸",
        audience="约 4～7 岁",
        characters=("Elsa",),
        tts_voice="elsa",
        tts_rate="+8%",
        tts_pitch="+10Hz",
        sample_material=(
            "Hi! Welcome to the night shadow room.\n"
            "Here you can see magical shadows at night.\n"
            "We also have a fun puppet show!"
        ),
        kickoff_read_along=(
            "(Read-along — Elsa teacher.) "
            "Speak **only** the first sentence of the pasted material (≤10 words). "
            "No hello, Good, Your turn, or praise."
        ),
        kickoff_free=FREE_CHAT_KICKOFFS,
        theme={
            "card_bg": "linear-gradient(145deg, #fce7f3, #e0e7ff)",
            "card_border": "#f9a8d4",
            "accent": "#ec4899",
            "accent2": "#818cf8",
        },
        page={
            "skin": "girls",
            "picker_title": "冰雪艾莎",
            "picker_tagline": "艾莎当老师，按年级课文带读",
            "picker_bg": (
                "radial-gradient(circle at 20% 15%, #fce7f3 0%, transparent 45%), "
                "radial-gradient(circle at 85% 20%, #dbeafe 0%, transparent 40%), "
                "linear-gradient(165deg, #fff5f8 0%, #eef2ff 50%, #fdf2f8 100%)"
            ),
            "hero_bg": (
                "radial-gradient(circle at 50% 0%, #fbcfe8 0%, transparent 55%), "
                "linear-gradient(180deg, #fff5f8 0%, #eef2ff 100%)"
            ),
            "decor": [],
            "btn_primary": "linear-gradient(135deg, #f472b6, #a78bfa)",
            "btn_shadow": "rgba(244, 114, 182, 0.35)",
            "material_hint": "课文按上海沪教牛津年级编排，与艾莎剧情无关。",
        },
        cast=(
            {
                "name_cn": "艾莎",
                "name_en": "Elsa",
                "emoji": "👸",
                "avatar": "elsa",
                "role": "带读老师",
            },
        ),
    ),
    "ultra_hero": Program(
        id="ultra_hero",
        title="光之奥特曼",
        subtitle="奥特曼",
        emoji="🤖",
        audience="约 7～8 岁（上海二年级）",
        characters=("Ultra",),
        tts_voice="ultra",
        tts_rate="+0%",
        tts_pitch="+0Hz",
        sample_material=(
            "Are you Alice?\n"
            "No, I am Danny.\n"
            "I am eight years old."
        ),
        kickoff_read_along=(
            "(Read-along — **光之奥特曼**.) "
            "Ultra says hello (one short cool line). "
            "Hero mission: English. Model first 4–6 words, then 'Your turn!'"
        ),
        kickoff_free=FREE_CHAT_KICKOFFS,
        theme={
            "card_bg": "linear-gradient(145deg, #dbeafe, #fef3c7)",
            "card_border": "#2563eb",
            "accent": "#2563eb",
            "accent2": "#f59e0b",
        },
        page={
            "skin": "boys",
            "picker_title": "光之奥特曼",
            "picker_tagline": "奥特曼当老师，按年级课文带读",
            "picker_bg": (
                "radial-gradient(circle at 15% 10%, #bfdbfe 0%, transparent 42%), "
                "radial-gradient(circle at 90% 15%, #fde68a 0%, transparent 38%), "
                "linear-gradient(165deg, #eff6ff 0%, #fef9c3 45%, #e0f2fe 100%)"
            ),
            "hero_bg": (
                "radial-gradient(circle at 50% 0%, #93c5fd 0%, transparent 50%), "
                "linear-gradient(180deg, #eff6ff 0%, #fef9c3 100%)"
            ),
            "decor": [],
            "btn_primary": "linear-gradient(135deg, #2563eb, #f59e0b)",
            "btn_shadow": "rgba(37, 99, 235, 0.35)",
            "material_hint": (
                "课文与奥特曼剧情无关。下方为沪教二年级「我是 Danny」（第1课），也可贴学校作业英文。"
            ),
        },
        cast=(
            {
                "name_cn": "奥特曼",
                "name_en": "Ultra",
                "emoji": "🤖",
                "avatar": "ultra",
                "role": "光之战士",
            },
        ),
    ),
}


def get_program(program_id: str | None) -> Program:
    pid = (program_id or "").strip() or DEFAULT_PROGRAM_ID
    pid = _PROGRAM_ALIASES.get(pid, pid)
    return PROGRAMS.get(pid, PROGRAMS[DEFAULT_PROGRAM_ID])


def list_programs_public() -> list[dict]:
    out: list[dict] = []
    for p in PROGRAMS.values():
        out.append(
            {
                "id": p.id,
                "title": p.title,
                "subtitle": p.subtitle,
                "emoji": p.emoji,
                "audience": p.audience,
                "characters": list(p.characters),
                "sample_material": p.sample_material,
                "theme": p.theme,
                "page": p.page,
                "cast": list(p.cast),
            }
        )
    return out
