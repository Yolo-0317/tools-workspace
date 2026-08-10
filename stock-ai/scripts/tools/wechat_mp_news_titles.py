#!/usr/bin/env python3
"""evening / weekend news 头条标题：热股名前置 + 按日轮换 + 群友好句式（合规）。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


_EVENT_HOOK_REJECT = (
    "人气榜",
    "榜首",
    "人气标的",
    "热股",
    "快讯",
    "同一主题",
)


def _short_event_hook(
    items: list[dict[str, Any]],
    *,
    max_len: int = 10,
    lead: str = "",
    second: str = "",
) -> str:
    """宏观/事件钩子；拒绝把「XX人气榜首」这类股名元叙述当事件。"""
    raw = str((items[0] or {}).get("title") or "").strip()
    if not raw:
        return ""
    raw = re.sub(r"\[[^\]]+\]", "", raw)
    raw = re.sub(r"\s+", "", raw)
    for cut in ("，", "。", "；", "：", "|", " "):
        if cut in raw:
            raw = raw.split(cut, 1)[0]
    if len(raw) < 4:
        return ""
    if any(bad in raw for bad in _EVENT_HOOK_REJECT):
        return ""
    # 事件钩子若已含头条股名，拼进「背景下+双股」必重复
    for name in (lead, second):
        if name and len(name) >= 2 and name in raw:
            return ""
    return raw[:max_len]


def _lead_pair(items: list[dict[str, Any]]) -> tuple[str, str]:
    leads = [
        str(it.get("matched_stock_name") or "").strip()
        for it in items[:4]
        if str(it.get("matched_stock_name") or "").strip()
    ]
    lead = leads[0] if leads else "人气标的"
    second = leads[1] if len(leads) > 1 else ""
    return lead, second


def _rotate(options: list[str], *, day_seed: int, count: int = 6) -> list[str]:
    if not options:
        return []
    n = len(options)
    start = day_seed % n
    out: list[str] = []
    for i in range(min(count, n)):
        out.append(options[(start + i) % n])
    return out


def build_hot_stock_news_title_options(
    items: list[dict[str, Any]],
    *,
    now: datetime,
    n_label: str,
    weekend: bool,
) -> list[list[str]]:
    """返回标题池（外层按优先级尝试）；内层为同日备选。"""
    lead, second = _lead_pair(items)
    event = _short_event_hook(items, lead=lead, second=second)
    day_seed = now.toordinal() + now.weekday() * 17
    pair = bool(second and second != lead)

    if weekend:
        anchor = str((items[0] or {}).get("hot_stock_anchor_label") or "").replace("收盘", "")
        anchor_short = anchor if anchor else "周五"
        base = [
            f"周末值得扫{lead}？{n_label}条快讯对照",
            f"周末{n_label}条｜{lead}这条值得扫一眼？",
            f"{lead}等{anchor_short}人气：{n_label}条周末快讯",
            f"{lead}周末人气高：{n_label}条要闻拆开",
            f"只扫{lead}？周末{n_label}条快讯精选",
        ]
        if pair:
            base.extend(
                [
                    f"{lead}与{second}：周末{n_label}条人气快讯",
                    f"周末快讯｜{lead}和{second}同一主题？",
                    f"{lead}与{second}：{n_label}条周末对照",
                ]
            )
        if event:
            base.append(f"{event}：{lead}等{n_label}条周末快讯")
            if pair:
                base.append(f"周末{event}｜{lead}与{second}")
        rotated = _rotate(base, day_seed=day_seed, count=7)
        return [rotated, base[:4]]

    anchor = str((items[0] or {}).get("hot_stock_anchor_label") or "收盘")
    base = [
        f"{lead}今天有事？{n_label}条{anchor}快讯值得扫",
        f"今天人气在{lead}：{n_label}条快讯对照",
        f"{lead}这条快讯，和盘面有关系吗？",
        f"{lead}牵动什么？{n_label}条收盘解读",
        f"{lead}上人气了，{n_label}条快讯拆开",
        f"今天只看{lead}？{n_label}条快讯逐条拆",
        f"收盘值得看{lead}？{n_label}条快讯拆开",
    ]
    if pair:
        base.extend(
            [
                f"{lead}与{second}：同一条人气线？",
                f"收盘值得看{lead}？还有{second}等{n_label}条",
                f"{lead}与{second}：两条快讯怎么理解",
                f"今夜快讯｜{lead}与{second}同一主题？",
                f"{lead}和{second}，{anchor}{n_label}条快讯",
            ]
        )
    if event:
        base.append(f"{event}：{lead}等{n_label}条快讯")
        if pair:
            base.append(f"{event}｜{lead}与{second}怎么看？")
    rotated = _rotate(base, day_seed=day_seed, count=7)
    legacy = [
        f"{lead}：A股快讯精选" if not pair else f"{lead}与{second}：A股快讯精选",
        f"收盘快讯｜{lead}" if not pair else f"收盘快讯｜{lead}与{second}",
        f"A股{n_label}条快讯｜{lead}等{anchor}人气+解读",
    ]
    return [rotated, legacy[:3]]


def build_generic_news_title_options(
    items: list[dict[str, Any]],
    *,
    now: datetime,
    n_label: str,
    hook: str,
    hook_alt: str,
    weekday_cn: str,
) -> list[list[str]]:
    event = _short_event_hook(items) or hook
    day_seed = now.toordinal() + now.weekday() * 17
    base = [
        f"A股｜今天这条{event}，有何影响？",
        f"{weekday_cn}快讯｜{hook}等{n_label}条拆开",
        f"{event}：{n_label}条A股快讯逐条拆",
        f"收盘{hook}这条，后面{n_label}条对照",
        f"{hook_alt or hook}牵动什么？{n_label}条快讯",
        f"今夜{n_label}条｜{hook}要闻怎么理解",
    ]
    rotated = _rotate(base, day_seed=day_seed, count=5)
    legacy = [
        f"A股{weekday_cn}{n_label}条快讯｜{hook}逐条拆",
        f"A股快讯精选{n_label}条：{hook}有何影响？",
    ]
    return [rotated, legacy]
