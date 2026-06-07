"""Load curated young-learner teaching playbook into the LLM system prompt."""

from __future__ import annotations

import json
import os
from pathlib import Path

TEACHING_DIR = Path(__file__).resolve().parent
DEFAULT_PLAYBOOK = TEACHING_DIR / "playbook_age4_read_along.md"
REFERENCES_JSON = TEACHING_DIR / "references.json"


def teaching_enabled() -> bool:
    return os.getenv("TEACHING_GUIDE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def playbook_path() -> Path:
    raw = os.getenv("TEACHING_GUIDE_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_PLAYBOOK


def load_teaching_addon() -> str:
    """Condensed pedagogy block appended to the system prompt."""
    if not teaching_enabled():
        return ""
    path = playbook_path()
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return ""
    max_chars = int(os.getenv("TEACHING_GUIDE_MAX_CHARS", "2800"))
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n\n[Teaching guide truncated.]"
    return (
        "\n\n## How to teach this 4-year-old (use every turn)\n"
        "Follow the playbook below. You are the English teacher; apply these steps in English only.\n\n"
        + text
    )


def teaching_status() -> dict[str, object]:
    path = playbook_path()
    enabled = teaching_enabled()
    loaded = enabled and path.is_file()
    chars = 0
    if loaded:
        chars = len(path.read_text(encoding="utf-8"))
    return {
        "enabled": enabled,
        "loaded": loaded,
        "path": str(path),
        "chars": chars,
    }


def load_references() -> dict:
    if not REFERENCES_JSON.is_file():
        return {"references": []}
    return json.loads(REFERENCES_JSON.read_text(encoding="utf-8"))
