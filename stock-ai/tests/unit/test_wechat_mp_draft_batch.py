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
        "news",
        "hotspot",
    )
    assert len(SCHEDULE_BATCHES["evening"]["kinds"]) == 2
    assert SCHEDULE_BATCHES["evening"]["edition"] == "close"
    assert SCHEDULE_BATCHES["evening"]["dragon_slot"] is None


def test_schedule_batches_weekend() -> None:
    assert tuple(SCHEDULE_BATCHES["weekend"]["kinds"]) == ("hotspot",)
    assert SCHEDULE_BATCHES["weekend"]["edition"] == "close"
    assert SCHEDULE_BATCHES["weekend"]["dragon_slot"] is None
    assert tuple(SCHEDULE_BATCHES["weekend_skip"]["kinds"]) == ()


def test_schedule_batches_hotspot_early() -> None:
    assert tuple(SCHEDULE_BATCHES["hotspot_early"]["kinds"]) == ("hotspot",)
    assert SCHEDULE_BATCHES["hotspot_early"]["edition"] == "pre"
    assert SCHEDULE_BATCHES["hotspot_early"]["slot_key"] == "hotspot_early"


def test_schedule_batches_hotspot_afternoon() -> None:
    assert tuple(SCHEDULE_BATCHES["hotspot_afternoon"]["kinds"]) == ("hotspot",)
    assert SCHEDULE_BATCHES["hotspot_afternoon"]["edition"] == "midday"
    assert SCHEDULE_BATCHES["hotspot_afternoon"]["dragon_slot"] is None
    assert SCHEDULE_BATCHES["hotspot_afternoon"]["slot_key"] == "hotspot_afternoon"


def test_schedule_batches_hotspot_morning_evening() -> None:
    assert SCHEDULE_BATCHES["hotspot_morning"]["edition"] == "pre"
    assert SCHEDULE_BATCHES["hotspot_evening"]["edition"] == "close"
    assert tuple(SCHEDULE_BATCHES["hotspot_evening"]["kinds"]) == ("hotspot",)
    assert SCHEDULE_BATCHES["hotspot_morning"]["slot_key"] == "hotspot_morning"
    assert SCHEDULE_BATCHES["hotspot_evening"]["slot_key"] == "hotspot_evening"


def test_apply_batch_env_hotspot_slots_social_figures(monkeypatch) -> None:
    from scripts.tools.wechat_mp_draft_batch import _apply_batch_env

    for key in (
        "WECHAT_MP_DISCUSSION_FIGURES",
        "WECHAT_MP_DISCUSSION_BODY_FIGURES",
        "WECHAT_MP_HOTSPOT_SOCIAL_FIGURES",
        "WECHAT_MP_TV_PICK_MODE",
    ):
        monkeypatch.delenv(key, raising=False)
    for batch in ("hotspot_early", "hotspot_morning", "hotspot_afternoon", "hotspot_evening"):
        monkeypatch.delenv("WECHAT_MP_DISCUSSION_FIGURES", raising=False)
        monkeypatch.delenv("WECHAT_MP_DISCUSSION_BODY_FIGURES", raising=False)
        _apply_batch_env(batch)
        import os

        assert os.environ.get("WECHAT_MP_DISCUSSION_FIGURES") == "1"
        assert os.environ.get("WECHAT_MP_DISCUSSION_BODY_FIGURES") == "3"
        assert os.environ.get("WECHAT_MP_HOTSPOT_SOCIAL_FIGURES") == "1"
        assert os.environ.get("WECHAT_MP_TV_PICK_MODE") is None


def test_schedule_batches_tv_trial() -> None:
    assert tuple(SCHEDULE_BATCHES["tv_trial"]["kinds"]) == ("tv_review",)


def test_apply_batch_env_weekend_hotspot_not_hot_stock_news(monkeypatch) -> None:
    from scripts.tools.wechat_mp_draft_batch import _apply_batch_env

    monkeypatch.delenv("WECHAT_MP_HOT_STOCK_NEWS", raising=False)
    _apply_batch_env("weekend")
    import os

    assert os.environ.get("WECHAT_MP_HOT_STOCK_NEWS") is None
    assert os.environ.get("WECHAT_MP_NEWS_BATCH") == "weekend"


def test_apply_batch_env_hotspot_morning(monkeypatch) -> None:
    from scripts.tools.wechat_mp_draft_batch import _apply_batch_env

    monkeypatch.delenv("WECHAT_MP_HOTSPOT_SOURCE", raising=False)
    _apply_batch_env("hotspot_morning")
    import os

    assert os.environ.get("WECHAT_MP_HOTSPOT_SOURCE") == "trends"
    assert os.environ.get("WECHAT_MP_STOCK_AI_CTA") == "0"


def test_apply_batch_env_evening_enables_hot_stock_news(monkeypatch) -> None:
    from scripts.tools.wechat_mp_draft_batch import _apply_batch_env

    monkeypatch.setenv("WECHAT_MP_WEEKEND_NEWS", "0")
    _apply_batch_env("evening")
    import os

    assert os.environ.get("WECHAT_MP_HOT_STOCK_NEWS") == "1"
    assert os.environ.get("WECHAT_MP_NEWS_BATCH") == "evening"


def test_resolve_scheduled_batch_weekday() -> None:
    wed = datetime(2026, 6, 3, 19, 0, tzinfo=TZ)
    assert resolve_scheduled_batch(now=wed) == "evening"


def test_resolve_scheduled_batch_weekend(monkeypatch) -> None:
    import scripts.tools.wechat_mp_tv_review_article
    monkeypatch.setattr(scripts.tools.wechat_mp_tv_review_article, "tv_trial_active", lambda **kwargs: False)

    sat = datetime(2026, 6, 6, 19, 0, tzinfo=TZ)
    sun = datetime(2026, 6, 7, 19, 0, tzinfo=TZ)
    assert resolve_scheduled_batch(now=sat) == "weekend_skip"
    assert resolve_scheduled_batch(now=sun) == "weekend"
