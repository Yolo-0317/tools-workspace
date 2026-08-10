#!/usr/bin/env python3
"""东财 np-listapi / 新浪 roll 等 HTTP 补源：弥补 OpenCLI 7×24 漏抓的政策稳市要闻。"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.fetch_eastmoney_macro_news import MacroNewsItem, _normalize_items

TZ = ZoneInfo("Asia/Shanghai")

_EM_NP_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("350", "web_724", "np_724"),
    ("802", "web_news_col", "np_news_col"),
)

_SINA_ROLL_LIDS: tuple[tuple[int, str], ...] = (
    (2516, "sina_finance"),
    (2509, "sina_stock"),
)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.eastmoney.com/",
}


def _normalize_href(href: str) -> str:
    href = (href or "").strip()
    if href.startswith("//"):
        return f"https:{href}"
    return href


def _news_time_from_show_time(show_time: str) -> str:
    raw = (show_time or "").strip()
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(raw, fmt).replace(tzinfo=TZ)
            return dt.strftime("%H:%M")
        except ValueError:
            continue
    m = re.search(r"(\d{2}:\d{2})", raw)
    return m.group(1) if m else raw


def fetch_eastmoney_np_column_news(
    *,
    column: str,
    biz: str,
    source: str,
    page_size: int = 50,
) -> list[dict[str, Any]]:
    """东财 np-listapi（HTTP，无需 OpenCLI）。"""
    trace = uuid.uuid4().hex[:16]
    params = {
        "client": "web",
        "biz": biz,
        "column": column,
        "pageSize": str(page_size),
        "pageIndex": "1",
        "fields": "title,url,showTime,digest,summary",
        "req_trace": trace,
    }
    resp = requests.get(
        "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns",
        params=params,
        headers=_DEFAULT_HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    if int(payload.get("code") or 0) != 1:
        msg = str(payload.get("message") or payload.get("msg") or "np-listapi error")
        raise RuntimeError(msg)
    rows = (payload.get("data") or {}).get("list") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        href = _normalize_href(str(row.get("url") or row.get("art_url") or ""))
        title = str(row.get("title") or "").strip()
        if not href or not title:
            continue
        summary = str(row.get("digest") or row.get("summary") or "").strip()
        out.append(
            {
                "title": title,
                "text": title if not summary else f"{title} {summary}",
                "summary": summary,
                "href": href,
                "time": _news_time_from_show_time(str(row.get("showTime") or "")),
                "source": source,
            }
        )
    return out


def fetch_sina_roll_news(*, num: int = 50) -> list[dict[str, Any]]:
    """新浪财经 roll JSON（HTTP）。"""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for lid, source in _SINA_ROLL_LIDS:
        resp = requests.get(
            "https://feed.mix.sina.com.cn/api/roll/get",
            params={"pageid": 153, "lid": lid, "k": "", "num": num, "page": 1},
            headers={"User-Agent": _DEFAULT_HEADERS["User-Agent"]},
            timeout=20,
        )
        resp.raise_for_status()
        rows = (resp.json().get("result") or {}).get("data") or []
        for row in rows:
            href = _normalize_href(str(row.get("url") or ""))
            title = str(row.get("title") or "").strip()
            if not href or not title or href in seen:
                continue
            seen.add(href)
            ctime = row.get("ctime")
            time_str = ""
            if ctime:
                try:
                    time_str = datetime.fromtimestamp(int(ctime), TZ).strftime("%H:%M")
                except (TypeError, ValueError, OSError):
                    time_str = ""
            out.append(
                {
                    "title": title,
                    "text": title,
                    "summary": "",
                    "href": href,
                    "time": time_str,
                    "source": source,
                }
            )
    return out


def merge_macro_news_items(
    primary: list[MacroNewsItem],
    *extra: list[MacroNewsItem],
) -> list[MacroNewsItem]:
    """按 href 去重；摘要取更长者；补源条目排在前面（同 href 时保留 primary 顺序）。"""
    merged: dict[str, MacroNewsItem] = {}
    order: list[str] = []
    for batch in (primary, *extra):
        for item in batch:
            href = _normalize_href(item.href)
            if not href:
                continue
            prev = merged.get(href)
            if prev is None:
                merged[href] = item
                order.append(href)
                continue
            if len(item.summary or "") > len(prev.summary or ""):
                merged[href] = MacroNewsItem(
                    title=item.title or prev.title,
                    summary=item.summary or prev.summary,
                    time=item.time or prev.time,
                    href=href,
                    source=item.source or prev.source,
                )
    return [merged[h] for h in order]


def fetch_supplemental_macro_news(*, limit: int = 30) -> list[MacroNewsItem]:
    """HTTP 多源补抓；失败单源跳过，不阻断主同步。"""
    raw: list[dict[str, Any]] = []
    for column, biz, source in _EM_NP_COLUMNS:
        try:
            raw.extend(
                fetch_eastmoney_np_column_news(
                    column=column,
                    biz=biz,
                    source=source,
                    page_size=max(limit, 30),
                )
            )
        except Exception:
            continue
    try:
        raw.extend(fetch_sina_roll_news(num=max(limit, 40)))
    except Exception:
        pass

    items = _normalize_items(raw, default_source="supplement")
    if len(items) <= limit:
        return items
    return items[:limit]
