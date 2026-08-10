"""HarryPutter env (HARRYPUTTER_* preferred; READALONG_* legacy fallback)."""

from __future__ import annotations

import os


def hp_env(name: str, default: str = "") -> str:
    return os.environ.get(f"HARRYPUTTER_{name}") or os.environ.get(f"READALONG_{name}", default)
