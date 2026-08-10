"""公众号五槽位草稿：优先 update，否则 add 并替换 media_id。"""

from __future__ import annotations

import json
import re
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
    draft_first_title,
    draft_update,
    list_all_drafts,
    normalize_draft_text,
)
from scripts.tools.wechat_mp_content import DRAFT_KINDS

TZ = ZoneInfo("Asia/Shanghai")
SLOTS_PATH = ROOT / "data" / "wechat_mp_draft_slots.json"

# 定时四篇热点稿各占一槽，避免 upsert 时删掉同日其它时段草稿
HOTSPOT_SCHEDULE_SLOT_KEYS: tuple[str, ...] = (
    "hotspot_early",
    "hotspot_morning",
    "hotspot_afternoon",
    "hotspot_evening",
)

# 用于识别「本脚本管理的草稿」，避免误删人工撰写的其他草稿
_KIND_TITLE_HINTS: dict[str, tuple[str, ...]] = {
    "hotspot": (
        "热点深评",
        "网上在吵",
        "舆情",
        "盘面",
        "热点",
    ),
    "sector": (
        "行业",
        "产业链",
        "热点行业",
        "量价",
        "行业研究",
        "A股行业",
    ),
    "market": (
        "市场评论",
        "宏观",
        "收盘",
        "盘中",
        "必读",
        "别漏看",
        "盘面",
        "霍尔木兹",
        "中东",
        "结构判断",
    ),
    "news": (
        "要闻",
        "快讯",
        "7×24",
        "精选",
        "评论最高",
        "AI 解读",
        "地缘",
        "财经",
    ),
    "top5": (
        "选股",
        "Top5",
        "TOP5",
        "甄选",
        "领衔",
        "盯啥",
        "信号",
    ),
    "dragons": (
        "龙头",
        "情绪",
        "退潮",
        "板还在",
        "游资",
    ),
    "workspace": (
        "工作区",
        "工具工作区",
        "技术分享",
        "自动化",
        "git",
        "仓库",
        "全景",
    ),
    "temp": (
        "飞书",
        "lark",
        "CLI",
        "OpenAPI",
        "临稿",
        "临时",
        "Agent",
        "自建应用",
    ),
    "guba": (
        "东财股吧",
        "股吧",
        "产业链怎么读",
        "产业链怎么拆",
        "向后看",
        "盘面样本",
    ),
    "tv_review": (
        "HBO",
        "Netflix",
        "美剧",
        "电影",
        "值不值得",
        "开刷",
        "追完",
        "安利",
    ),
}


def _load_slots() -> dict[str, Any]:
    if not SLOTS_PATH.is_file():
        return {"version": 1, "slots": {}}
    try:
        return json.loads(SLOTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "slots": {}}


def _save_slots(data: dict[str, Any]) -> None:
    SLOTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(TZ).isoformat(timespec="seconds")
    SLOTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def classify_draft_kind(title: str) -> str | None:
    title = normalize_draft_text(title)
    if not title:
        return None
    scores: dict[str, int] = {}
    for kind, hints in _KIND_TITLE_HINTS.items():
        scores[kind] = sum(1 for h in hints if h in title)
    best = max(scores.items(), key=lambda x: x[1])
    if best[1] <= 0:
        return None
    return best[0]


def is_managed_draft_title(title: str) -> bool:
    return classify_draft_kind(title) is not None


def managed_slot_keys() -> tuple[str, ...]:
    """草稿 prune 保留的槽位键（含定时热点三槽 + 各 kind 默认槽）。"""
    from scripts.tools.wechat_mp_content import DRAFT_KINDS

    keys: list[str] = list(HOTSPOT_SCHEDULE_SLOT_KEYS)
    for k in DRAFT_KINDS:
        if k not in keys:
            keys.append(k)
    return tuple(keys)


def get_slot_media_id(kind: str) -> str | None:
    slots = _load_slots().get("slots") or {}
    entry = slots.get(kind) or {}
    mid = str(entry.get("media_id") or "").strip()
    return mid or None


def set_slot_media_id(kind: str, media_id: str, *, title: str = "") -> None:
    data = _load_slots()
    slots = dict(data.get("slots") or {})
    slots[kind] = {
        "media_id": media_id,
        "title": title[:64],
        "updated_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }
    data["slots"] = slots
    _save_slots(data)


def upsert_draft_article(
    kind: str,
    article: dict[str, Any],
    *,
    thumb_media_id: str,
    slot_key: str | None = None,
) -> tuple[str | None, str, dict[str, Any] | None]:
    """
    更新或新建草稿。返回 (media_id, action, error)。
    action: updated | created

    slot_key: 槽位键，默认同 kind；定时热点三篇用 hotspot_morning 等分槽。
    """
    from scripts.tools.wechat_mp_product import draft_article_payload

    item = draft_article_payload(article)
    item["thumb_media_id"] = thumb_media_id
    attach_cover_crop_fields(item, thumb_media_id=thumb_media_id)

    slot = (slot_key or kind).strip()
    old_id = get_slot_media_id(slot)
    if old_id:
        draft_delete(media_id=old_id)

    new_id, err = draft_add(articles=[item])
    if err:
        return None, "failed", err
    if new_id:
        set_slot_media_id(slot, new_id, title=str(item.get("title") or ""))
    action = "recreated" if old_id else "created"
    return new_id, action, None


def prune_extra_managed_drafts(
    *,
    keep_media_ids: set[str],
    dry_run: bool = False,
) -> tuple[int, list[str]]:
    """删除草稿箱里多余的「本脚本」草稿（保留 keep_media_ids）。"""
    items, err = list_all_drafts()
    if err:
        return 0, [f"拉取失败: {err}"]

    author = __import__("os").getenv("WECHAT_MP_AUTHOR", "R2D2").strip()
    to_delete: list[tuple[str, str]] = []

    for it in items:
        media_id = str(it.get("media_id") or "")
        if not media_id or media_id in keep_media_ids:
            continue
        title = draft_first_title(it)
        if not is_managed_draft_title(title):
            continue
        content = it.get("content") or {}
        news = (content.get("news_item") or [{}])[0]
        item_author = str(news.get("author") or "").strip()
        if author and item_author and item_author != author:
            continue
        to_delete.append((media_id, title))

    if dry_run:
        return len(to_delete), [t for _, t in to_delete]

    deleted = 0
    for media_id, _title in to_delete:
        derr = draft_delete(media_id=media_id)
        if derr:
            continue
        deleted += 1
    return deleted, []


def sync_all_slots_after_run(*, dry_run: bool = False) -> None:
    keep = {mid for k in managed_slot_keys() if (mid := get_slot_media_id(k))}
    prune_extra_managed_drafts(keep_media_ids=keep, dry_run=dry_run)
