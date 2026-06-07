"""分时段草稿批次配置。"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_draft_batch import SCHEDULE_BATCHES, resolve_scheduled_batch

TZ = ZoneInfo("Asia/Shanghai")


def test_schedule_batches_evening() -> None:
    assert tuple(SCHEDULE_BATCHES["evening"]["kinds"]) == (
        "sector",
        "dragons",
        "top5",
    )
    assert len(SCHEDULE_BATCHES["evening"]["kinds"]) == 3
    assert SCHEDULE_BATCHES["evening"]["edition"] == "close"
    assert SCHEDULE_BATCHES["evening"]["dragon_slot"] == "eod"


def test_schedule_batches_weekend() -> None:
    assert tuple(SCHEDULE_BATCHES["weekend"]["kinds"]) == ("news",)
    assert SCHEDULE_BATCHES["weekend"]["edition"] is None
    assert SCHEDULE_BATCHES["weekend"]["dragon_slot"] is None
    assert tuple(SCHEDULE_BATCHES["weekend_skip"]["kinds"]) == ()


def test_resolve_scheduled_batch_weekday() -> None:
    wed = datetime(2026, 6, 3, 19, 0, tzinfo=TZ)
    assert resolve_scheduled_batch(now=wed) == "evening"


def test_resolve_scheduled_batch_weekend() -> None:
    sat = datetime(2026, 6, 6, 19, 0, tzinfo=TZ)
    sun = datetime(2026, 6, 7, 19, 0, tzinfo=TZ)
    assert resolve_scheduled_batch(now=sat) == "weekend_skip"
    assert resolve_scheduled_batch(now=sun) == "weekend"
