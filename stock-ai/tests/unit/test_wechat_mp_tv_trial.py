"""影视选题：热度排序与 pick 逻辑。"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_draft_batch import resolve_scheduled_batch
from scripts.tools.wechat_mp_public import audit_recommendation_safety
from scripts.tools.wechat_mp_tv_review_article import build_tv_review_title
from scripts.tools.wechat_mp_tv_topics import (
    CURATED_HOT,
    _score_topic,
    pick_tv_topic,
    rank_topics,
    tv_trial_active,
)


def test_tv_trial_active_when_enabled() -> None:
    assert tv_trial_active(when=datetime(2026, 6, 17, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai")))


def test_resolve_scheduled_batch_tv_trial() -> None:
    # 2026-06-21 is Sunday (off-market), should return tv_trial when active
    batch = resolve_scheduled_batch(
        now=datetime(2026, 6, 21, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert batch == "tv_trial"

    # 2026-06-17 is Wednesday (workday), should return evening (finance) even if tv_trial is active
    batch_weekday = resolve_scheduled_batch(
        now=datetime(2026, 6, 17, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert batch_weekday == "evening"


def test_curated_hot_prefers_euphoria() -> None:
    ranked = rank_topics(CURATED_HOT, on=datetime(2026, 6, 17).date())
    assert ranked[0]["title_en"] == "Euphoria"
    assert ranked[0]["controversy_score"] >= 80


def test_pick_tv_topic_skips_harlots(tmp_path: Path, monkeypatch) -> None:
    trial = tmp_path / "trial.json"
    usage = tmp_path / "usage.json"
    trial.write_text(
        json.dumps(
            {
                "enabled": True,
                "until": "2026-06-24",
                "queue": rank_topics(CURATED_HOT),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    usage.write_text('{"used": {}}', encoding="utf-8")
    monkeypatch.setattr("scripts.tools.wechat_mp_tv_topics.TRIAL_PATH", trial)
    monkeypatch.setattr("scripts.tools.wechat_mp_tv_topics.USAGE_PATH", usage)

    when = datetime(2026, 6, 17, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    topic = pick_tv_topic(when=when)
    assert topic["title_en"] == "Euphoria"
    title = build_tv_review_title(topic, now=when)
    assert audit_recommendation_safety(title=title, body="", digest="") == []
    assert title == "HBO这部青春剧，为什么老观众吵起来了？"
