from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.tools.wechat_mp_silver_topics import (
    load_silver_topics,
    pick_silver_topic,
    record_silver_topic_usage,
)

NOW = datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc)


def _topic(topic_id: str, lane: str) -> dict[str, object]:
    return {
        "topic_id": topic_id,
        "lane": lane,
        "title": f"{lane} 的 {topic_id}",
        "reader_problem": f"怎样处理 {topic_id}？",
        "search_terms": [topic_id, lane],
        "scene_prompt": "从一个具体家庭场景开篇",
        "risk_notes": ["不夸大个体经验"],
    }


def _bank(path: Path) -> Path:
    rows = [
        _topic(f"{lane}-{index}", lane)
        for lane in ("relation", "health", "money")
        for index in (1, 2)
    ]
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


def test_pick_respects_lane_and_excludes_topic_used_within_30_days(tmp_path: Path) -> None:
    topics_path = _bank(tmp_path / "topics.json")
    usage_path = tmp_path / "usage.json"
    usage_path.write_text(
        json.dumps(
            [{"topic_id": "health-1", "lane": "health", "used_at": (NOW - timedelta(days=10)).isoformat()}]
        ),
        encoding="utf-8",
    )

    picked = pick_silver_topic(
        lane="health", now=NOW, topics_path=topics_path, usage_path=usage_path
    )

    assert picked.topic_id == "health-2"


def test_default_pick_rotates_to_least_recently_used_lane(tmp_path: Path) -> None:
    topics_path = _bank(tmp_path / "topics.json")
    usage_path = tmp_path / "usage.json"
    usage_path.write_text(
        json.dumps(
            [
                {"topic_id": "relation-1", "lane": "relation", "used_at": (NOW - timedelta(days=40)).isoformat()},
                {"topic_id": "health-1", "lane": "health", "used_at": (NOW - timedelta(days=20)).isoformat()},
                {"topic_id": "money-1", "lane": "money", "used_at": (NOW - timedelta(days=5)).isoformat()},
            ]
        ),
        encoding="utf-8",
    )

    picked = pick_silver_topic(now=NOW, topics_path=topics_path, usage_path=usage_path)

    assert picked.lane == "relation"
    assert picked.topic_id == "relation-2"


def test_topic_becomes_eligible_again_after_30_days(tmp_path: Path) -> None:
    topics_path = _bank(tmp_path / "topics.json")
    usage_path = tmp_path / "usage.json"
    usage_path.write_text(
        json.dumps(
            [
                {"topic_id": "money-1", "lane": "money", "used_at": (NOW - timedelta(days=31)).isoformat()},
                {"topic_id": "money-2", "lane": "money", "used_at": (NOW - timedelta(days=2)).isoformat()},
            ]
        ),
        encoding="utf-8",
    )

    assert pick_silver_topic(
        lane="money", now=NOW, topics_path=topics_path, usage_path=usage_path
    ).topic_id == "money-1"


def test_fails_closed_when_every_eligible_topic_is_recent(tmp_path: Path) -> None:
    topics_path = _bank(tmp_path / "topics.json")
    usage_path = tmp_path / "usage.json"
    usage_path.write_text(
        json.dumps(
            [
                {"topic_id": f"health-{index}", "lane": "health", "used_at": NOW.isoformat()}
                for index in (1, 2)
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="30 天"):
        pick_silver_topic(
            lane="health", now=NOW, topics_path=topics_path, usage_path=usage_path
        )


def test_default_pick_skips_lane_when_all_its_topics_are_recent(tmp_path: Path) -> None:
    topics_path = _bank(tmp_path / "topics.json")
    usage_path = tmp_path / "usage.json"
    usage_path.write_text(
        json.dumps(
            [
                {"topic_id": f"relation-{index}", "lane": "relation", "used_at": NOW.isoformat()}
                for index in (1, 2)
            ]
        ),
        encoding="utf-8",
    )

    picked = pick_silver_topic(now=NOW, topics_path=topics_path, usage_path=usage_path)

    assert picked.lane == "health"


def test_load_rejects_malformed_lane(tmp_path: Path) -> None:
    topics_path = tmp_path / "topics.json"
    topics_path.write_text(json.dumps([_topic("travel-1", "travel")]), encoding="utf-8")

    with pytest.raises(ValueError, match="lane"):
        load_silver_topics(topics_path)


def test_record_usage_appends_stable_row(tmp_path: Path) -> None:
    topic = load_silver_topics(_bank(tmp_path / "topics.json"))[0]
    usage_path = tmp_path / "usage.json"

    record_silver_topic_usage(topic, used_at=NOW, usage_path=usage_path)

    assert json.loads(usage_path.read_text(encoding="utf-8")) == [
        {"topic_id": topic.topic_id, "lane": topic.lane, "used_at": NOW.isoformat()}
    ]
