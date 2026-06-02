#!/usr/bin/env python3
"""公众号宏观稿：盘面行情 + 扩充快讯 + 研究员体例（不依赖 briefing 最后一版 AI）。"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.deepseek_client import call_deepseek, is_llm_configured
from scripts.tools.wechat_mp_public import PUBLIC_MP_WRITER_RULE
from scripts.tools.fetch_eastmoney_macro_news import MacroNewsItem
from scripts.tools.market_session import detect_market_session
from scripts.tools.news_db import GEOPOLITICS_KEYWORDS, classify_category, list_news_items
from scripts.tools.news_sentiment import sentiment_label

TZ = ZoneInfo("Asia/Shanghai")
WEEKDAY_CN = "一二三四五六日"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _pick_geopolitics(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    for it in items:
        blob = f"{it.get('title', '')} {it.get('summary', '')}"
        if any(kw in blob for kw in GEOPOLITICS_KEYWORDS):
            picked.append(it)
        if len(picked) >= limit:
            break
    return picked


def _load_news_pool(*, hours: int, limit: int) -> list[dict[str, Any]]:
    from scripts.tools.news_db import load_recent_news

    today = datetime.now(TZ).date()
    rows = list_news_items(day=today, limit=limit)
    if len(rows) < limit // 2:
        seen = {r.get("href") for r in rows}
        for item in load_recent_news(hours=hours, limit=limit):
            href = getattr(item, "href", "")
            if href in seen:
                continue
            rows.append(
                {
                    "href": href,
                    "title": item.title,
                    "summary": item.summary or "",
                    "news_time": item.time or "",
                    "category": classify_category(item.title, item.summary),
                    "sentiment": "neutral",
                }
            )
            seen.add(href)
    return rows[:limit]


def _fetch_market_block(session) -> list[str]:
    from scripts.tools.daily_briefing_report import (
        fetch_international_markets,
        fetch_market_indices,
    )

    lines = [session.header_note(), ""]
    lines.extend(fetch_market_indices())
    lines.append("")
    lines.append("国际市场简况：")
    intl = fetch_international_markets()
    lines.extend(intl[:6] if len(intl) > 6 else intl)
    return lines


def _format_news_lines(items: list[dict[str, Any]], *, limit: int) -> list[str]:
    show_time = _env_bool("WECHAT_MP_NEWS_SHOW_TIME", False)
    out: list[str] = []
    for it in items[:limit]:
        tag = sentiment_label(str(it.get("sentiment") or "neutral"))
        t = (it.get("news_time") or "").strip()
        title = (it.get("title") or "").strip()
        summary = (it.get("summary") or "").strip()
        if show_time and t:
            head = f"{t} [{tag}] {title}"
        else:
            head = f"[{tag}] {title}"
        out.append(head)
        if summary and summary != title:
            brief = summary if len(summary) <= 96 else summary[:96] + "…"
            out.append(f"  {brief}")
    return out or ["（暂无相关快讯）"]


def build_market_context_blob(*, now: datetime | None = None) -> tuple[str, str]:
    """
    组装给 LLM / 模板的原始素材。
    返回 (full_blob, news_blob_for_title)。
    """
    now = now or datetime.now(TZ)
    session = detect_market_session(now=now)
    news_limit = _env_int("WECHAT_MP_MARKET_NEWS_LIMIT", 40)
    hours = _env_int("WECHAT_MP_MARKET_NEWS_HOURS", 36)
    geo_limit = _env_int("WECHAT_MP_MARKET_GEO_LIMIT", 8)
    dom_limit = _env_int("WECHAT_MP_MARKET_DOMESTIC_LIMIT", 14)

    pool = _load_news_pool(hours=hours, limit=news_limit)
    geo = _pick_geopolitics(pool, geo_limit)
    geo_hrefs = {x.get("href") for x in geo}
    domestic = [x for x in pool if x.get("href") not in geo_hrefs][:dom_limit]

    parts = [
        f"写作时间：{now.strftime('%Y-%m-%d %H:%M')}（{session.ai_session_hint(now.strftime('%H:%M'))}）",
        "",
        "【A股盘面数据】",
        *_fetch_market_block(session),
        "",
        f"【地缘要闻 {len(geo)} 条】",
        *_format_news_lines(geo, limit=geo_limit),
        "",
        f"【国内财经 {len(domestic)} 条】",
        *_format_news_lines(domestic, limit=dom_limit),
    ]
    blob = "\n".join(parts)
    news_blob = "\n".join(_format_news_lines(geo + domestic, limit=12))
    return blob, news_blob


def _template_market_body(*, now: datetime, session) -> str:
    """无 LLM 时的研究员体例模板。"""
    blob, _ = build_market_context_blob(now=now)
    lines = [
        "一、盘面一览",
    ]
    for block_line in blob.splitlines():
        if block_line.startswith(("上证指数", "深证成指", "创业板指", "沪深300", "科创50", "全A涨跌")):
            lines.append(block_line)
    lines.extend(["", "二、外围与资金", "（详见国际市场简况，数据见上）", "", "三、要闻精选"])
    in_news = False
    for block_line in blob.splitlines():
        if block_line.startswith("【地缘") or block_line.startswith("【国内"):
            in_news = True
            lines.append("")
            lines.append(block_line.replace("【", "").replace("】", ""))
            continue
        if in_news and block_line.strip() and not block_line.startswith("【"):
            lines.append(block_line)
    lines.extend(
        [
            "",
            "四、观点与推演",
            "我们认为，盘面与要闻需放在同一框架下理解：指数涨跌反映风险偏好，",
            "地缘与政策变量则决定结构性强弱。短期宜先确认量能与涨跌家数是否共振，",
            "再讨论行业机会；以上仅为市场观察，不构成投资建议。",
        ]
    )
    return "\n".join(lines)


def generate_researcher_market_body(*, now: datetime | None = None) -> str:
    """资深研究员口吻正文（盘面 + 扩充快讯 + 四段式）。"""
    now = now or datetime.now(TZ)
    session = detect_market_session(now=now)
    context, _ = build_market_context_blob(now=now)

    if not is_llm_configured():
        return _template_market_body(now=now, session=session)

    prompt = f"""你是一位从业15年的A股宏观策略研究员，为公众号撰写「盘后札记」。
{PUBLIC_MP_WRITER_RULE}

