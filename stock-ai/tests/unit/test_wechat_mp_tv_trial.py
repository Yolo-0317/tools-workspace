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


def test_nanjing_photo_studio_builds_fixed_public_title() -> None:
    topic = next(t for t in CURATED_HOT if t["title_en"] == "Nanjing Photo Studio")

    assert topic["title_zh"] == "南京照相馆"
    assert topic["cover_slug"] == "nanjing-photo-studio"
    assert topic["type"] == "film"
    assert topic["douban_subject_id"] == "36809864"
    title = build_tv_review_title(
        topic,
        now=datetime(2026, 8, 15, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    assert title == "《南京照相馆》：底片不能烧"
    assert len(title) <= 20


def test_odyssey_builds_fixed_public_title_and_explicit_topic() -> None:
    topic = next(t for t in CURATED_HOT if t["title_en"] == "The Odyssey")

    assert topic["title_zh"] == "奥德赛"
    assert topic["cover_slug"] == "the-odyssey-2026"
    assert topic["type"] == "film"
    assert topic["year"] == "2026"
    title = build_tv_review_title(
        topic,
        now=datetime(2026, 8, 16, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    assert title == "《奥德赛》：回家不是凯旋"
    assert len(title) <= 20


def test_niu_lai_builds_fixed_public_title() -> None:
    topic = next(t for t in CURATED_HOT if t["title_en"] == "Niu Lai")

    assert topic["title_zh"] == "牛来"
    assert topic["cover_slug"] == "niu-lai"
    assert topic["type"] == "film"
    assert topic["year"] == "2026"
    assert topic["title_override"] == "《牛来》笑到后来，有点难受"
    assert len(topic["title_override"]) <= 20


def test_devil_wears_prada_builds_fixed_public_title() -> None:
    topic = next(t for t in CURATED_HOT if t["title_en"] == "The Devil Wears Prada")

    assert topic["title_zh"] == "穿普拉达的女王"
    assert topic["cover_slug"] == "the-devil-wears-prada"
    assert topic["type"] == "film"
    assert topic["year"] == "2006"
    assert topic["title_override"] == "20年后，安迪为什么离开"
    assert len(topic["title_override"]) <= 20


def test_explicit_curated_topic_override_wins_before_live_discussion(
    tmp_path: Path, monkeypatch
) -> None:
    trial = tmp_path / "trial.json"
    trial.write_text('{"enabled": true, "queue": []}', encoding="utf-8")
    monkeypatch.setattr("scripts.tools.wechat_mp_tv_topics.TRIAL_PATH", trial)
    monkeypatch.setenv("WECHAT_MP_TV_TOPIC", "南京照相馆")
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_tv_trend_topics.build_known_tv_topic",
        lambda _: None,
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_tv_trend_topics.fetch_tv_trend_topics",
        lambda **_: [],
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_tv_morning_discussion.pick_morning_discussion_topic",
        lambda **_: {"title_zh": "不相关实时话题", "content_mode": "discussion"},
    )
    monkeypatch.setattr(
        "scripts.tools.wechat_mp_tv_morning_discussion.tv_morning_pick_mode",
        lambda: "discussion",
    )

    topic = pick_tv_topic(
        when=datetime(2026, 8, 15, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    )

    assert topic["title_en"] == "Nanjing Photo Studio"


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
