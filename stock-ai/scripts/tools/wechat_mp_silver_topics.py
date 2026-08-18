"""银发栏目的常青选题库与可复现轮换。"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.tools.wechat_mp_codex_silver import SILVER_LANES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOPICS_PATH = PROJECT_ROOT / "data" / "wechat_mp_silver_topics.json"
USAGE_PATH = PROJECT_ROOT / "data" / "wechat_mp_silver_topic_usage.json"
RECENT_WINDOW = timedelta(days=30)
_LANE_ORDER = {"relation": 0, "health": 1, "money": 2}


@dataclass(frozen=True)
class SilverTopic:
    topic_id: str
    lane: str
    title: str
    reader_problem: str
    search_terms: tuple[str, ...]
    scene_prompt: str
    risk_notes: tuple[str, ...]


def _text(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"银发选题字段 {field} 必须是非空字符串")
    return value.strip()


def _text_list(row: dict[str, Any], field: str) -> tuple[str, ...]:
    value = row.get(field)
    if not isinstance(value, list) or not value or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"银发选题字段 {field} 必须是非空字符串数组")
    return tuple(item.strip() for item in value)


def load_silver_topics(path: Path = TOPICS_PATH) -> tuple[SilverTopic, ...]:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"银发选题库 JSON 无效: {source}: {exc.msg}") from exc
    if not isinstance(data, list) or not data:
        raise ValueError("银发选题库必须是非空数组")
    topics: list[SilverTopic] = []
    seen: set[str] = set()
    for row in data:
        if not isinstance(row, dict):
            raise ValueError("银发选题库每一项必须是对象")
        lane = _text(row, "lane")
        if lane not in SILVER_LANES:
            raise ValueError(f"银发选题 lane 无效: {lane}")
        topic_id = _text(row, "topic_id")
        if topic_id in seen:
            raise ValueError(f"银发选题 topic_id 重复: {topic_id}")
        seen.add(topic_id)
        topics.append(
            SilverTopic(
                topic_id=topic_id,
                lane=lane,
                title=_text(row, "title"),
                reader_problem=_text(row, "reader_problem"),
                search_terms=_text_list(row, "search_terms"),
                scene_prompt=_text(row, "scene_prompt"),
                risk_notes=_text_list(row, "risk_notes"),
            )
        )
    return tuple(topics)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _load_usage(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"银发选题使用记录 JSON 无效: {path}: {exc.msg}") from exc
    if not isinstance(data, list):
        raise ValueError("银发选题使用记录必须是数组")
    rows: list[dict[str, str]] = []
    for row in data:
        if not isinstance(row, dict) or not all(
            isinstance(row.get(key), str) and row[key].strip()
            for key in ("topic_id", "lane", "used_at")
        ):
            raise ValueError("银发选题使用记录格式无效")
        try:
            datetime.fromisoformat(row["used_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("银发选题使用记录 used_at 无效") from exc
        rows.append({key: row[key].strip() for key in ("topic_id", "lane", "used_at")})
    return rows


def _usage_times(rows: list[dict[str, str]]) -> list[tuple[dict[str, str], datetime]]:
    return [
        (row, _as_utc(datetime.fromisoformat(row["used_at"].replace("Z", "+00:00"))))
        for row in rows
    ]


def pick_silver_topic(
    lane: str | None = None,
    *,
    now: datetime | None = None,
    topics_path: Path = TOPICS_PATH,
    usage_path: Path = USAGE_PATH,
) -> SilverTopic:
    if lane is not None and lane not in SILVER_LANES:
        raise ValueError(f"银发选题 lane 必须是 {sorted(SILVER_LANES)} 之一")
    current = _as_utc(now or datetime.now(timezone.utc))
    topics = load_silver_topics(topics_path)
    usage = _usage_times(_load_usage(Path(usage_path)))

    last_by_topic: dict[str, datetime] = {}
    last_by_lane: dict[str, datetime] = {}
    for row, used_at in usage:
        last_by_topic[row["topic_id"]] = max(used_at, last_by_topic.get(row["topic_id"], datetime.min.replace(tzinfo=timezone.utc)))
        last_by_lane[row["lane"]] = max(used_at, last_by_lane.get(row["lane"], datetime.min.replace(tzinfo=timezone.utc)))

    def is_eligible(topic: SilverTopic) -> bool:
        return topic.topic_id not in last_by_topic or (
            current - last_by_topic[topic.topic_id] >= RECENT_WINDOW
        )

    if lane is None:
        available_lanes = {topic.lane for topic in topics if is_eligible(topic)}
        if not available_lanes:
            raise ValueError("银发选题库没有 30 天内未使用的选题")
        lane = min(
            available_lanes,
            key=lambda item: (
                last_by_lane.get(item, datetime.min.replace(tzinfo=timezone.utc)),
                _LANE_ORDER[item],
            ),
        )

    eligible = [
        topic
        for topic in topics
        if topic.lane == lane
        and is_eligible(topic)
    ]
    if not eligible:
        raise ValueError(f"银发 {lane} 方向没有 30 天内未使用的选题")
    return min(
        eligible,
        key=lambda topic: (
            last_by_topic.get(topic.topic_id, datetime.min.replace(tzinfo=timezone.utc)),
            topic.topic_id,
        ),
    )


def record_silver_topic_usage(
    topic: SilverTopic,
    *,
    used_at: datetime | None = None,
    usage_path: Path = USAGE_PATH,
) -> None:
    target = Path(usage_path)
    rows = _load_usage(target)
    timestamp = _as_utc(used_at or datetime.now(timezone.utc)).isoformat()
    rows.append({"topic_id": topic.topic_id, "lane": topic.lane, "used_at": timestamp})
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=target.parent, delete=False
    ) as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(target)
