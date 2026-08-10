#!/usr/bin/env python3
"""11:00 批次：双榜热搜 → 关注度最高、可写的文娱/话题讨论选题。"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from scripts.tools.wechat_mp_hot_trends import (
    _GOSSIP_TREND_DOWNRANK,
    fetch_baidu_hot,
    fetch_weibo_hot,
    merge_and_rank_trends,
)
from scripts.tools.wechat_mp_tv_trend_topics import (
    _slugify,
    is_tv_trend,
    merge_tv_trends,
    trend_item_to_topic,
)

TZ = ZoneInfo("Asia/Shanghai")

# 硬性排除：财经快评、灾难事故、时政军事（民生个案不在此列）
_DISCUSSION_EXCLUDE: tuple[str, ...] = (
    "A股",
    "沪指",
    "创业板",
    "科创",
    "芯片",
    "半导体",
    "存储",
    "涨停",
    "跌停",
    "央行",
    "公积金",
    "GDP",
    "战机",
    "黄岩岛",
    "军事",
    "雪崩",
    "失联",
    "身亡",
    "坠楼",
    "火灾",
    "暴力",
    "地锁",
    "政治局",
    "集体学习",
)

# 文娱/社会/职场加分（不必是「剧评片单」）
_DISCUSSION_BOOST: tuple[str, ...] = (
    "剧",
    "电影",
    "影院",
    "票房",
    "豆瓣",
    "综艺",
    "拍戏",
    "演员",
    "上映",
    "定档",
    "开播",
    "收官",
    "暑期档",
    "烂片",
    "神作",
    "Netflix",
    "HBO",
    "漫威",
    "迪士尼",
    "孟子义",
    "曾舜晞",
    # 社会争议（成稿须合规）
    "出轨",
    "试管",
    "胚胎",
    "原配",
    "婚姻",
    "离婚",
    "法院",
    "判决",
    "案件",
    "原告",
    "被告",
    # 职场 / 消费
    "职场",
    "劳动",
    "欠薪",
    "加班",
    "辞退",
    "裁员",
    "仲裁",
    "打工",
    "考公",
    "求职",
    "租房",
    "医美",
    "培训",
    "维权",
    "爆料",
    # 教育 / 游戏
    "高考",
    "学校",
    "幼儿园",
    "育儿",
    "校园",
    "游戏",
    "二次元",
    "短剧",
    "AI",
)


def tv_morning_pick_mode() -> str:
    import os

    return (os.getenv("WECHAT_MP_TV_PICK_MODE") or "discussion").strip().lower()


def _is_excluded(title: str) -> bool:
    blob = (title or "").strip()
    if not blob:
        return True
    return any(kw in blob for kw in _DISCUSSION_EXCLUDE)


def _discussion_bonus(title: str) -> float:
    blob = (title or "").strip()
    bonus = 0.0
    if is_tv_trend(blob):
        bonus += 280.0
    for kw in _DISCUSSION_BOOST:
        if kw in blob:
            bonus += 45.0
    if re.search(r"《[^》]{2,12}》", blob):
        bonus += 120.0
    for kw in _GOSSIP_TREND_DOWNRANK:
        if kw in blob:
            bonus -= 90.0
    return bonus


def _best_trend_rank(item: dict[str, Any]) -> int:
    ranks = item.get("ranks") or {}
    if not ranks:
        return 99
    return min(int(v) for v in ranks.values())


def fetch_discussion_candidates(*, limit: int = 15) -> list[dict[str, Any]]:
    """双榜合并后按 attention_score + 文娱话题加权排序。"""
    try:
        weibo = fetch_weibo_hot(limit=50)
        baidu = fetch_baidu_hot(limit=50)
    except Exception:
        return []
    items = merge_and_rank_trends(weibo, baidu, limit=50)
    scored: list[tuple[float, dict[str, Any]]] = []
    for item in items:
        title = str(item.get("title") or "").strip()
        if not title or _is_excluded(title):
            continue
        base = float(item.get("attention_score") or 0.0)
        bonus = _discussion_bonus(title)
        best_rank = _best_trend_rank(item)
        # 无关键词时仍保留双榜中游好题（约 Top25）
        if bonus <= 0 and not is_tv_trend(title) and best_rank > 25:
            continue
        total = base + bonus
        row = dict(item)
        row["discussion_score"] = total
        scored.append((total, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in scored[:limit]]


def _subject_from_title(title: str) -> str:
    blob = (title or "").strip()
    m = re.search(r"《([^》]{2,16})》", blob)
    if m:
        return m.group(1).strip()
    for sep in ("，", ",", "：", ":", " "):
        if sep in blob:
            left = blob.split(sep, 1)[0].strip()
            if 2 <= len(left) <= 14:
                return left
    return blob[:10].strip()


def discussion_item_to_topic(item: dict[str, Any], *, on: date | None = None) -> dict[str, Any]:
    on = on or datetime.now(TZ).date()
    trend = str(item.get("title") or "").strip()
    subject = _subject_from_title(trend)
    ranks = item.get("ranks") or {}
    sources = list(item.get("sources") or [])
    rank_txt = "、".join(f"{k}#{v}" for k, v in sorted(ranks.items(), key=lambda x: x[1]))
    score = float(item.get("discussion_score") or item.get("attention_score") or 0.0)

    return {
        "title_zh": subject,
        "title_en": "",
        "platform": "话题",
        "type": "discussion",
        "year": str(on.year),
        "cover_slug": _slugify(subject) or "tv-discussion",
        "content_mode": "discussion",
        "from_discussion_trend": True,
        "from_trend": True,
        "trend_title": trend,
        "trend_sources": sources,
        "trend_ranks": ranks,
        "attention_score": float(item.get("attention_score") or 0.0),
        "discussion_score": score,
        "heat_score": min(99, max(60, int(score / 40))),
        "controversy_score": 75,
        "write_score": 80,
        "hook": trend if len(trend) <= 48 else f"{rank_txt}热议：{subject}",
        "reference_angles": [
            f"{'+'.join(sources) or '热搜'}：{trend}",
            f"讨论分 discussion_score={score:.0f}",
        ],
        "sources": [f"微博/百度热搜：{trend}"],
        "hot_until": (on + timedelta(days=14)).isoformat(),
    }


def pick_morning_discussion_topic(*, when: datetime | None = None) -> dict[str, Any]:
    """取当日关注度最高的可写话题（跳过近期已写）。"""
    from scripts.tools.wechat_mp_tv_topics import _load_usage, _save_usage, _topic_key

    when = when or datetime.now(TZ)
    today = when.date()
    candidates = fetch_discussion_candidates(limit=20)
    if not candidates:
        # 回退：仅影视向热搜
        try:
            weibo = fetch_weibo_hot(limit=50)
            baidu = fetch_baidu_hot(limit=50)
            tv_items = merge_tv_trends(weibo, baidu, limit=5)
            if tv_items:
                topic = trend_item_to_topic(tv_items[0], on=today)
                topic["content_mode"] = "discussion"
                topic["from_discussion_trend"] = True
                return topic
        except Exception:
            pass
        raise RuntimeError("热搜无可写文娱/话题条目")

    usage = _load_usage()
    used: dict[str, str] = dict(usage.get("used") or {})

    for item in candidates:
        topic = discussion_item_to_topic(item, on=today)
        key = f"discussion:{_topic_key(topic) or topic.get('cover_slug')}"
        if used.get(key) == today.isoformat():
            continue
        used[key] = today.isoformat()
        usage["used"] = used
        _save_usage(usage)
        topic["_discussion_key"] = key
        return topic

    # 全部写过则取最高分
    topic = discussion_item_to_topic(candidates[0], on=today)
    key = f"discussion:{_topic_key(topic) or topic.get('cover_slug')}"
    used[key] = today.isoformat()
    usage["used"] = used
    _save_usage(usage)
    topic["_discussion_key"] = key
    return topic


def preview_morning_discussion(*, limit: int = 8) -> str:
    lines = [f"11:00 话题选题 · {datetime.now(TZ).strftime('%Y-%m-%d %H:%M')}", ""]
    for i, item in enumerate(fetch_discussion_candidates(limit=limit), 1):
        title = str(item.get("title") or "")
        score = float(item.get("discussion_score") or 0.0)
        src = "+".join(item.get("sources") or [])
        lines.append(f"{i}. score={score:.0f} [{src}] {title}")
    if len(lines) == 2:
        lines.append("（无可写条目）")
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="11:00 关注度话题选题预览")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--pick", action="store_true", help="打印今日将选中的 topic JSON")
    args = parser.parse_args()
    if args.pick:
        import json

        print(json.dumps(pick_morning_discussion_topic(), ensure_ascii=False, indent=2))
        return 0
    print(preview_morning_discussion(limit=args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
