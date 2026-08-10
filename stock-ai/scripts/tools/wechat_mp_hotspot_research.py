#!/usr/bin/env python3
"""热点深评：东财搜索 + 本地快讯库 → 参考文章取材与标题路牌。"""

from __future__ import annotations

import json
import os
import re
from hashlib import sha256
from pathlib import Path
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from typing import Any

_EM_SEARCH_URL = "https://search-api-web.eastmoney.com/search/jsonp"
_HOTSPOT_TITLE_PREFIX = ""
_LEGACY_HOTSPOT_TITLE_PREFIXES = ("热点深评｜", "热点评论｜", "A股热点｜")
_WECHAT_TITLE_MAX = 32
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_TAG_RE = re.compile(r"<[^>]+>")
_BAD_TITLE_SUFFIXES = (
    "影响大吗？",
    "该关注啥？",
    "意味着啥？",
    "有关系吗？",
    "怎么看？",
    "和A股啥关系？",
    "对A股有什么影响？",
)
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "hotspot-research"
_CACHE_VERSION = 1


@dataclass(frozen=True)
class ResearchHit:
    title: str
    snippet: str
    source: str
    url: str
    published: str = ""


def hotspot_research_enabled() -> bool:
    raw = (os.getenv("WECHAT_MP_HOTSPOT_RESEARCH") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def hotspot_research_limit() -> int:
    try:
        return max(3, min(8, int(os.getenv("WECHAT_MP_HOTSPOT_RESEARCH_LIMIT") or "5")))
    except ValueError:
        return 5


def _strip_html(text: str) -> str:
    out = unescape(_TAG_RE.sub("", text or ""))
    return re.sub(r"\s+", " ", out).strip()


def _research_query(title: str) -> str:
    blob = _strip_html(title)
    blob = re.sub(r"[「」""''？?！!]", "", blob)
    if len(blob) <= 20:
        return blob
    for sep in ("，", "。", "；", "、", " "):
        if sep in blob:
            left = blob.split(sep, 1)[0].strip()
            if len(left) >= 4:
                return left[:18]
    return blob[:18]


def _fetch_eastmoney_search(keyword: str, *, limit: int = 8) -> list[ResearchHit]:
    param = json.dumps(
        {
            "uid": "",
            "keyword": keyword,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "1.0.0",
            "pageIndex": 1,
            "pageSize": limit,
        },
        ensure_ascii=False,
    )
    url = f"{_EM_SEARCH_URL}?uid=&cb=jQuery&param={urllib.request.quote(param)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _UA, "Referer": "https://so.eastmoney.com/"},
    )
    with urllib.request.urlopen(req, timeout=18.0) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    m = re.search(r"jQuery\((.*)\)\s*;?\s*$", raw, flags=re.DOTALL)
    if not m:
        return []
    data = json.loads(m.group(1))
    items = ((data.get("result") or {}).get("cmsArticleWebOld") or [])[:limit]
    out: list[ResearchHit] = []
    for item in items:
        title = _strip_html(str(item.get("title") or ""))
        snippet = _strip_html(str(item.get("content") or ""))
        if not title or len(snippet) < 20:
            continue
        out.append(
            ResearchHit(
                title=title,
                snippet=snippet[:720],
                source=str(item.get("mediaName") or "东财"),
                url=str(item.get("url") or "").strip(),
                published=str(item.get("date") or "").strip(),
            )
        )
    return out


def _fetch_local_news(keyword: str, *, limit: int = 4) -> list[ResearchHit]:
    try:
        from scripts.tools.news_db import _load_keyword_news_items

        keys = {k for k in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", keyword) if len(k) >= 2}

        def pred(item: dict[str, Any]) -> bool:
            blob = f"{item.get('title') or ''}{item.get('summary') or ''}"
            return any(k in blob for k in keys)

        rows = _load_keyword_news_items(hours=72, limit=limit * 3, predicate=pred)
    except Exception:
        return []
    out: list[ResearchHit] = []
    for row in rows[:limit]:
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        out.append(
            ResearchHit(
                title=title,
                snippet=str(row.get("summary") or "")[:720],
                source=str(row.get("source") or "macro_news"),
                url=str(row.get("href") or "").strip(),
                published=str(row.get("news_time") or row.get("published_at") or ""),
            )
        )
    return out


def fetch_hotspot_research(title: str, *, limit: int | None = None) -> list[ResearchHit]:
    """按热搜标题检索相关报道，供成稿引用与仿写。"""
    if not hotspot_research_enabled():
        return []
    n = limit if limit is not None else hotspot_research_limit()
    query = _research_query(title)
    if not query:
        return []
    cached = _load_cached_research(query)
    if cached is not None:
        return cached[:n]
    seen: set[str] = set()
    merged: list[ResearchHit] = []
    for hit in _fetch_eastmoney_search(query, limit=n + 2):
        key = re.sub(r"\s+", "", hit.title)[:24]
        if key in seen:
            continue
        seen.add(key)
        merged.append(hit)
    if len(merged) < 3:
        for hit in _fetch_local_news(query, limit=n):
            key = re.sub(r"\s+", "", hit.title)[:24]
            if key in seen:
                continue
            seen.add(key)
            merged.append(hit)
    result = merged[:n]
    _save_cached_research(query, result)
    return result


def _cache_path(query: str) -> Path:
    digest = sha256(query.encode("utf-8")).hexdigest()[:16]
    cache_day = datetime.now().astimezone().date().isoformat()
    return _CACHE_DIR / cache_day / f"{digest}.json"


def _load_cached_research(query: str) -> list[ResearchHit] | None:
    path = _cache_path(query)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != _CACHE_VERSION or payload.get("query") != query:
            return None
        rows = payload.get("hits")
        if not isinstance(rows, list):
            return None
        return [ResearchHit(**row) for row in rows if isinstance(row, dict)]
    except (OSError, ValueError, TypeError):
        return None


def _save_cached_research(query: str, hits: list[ResearchHit]) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _CACHE_VERSION,
            "query": query,
            "hits": [hit.__dict__ for hit in hits],
        }
        _cache_path(query).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def format_hotspot_research_block(hits: list[ResearchHit]) -> str:
    if not hits:
        return ""
    lines = [
        "【联网事实】成稿须写入下列可核对信息（可改写，禁止编造；勿写「参考/搜索」字样）："
    ]
    for i, hit in enumerate(hits[:3], 1):
        when = f"（{hit.published}）" if hit.published else ""
        snip = hit.snippet[:180] + ("…" if len(hit.snippet) > 180 else "")
        lines.append(f"{i}. {hit.title}{when}｜{hit.source}｜{snip}")
    return "\n".join(lines)


