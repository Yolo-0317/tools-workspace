#!/usr/bin/env python3
"""Run built-in lesson TTS prewarm (concurrent). Safe to run while backend is up."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from services.builtin_prewarm import (  # noqa: E402
    builtin_prewarm_stats,
    prewarm_all_builtin,
    prewarm_concurrency,
)


async def main() -> None:
    before = builtin_prewarm_stats()
    print(
        f"before: ready={before['ready']}/{before['total']} "
        f"(concurrency={prewarm_concurrency()})"
    )
    stats = await prewarm_all_builtin()
    after = builtin_prewarm_stats()
    print(
        f"done: +{stats['done']} skipped={stats['skipped']} "
        f"failed={stats['failed']} total_jobs={stats['total']}"
    )
    print(f"after: ready={after['ready']}/{after['total']}")


if __name__ == "__main__":
    asyncio.run(main())
