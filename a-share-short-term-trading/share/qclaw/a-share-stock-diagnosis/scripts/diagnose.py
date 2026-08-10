#!/usr/bin/env python3
"""Installation-neutral wrapper for the QClaw diagnosis command."""

from pathlib import Path
import sys


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT))

from a_share_stock_diagnosis.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