{context}

## 写作要求
1. 全文四节，直接从「一、盘面一览」起笔，不要写「研究员札记 |」等抬头行
   一、盘面一览
   二、外围与资金
   三、要闻精选
   四、观点与推演
2. 「一、盘面一览」必须逐条写出上下文中的主要指数、涨跌幅与全A涨跌家数（有则写，无则说明获取失败）
3. 「三、要闻精选」分「地缘」与「国内」两段，合计至少12条，每条格式：[利好/利空/中性] 标题（不要写具体钟点，札记开头已有日期）；下一行可有一句摘要
4. 「四、观点与推演」250-400字：先给1-2句总判断，再拆2-3条逻辑链；可用「我们认为」「值得关注的是」「向后看」；避免喊单与具体价位
5. 禁止 emoji、禁止【AI综合解读】、禁止 markdown 加粗与表格
6. 只使用上下文出现的事实，勿编造数据"""

    try:
        content = call_deepseek(
            [
                {
                    "role": "system",
                    "content": (
                        "你是资深A股宏观研究员，文风冷静、有框架感，"
                        "像给不特定读者的公开盘后简报，而不是聊天机器人或作者日记。"
                        "禁止涉及作者个人持仓与账户。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=2200,
        )
        return content.strip()
    except Exception as exc:  # noqa: BLE001
        body = _template_market_body(now=now, session=session)
        return f"{body}\n\n（研究员点评生成失败：{exc}，以上为模板正文）"
