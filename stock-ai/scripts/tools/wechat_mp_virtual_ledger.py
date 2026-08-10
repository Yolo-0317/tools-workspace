"""栀夏草稿待发表记录与正式发表台账。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from scripts.tools.wechat_mp_client import ROOT


TZ = ZoneInfo("Asia/Shanghai")
PENDING_PATH = ROOT / "data" / "wechat_mp_virtual_lifestyle_pending.json"
HISTORY_PATH = ROOT / "data" / "wechat_mp_virtual_lifestyle_history.json"


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_virtual_history(path: Path = HISTORY_PATH) -> dict[str, Any]:
    if not path.is_file():
        return {"sequence": 0, "round": 1, "posts": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"栀夏发表台账无效: {path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("posts"), list):
        raise ValueError(f"栀夏发表台账结构无效: {path}")
    return payload


def record_pending_draft(
    *,
    media_id: str,
    title: str,
    topic_card: Mapping[str, Any],
    topic_card_sha256: str,
    drafted_at: datetime | None = None,
    mix_override_reason: str = "",
    pending_path: Path = PENDING_PATH,
) -> dict[str, Any]:
    timestamp = drafted_at or datetime.now(TZ)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=TZ)
    payload: dict[str, Any] = {
        "media_id": media_id.strip(),
        "title": title.strip(),
        "content_type": str(topic_card.get("content_type") or "").strip(),
        "topic": str(topic_card.get("topic") or "").strip(),
        "topic_card_sha256": topic_card_sha256.strip(),
        "drafted_at": timestamp.isoformat(timespec="seconds"),
        "mix_override_reason": mix_override_reason.strip(),
    }
    if not all(
        payload[field]
        for field in ("media_id", "title", "content_type", "topic", "topic_card_sha256")
    ):
        raise ValueError("栀夏待发表记录字段不完整")
    _write_json_atomic(pending_path, payload)
    return payload


def _publication_title(publication: Mapping[str, Any]) -> str:
    content = publication.get("content")
    if not isinstance(content, Mapping):
        return ""
    news_items = content.get("news_item")
    if not isinstance(news_items, list) or not news_items:
        return ""
    first = news_items[0]
    if not isinstance(first, Mapping):
        return ""
    return str(first.get("title") or "").strip()


def _publication_time(publication: Mapping[str, Any]) -> datetime | None:
    try:
        timestamp = int(publication.get("update_time") or 0)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    return datetime.fromtimestamp(timestamp, tz=TZ)


def match_pending_publication(
    pending: Mapping[str, Any],
    published_items: list[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """按精确标题和不早于草稿的发表时间匹配正式发表记录。"""
    title = str(pending.get("title") or "").strip()
    try:
        drafted_at = datetime.fromisoformat(str(pending.get("drafted_at") or ""))
    except ValueError as exc:
        raise ValueError("栀夏待发表记录 drafted_at 无效") from exc
    if drafted_at.tzinfo is None:
        raise ValueError("栀夏待发表记录 drafted_at 须包含时区")
    candidates: list[tuple[datetime, Mapping[str, Any]]] = []
    for publication in published_items:
        published_at = _publication_time(publication)
        if (
            str(publication.get("article_id") or "").strip()
            and _publication_title(publication) == title
            and published_at is not None
            and published_at >= drafted_at
        ):
            candidates.append((published_at, publication))
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])[1]


def record_verified_publication(
    *,
    pending: Mapping[str, Any],
    publication: Mapping[str, Any],
    ledger_path: Path = HISTORY_PATH,
) -> dict[str, Any]:
    """把已核验的正式发表追加到台账；同一 article_id 幂等。"""
    article_id = str(publication.get("article_id") or "").strip()
    if not article_id:
        raise ValueError("正式发表记录缺少 article_id")
    matched = match_pending_publication(pending, [publication])
    if matched is None:
        raise ValueError("正式发表记录与待发表草稿不匹配")

    ledger = load_virtual_history(ledger_path)
    for post in ledger["posts"]:
        if str(post.get("article_id") or "") == article_id:
            return ledger

    sequence = int(ledger.get("sequence") or 0) + 1
    round_number = ((sequence - 1) // 10) + 1
    experiment_variable = str(pending.get("experiment_variable") or "").strip()
    existing_variables = {
        str(post.get("experiment_variable") or "").strip()
        for post in ledger["posts"]
        if int(post.get("round") or 0) == round_number
        and str(post.get("experiment_variable") or "").strip()
    }
    if experiment_variable and existing_variables and experiment_variable not in existing_variables:
        raise ValueError("每轮只能调整一个变量")
    active_experiment = experiment_variable or next(iter(existing_variables), "")

    status = str(pending.get("status") or "published").strip()
    if status not in {"published", "invalid"}:
        raise ValueError("栀夏发表状态须为 published / invalid")
    published_at = _publication_time(publication)
    if published_at is None:
        raise ValueError("正式发表记录 update_time 无效")
    post = {
        "article_id": article_id,
        "post_no": f"ZX-{sequence:03d}",
        "content_type": str(pending.get("content_type") or "").strip(),
        "title": str(pending.get("title") or "").strip(),
        "published_at": published_at.isoformat(timespec="seconds"),
        "status": status,
        "round": round_number,
        "experiment_variable": active_experiment,
    }
    if not post["content_type"] or not post["title"]:
        raise ValueError("栀夏正式发表记录字段不完整")
    ledger["posts"].append(post)
    ledger["sequence"] = sequence
    ledger["round"] = round_number
    ledger["experiment_variable"] = active_experiment
    _write_json_atomic(ledger_path, ledger)
    return ledger