def format_hotspot_reference_imitation_block(hits: list[ResearchHit]) -> str:
    """把参考报道整理成「仿写」区块：学结构密度，不照搬。"""
    if not hits:
        return ""
    lines = [
        "【参考文章·仿写】先读下面同题财经稿，学它们的节奏再写：",
        "- 首段：直接报事实+数字（哪家涨跌幅、多少家上涨），不要结构预告；",
        "- 中段：点名 3～6 家公司/板块，用具体涨跌幅或「创历史新高」等可核对表述；",
        "- 末段：一句可验证的次日观察（竞价/龙头/量能），不要套话总结。",
        "可把多家信息熔成一篇，禁止整段照搬，禁止研报腔。",
        "",
    ]
    for i, hit in enumerate(hits[:2], 1):
        when = f"（{hit.published}）" if hit.published else ""
        body = hit.snippet[:260] + ("…" if len(hit.snippet) > 260 else "")
        opener = body.split("。")[0].strip()
        if opener:
            opener = opener + "。"
        lines.extend(
            [
                f"--- 参考{i}｜{hit.source}《{hit.title}》{when} ---",
                f"开头示范（学这种直接上口的写法，不要加「据报道」）：{opener}",
                body,
                "",
            ]
        )
    return "\n".join(lines).strip()


def _research_blob(hits: list[ResearchHit]) -> str:
    parts = [format_hotspot_research_block(hits), format_hotspot_reference_imitation_block(hits)]
    return "\n\n".join(p for p in parts if p).strip()


def _title_core_from_trend(trend: str) -> str:
    core = re.sub(r"\s+", "", _strip_html(trend))
    if core.startswith("A股"):
        core = core[2:].lstrip("，、：: ")
    return core


def _bad_title(title: str) -> bool:
    if not title or len(title) > _WECHAT_TITLE_MAX:
        return True
    if "…" in title or "..." in title:
        return True
    if any(title.endswith(s) for s in _BAD_TITLE_SUFFIXES):
        return True
    # 「A股市值前十，和A股…」类逻辑重复
    if title.count("A股") >= 2:
        return True
    if re.search(r"A股.+，和A股", title):
        return True
    return False


def build_hotspot_title_from_facts(
    hits: list[ResearchHit],
    *,
    trend: str,
) -> str:
    """用参考报道里的具体事实拼标题（不套模板后缀）。"""
    blob = " ".join(f"{h.title} {h.snippet}" for h in hits)
    blob = re.sub(r"\s+", "", blob)
    core = _title_core_from_trend(trend)

    banks: list[str] = []
    if "建设银行" in blob or "建行" in blob:
        banks.append("建行")
    if "工商银行" in blob or "工行" in blob:
        banks.append("工行")
    if "农业银行" in blob or "农行" in blob:
        banks.append("农行")
    bank_hint = ""
    if banks:
        bank_hint = f"，{'、'.join(banks[:2])}创新高"

    if "市值" in core and re.search(r"红[了]?\d|红了9|多数收涨|全涨", blob + core):
        n = re.search(r"红[了]?(\d+)", core + blob)
        if n:
            title = f"{_HOTSPOT_TITLE_PREFIX}市值前十红了{n.group(1)}家{bank_hint}？"
        else:
            title = f"{_HOTSPOT_TITLE_PREFIX}市值前十多数收涨{bank_hint}？"
        return title[:_WECHAT_TITLE_MAX]

    if hits:
        hit = hits[0]
        hook = re.sub(r"^(快讯|独家|重磅)[:：]?", "", _strip_html(hit.title))
        hook = hook.split("，")[0].split("。")[0].strip()
        if hook.startswith("A股"):
            hook = hook[2:].lstrip("，、 ")
        if 6 <= len(hook) <= 18:
            return f"{_HOTSPOT_TITLE_PREFIX}{hook}？"[:_WECHAT_TITLE_MAX]

    if core:
        if not core.endswith("？") and not core.endswith("?"):
            core = core[:16] + "？"
        return f"{_HOTSPOT_TITLE_PREFIX}{core}"[:_WECHAT_TITLE_MAX]
    return f"{_HOTSPOT_TITLE_PREFIX}当日热点解读？".lstrip("｜") or "当日热点解读？"


def sanitize_hotspot_title(title: str) -> str:
    t = (title or "").strip()
    for p in _LEGACY_HOTSPOT_TITLE_PREFIXES:
        if t.startswith(p):
            t = t[len(p) :].lstrip("｜|")
    return t[:_WECHAT_TITLE_MAX]


def title_is_acceptable(title: str) -> bool:
    return not _bad_title(title)
