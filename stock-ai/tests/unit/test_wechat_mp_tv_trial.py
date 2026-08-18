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


def test_tv_trial_active_respects_enabled_until(tmp_path: Path, monkeypatch) -> None:
    trial = tmp_path / "trial.json"
    trial.write_text(
        '{"enabled": true, "until": "2026-06-24", "queue": []}',
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.tools.wechat_mp_tv_topics.TRIAL_PATH", trial)

    assert tv_trial_active(
        when=datetime(2026, 6, 17, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert not tv_trial_active(
        when=datetime(2026, 6, 25, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )


def test_resolve_scheduled_batch_without_tv_trial(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_tv_topics.TRIAL_PATH",
        tmp_path / "missing-trial.json",
    )

    # 2026-06-21 is Sunday (off-market); missing config keeps the regular weekend batch.
    batch = resolve_scheduled_batch(
        now=datetime(2026, 6, 21, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert batch == "weekend"

    # 2026-06-17 is Wednesday (workday), so the finance evening batch is unchanged.
    batch_weekday = resolve_scheduled_batch(
        now=datetime(2026, 6, 17, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )
    assert batch_weekday == "evening"


def test_curated_hot_ranking_matches_current_scores() -> None:
    on = datetime(2026, 6, 17).date()
    ranked = rank_topics(CURATED_HOT, on=on)

    assert ranked == sorted(ranked, key=_score_topic, reverse=True)
    assert ranked[0]["title_en"] == "Teach You a Lesson"
    assert all(datetime.fromisoformat(topic["hot_until"]).date() >= on for topic in ranked)


def test_pick_tv_topic_skips_harlots(tmp_path: Path, monkeypatch) -> None:
    trial = tmp_path / "trial.json"
    usage = tmp_path / "usage.json"
    when = datetime(2026, 6, 17, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    trial.write_text(
        json.dumps(
            {
                "enabled": True,
                "until": "2026-06-24",
                "queue": rank_topics(CURATED_HOT, on=when.date()),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    usage.write_text('{"used": {}}', encoding="utf-8")
    monkeypatch.setattr("scripts.tools.wechat_mp_tv_topics.TRIAL_PATH", trial)
    monkeypatch.setattr("scripts.tools.wechat_mp_tv_topics.USAGE_PATH", usage)

    topic = pick_tv_topic(when=when)
    assert topic["title_en"] == "Teach You a Lesson"
    title = build_tv_review_title(topic, now=when)
    assert audit_recommendation_safety(title=title, body="", digest="") == []
    assert title == "追完《铁拳教育》，爽完为什么没特痛快？"
