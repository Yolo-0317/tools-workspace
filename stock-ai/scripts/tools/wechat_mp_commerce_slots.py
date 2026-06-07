"""带货公众号草稿槽位（与五槽财经稿隔离）。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (
    ROOT,
    attach_cover_crop_fields,
    draft_add,
    draft_delete,
)
from scripts.tools.wechat_mp_product import draft_article_payload

TZ = ZoneInfo("Asia/Shanghai")
SLOTS_PATH = ROOT / "data" / "wechat_mp_commerce_slots.json"
COMMERCE_SLOTS = ("guide", "review", "trend")


def _load_slots() -> dict[str, Any]:
    if not SLOTS_PATH.is_file():
        return {"slots": {}}
    try:
        return json.loads(SLOTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"slots": {}}


def _save_slots(data: dict[str, Any]) -> None:
    SLOTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SLOTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_slot_media_id(slot: str) -> str | None:
    key = slot.strip().lower()
    slots = (_load_slots().get("slots") or {})
    entry = slots.get(key) or {}
    mid = str(entry.get("media_id") or "").strip()
    return mid or None


def set_slot_media_id(slot: str, media_id: str, *, title: str = "") -> None:
    key = slot.strip().lower()
    data = _load_slots()
    slots = dict(data.get("slots") or {})
    slots[key] = {
        "media_id": media_id,
        "title": title[:64],
        "updated_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }
    data["slots"] = slots
    _save_slots(data)


def upsert_commerce_draft(
    slot: str,
    article: dict[str, Any],
    *,
    thumb_media_id: str,
) -> tuple[str | None, str, dict[str, Any] | None]:
    """更新或新建带货草稿。返回 (media_id, action, error)。"""
    key = slot.strip().lower()
    if key not in COMMERCE_SLOTS:
        return None, "failed", {
            "errcode": -1,
            "errmsg": f"未知 slot={slot!r}，可选: {', '.join(COMMERCE_SLOTS)}",
        }

    item = draft_article_payload(article)
    item["thumb_media_id"] = thumb_media_id
    attach_cover_crop_fields(item, thumb_media_id=thumb_media_id)

    old_id = get_slot_media_id(key)
    if old_id:
        draft_delete(media_id=old_id)

    new_id, err = draft_add(articles=[item])
    if err:
        return None, "failed", err
    if new_id:
        set_slot_media_id(key, new_id, title=str(item.get("title") or ""))
    action = "recreated" if old_id else "created"
    return new_id, action, None
