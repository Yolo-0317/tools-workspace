"""Load prompt templates from plain-text files."""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt_file(name: str) -> str:
    path = Path(name)
    if not path.is_file():
        path = PROMPTS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file not found: {name}")
    return path.read_text(encoding="utf-8").strip()


def render_user_prompt(
    template: str,
    *,
    fragment: str,
    task: str,
    word_count: int = 1500,
) -> str:
    return template.format(fragment=fragment, task=task, word_count=word_count)
