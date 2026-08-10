#!/usr/bin/env python3
"""news 头条开篇：群友好、按日轮换、结论先行（合规）。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from scripts.tools.wechat_mp_weekend_news import NewsTimeContext, build_news_time_context


def _lead_names(items: list[dict[str, Any]], n: int = 2) -> tuple[str, str]:
    names = [
        str(it.get("matched_stock_name") or "").strip()
        for it in items[: max(n, 4)]
        if str(it.get("matched_stock_name") or "").strip()
    ]
    lead = names[0] if names else "人气前排"
    second = names[1] if len(names) > 1 else lead
    return lead, second


def _event_snip(items: list[dict[str, Any]], *, max_len: int = 14) -> str:
    for it in items[:4]:
        raw = str(it.get("title") or it.get("matched_news_title") or "").strip()
        if not raw:
            continue
        raw = re.sub(r"\[[^\]]+\]", "", raw)
        raw = re.sub(r"\s+", "", raw)
        for cut in ("，", "。", "；", "：", "|"):
            if cut in raw:
                raw = raw.split(cut, 1)[0]
        if len(raw) >= 4:
            return raw[:max_len]
    return "盘面消息"


def _theme_clause() -> str:
    try:
        from scripts.tools.portfolio_db import load_emotion_cycle_checklist

        bundle = load_emotion_cycle_checklist(checklist_slot="eod") or load_emotion_cycle_checklist()
    except Exception:
        bundle = None
    if not bundle:
        return ""
    hdr = bundle.get("header") or {}
    theme = str(hdr.get("main_theme") or "").strip()
    phase = str(hdr.get("phase") or "").strip()
    parts: list[str] = []
    if phase:
        parts.append(f"情绪{phase}")
    if theme:
        parts.append(f"主线在{theme}")
    return "，".join(parts)


def _rotate_pick(options: list[str], *, now: datetime) -> str:
    if not options:
        return ""
    seed = now.toordinal() + now.weekday() * 19
    return options[seed % len(options)]


def build_hot_stock_news_intro(
    items: list[dict[str, Any]],
    *,
    now: datetime,
    hours: int,
    ctx: NewsTimeContext | None = None,
) -> str:
    """evening 热股 news 彩色开篇段（markdown  plain，HTML 层再上色）。"""
    ctx = ctx or build_news_time_context(now=now)
    lead, second = _lead_names(items)
    n = len(items) or 10
    event = _event_snip(items)
    theme = _theme_clause()
    verify = ctx.verify_title_suffix
    anchor = str((items[0] or {}).get("hot_stock_anchor_label") or ctx.anchor_label)

    theme_bit = f"{theme}；" if theme else ""
    templates = [
        (
            f"今天人气线落在{lead}——{event}。"
            f"{theme_bit}下面{n}条只写「发生了什么→{verify}」，你先扫第1条摘要。"
        ),
        (
            f"如果今天只追一条故事，我会先看{lead}；"
            f"{theme_bit}{hours}小时内{n}条快讯逐条对照，先读摘要再点进点评。"
        ),
        (
            f"{lead}和{second}同一天上人气榜，不是巧合——{event}。"
            f"往下{n}条，每条配验证动作（观察稿，非荐股）。"
        ),
        (
            f"收盘人气落在{lead}这一侧（{anchor}）；{theme_bit}"
            f"第1条摘要决定你要不要往下翻。"
        ),
        (
            f"常有人问「今天哪个票有消息」——{lead}这条优先。"
            f"{n}条里先看摘要，再决定要不要读 AI 点评。"
        ),
        (
            f"先把结论放前面：{lead}是今天{n}条里的第一条锚。"
            f"{event}；验证点看{verify}，先扫第1条摘要。"
        ),
        (
            f"只看一条线的话，从{lead}开始；{second}放对照。"
            f"{theme_bit}下面{n}条，摘要在前、先扫第1条再读点评。"
        ),
    ]
    return _rotate_pick(templates, now=now)


def build_weekend_hot_news_intro(
    items: list[dict[str, Any]],
    *,
    now: datetime,
    hours: int,
    ctx: NewsTimeContext | None = None,
) -> str:
    ctx = ctx or build_news_time_context(now=now)
    lead, second = _lead_names(items)
    n = len(items) or 10
    event = _event_snip(items)
    verify = ctx.verify_title_suffix
    anchor = str((items[0] or {}).get("hot_stock_anchor_label") or ctx.anchor_label)

    templates = [
        (
            f"周末榜单不刷新，锚还是{anchor}的{lead}。"
            f"{event}；{n}条周末消息，先扫摘要再看{verify}。"
        ),
        (
            f"休市别硬追消息——{lead}和{second}仍是人气参照。"
            f"下面{n}条各配一条解读，先读第1条摘要。"
        ),
        (
            f"如果周末只刷一遍，从{lead}这条开始。"
            f"{hours}小时内{n}条精选，验证动作写到{verify}。"
        ),
    ]
    return _rotate_pick(templates, now=now)


def build_generic_news_intro(
    items: list[dict[str, Any]],
    *,
    now: datetime,
    hours: int,
) -> str:
    n = len(items) or 10
    event = _event_snip(items)
    templates = [
        (
            f"近{hours}小时{n}条快讯，先看这条：{event}。"
            f"摘要在前，AI 点评在后；先扫第1条再决定要不要往下翻。"
        ),
        (
            f"如果今天只读一遍要闻，从「{event}」这条起。"
            f"下面{n}条逐条拆，验证点写在每条点评里。"
        ),
    ]
    return _rotate_pick(templates, now=now)


def first_sentence(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    for sep in ("。", "！", "？", "\n"):
        if sep in s:
            return s.split(sep, 1)[0] + (sep if sep != "\n" else "。")
    return s[:48] + ("…" if len(s) > 48 else "")


def extract_news_intro_from_body(body: str) -> str:
    """从成稿正文提取「要闻精选」下第一段开篇。"""
    lines = (body or "").splitlines()
    seen_section = False
    for line in lines:
        s = line.strip()
        if s.startswith("> 要闻精选"):
            seen_section = True
            continue
        if not seen_section:
            continue
        if not s or s.startswith(">") or s.startswith("[[fig:"):
            continue
        if re.match(r"^\d+\.", s):
            break
        return s
    return ""


def format_group_share_copy(*, title: str, intro: str) -> str:
    """控群/私聊转发：一句钩子 + 标题（用户复制即可）。"""
    hook = first_sentence(intro)
    title = (title or "").strip()
    if not hook:
        return title
    if title and title not in hook:
        return f"{hook}\n👉 {title}"
    return hook
