#!/usr/bin/env python3
"""Compatibility entry for the canonical manual short-term selector."""

from __future__ import annotations

from pathlib import Path
import runpy
import sys


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_ENTRY = (
    WORKSPACE_ROOT
    / "a-share-short-term-trading"
    / "scripts"
    / "select_short_term_candidates.py"
)


def main() -> int:
    namespace = runpy.run_path(str(CANONICAL_ENTRY))
    return namespace["main"](sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
