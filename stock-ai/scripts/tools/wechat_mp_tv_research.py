#!/usr/bin/env python3
"""影视稿联网取材：热搜语境 + 东财/娱乐报道检索。"""

from __future__ import annotations

import os
import re
from typing import Any

from scripts.tools.wechat_mp_hotspot_research import (
    ResearchHit,
    _fetch_eastmoney_search,
    fetch_hotspot_research,
    format_hotspot_research_block,
)


def tv_research_enabled() -> bool:
    raw = (os.getenv("WECHAT_MP_TV_RESEARCH") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _tv_query(title_zh: str, trend_title: str = "") -> str:
    show = (title_zh or "").strip()
    if not show:
        return (trend_title or "")[:12]
    # 东财娱乐稿常带「电视剧」「电影」
    if len(show) <= 6:
        return f"{show} 电视剧"
    return show


def fetch_tv_research(topic: dict[str, Any], *, limit: int = 5) -> list[ResearchHit]:
    """按片名/热搜标题检索可引用报道。"""
    if not tv_research_enabled():
        return []
    title_zh = str(topic.get("title_zh") or "").strip()
    trend = str(topic.get("trend_title") or topic.get("hook") or "").strip()
    query = _tv_query(title_zh, trend)
    if not query:
        return []

    hits = fetch_hotspot_research(query, limit=limit)
    # 过滤明显跑题（地名/金融误匹配）
    show = title_zh or query[:4]
    filtered: list[ResearchHit] = []
    for hit in hits:
        blob = f"{hit.title} {hit.snippet}"
        if show and show not in blob:
            if not any(k in blob for k in ("剧", "电影", "编剧", "豆瓣", "演员", "古偶", "热播")):
                continue
        filtered.append(hit)
    if len(filtered) >= 2:
        return filtered[:limit]

    # 用热搜原句再试一次
    if trend and trend != query:
        extra = _fetch_eastmoney_search(trend[:16], limit=limit + 2)
        seen = {re.sub(r"\s+", "", h.title)[:20] for h in filtered}
        for hit in extra:
            key = re.sub(r"\s+", "", hit.title)[:20]
            if key in seen:
                continue
            blob = f"{hit.title} {hit.snippet}"
            if show in blob or any(k in blob for k in ("剧", "编剧", "豆瓣", "魔改")):
                filtered.append(hit)
                seen.add(key)
    return filtered[:limit]


def format_tv_trend_context_block(topic: dict[str, Any]) -> str:
    """把热搜排名写进 prompt，不进入正文。"""
    trend = str(topic.get("trend_title") or "").strip()
    if not trend and not topic.get("from_trend"):
        return ""
    ranks = topic.get("trend_ranks") or {}
    bits = [f"{src}第{rank}" for src, rank in sorted(ranks.items(), key=lambda x: x[1])]
    rank_txt = "、".join(bits) if bits else "热搜榜"
    lines = [
        "【热搜语境】（融入开篇热度数字，勿写「热搜在聊」「双榜讨论」等套话）",
        f"- 词条：{trend or topic.get('title_zh')}",
        f"- 排名：{rank_txt}",
    ]
    for ang in (topic.get("reference_angles") or [])[:3]:
        lines.append(f"- {ang}")
    return "\n".join(lines)


def format_tv_reference_imitation_block(hits: list[ResearchHit]) -> str:
    """影视向仿写指引（学节奏，不照搬）。"""
    if not hits:
        return ""
    lines = [
        "【参考报道·仿写】先读 IGN 中国等同题剧评（见 skill tv-review-voice.md），学节奏再写：",
        "- 开篇：时间差 / 一个记得住的画面 / 内地没上前作（择一）；禁止百科复习体；",
        "- 段落：每段 2～4 句连成一块；先场面后判断；禁止一句一段；",
        "- 中段：具体桥段 + 一句评价；评分嵌进叙述，勿竖排外再念一遍；",
        "- 口吻：大白话、长短句交错；禁戏眼/意象/正向反馈/剧情承接；",
        "- 末段：试看场次 + 口语问句。",
        "禁止：小编体、对称金句、半句话、假共情、第一人称「我」。",
        "",
    ]
    for i, hit in enumerate(hits[:3], 1):
        body = hit.snippet[:520] + ("…" if len(hit.snippet) > 520 else "")
        lines.extend(
            [
                f"--- 参考{i}｜{hit.source}《{hit.title}》 ---",
                body,
                "",
            ]
        )
    return "\n".join(lines).strip()


def format_tv_research_bundle(topic: dict[str, Any], hits: list[ResearchHit]) -> str:
    parts = [
        format_tv_trend_context_block(topic),
        format_hotspot_research_block(hits) if hits else "",
        format_tv_reference_imitation_block(hits),
    ]
    return "\n\n".join(p for p in parts if p).strip()
