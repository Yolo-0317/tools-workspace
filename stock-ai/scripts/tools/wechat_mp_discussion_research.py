#!/usr/bin/env python3
"""话题讨论稿取材：同题公开报道检索 + 仿写指引（非东财财经泛搜）。"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from html import unescape
from typing import Any

from scripts.tools.wechat_mp_hotspot_research import (
    ResearchHit,
    _fetch_eastmoney_search,
    _strip_html,
    fetch_hotspot_research,
)

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_NEWS_DOMAINS = (
    "163.com",
    "sina.com.cn",
    "sina.cn",
    "china.com",
    "thepaper.cn",
    "qq.com",
    "sohu.com",
    "jinantimes.com.cn",
    "huanqiu.com",
    "ifeng.com",
    "setn.com",
    "bjnews.com.cn",
    "cctv.com",
    "cctv.cn",
    "news.cn",
    "xinhuanet.com",
    "people.com.cn",
    "cyol.com",
    "gmw.cn",
    "chinanews.com.cn",
    "rednet.cn",
    "stcn.com",
    "yicai.com",
    "jiemian.com",
    "caixin.com",
    "toutiao.com",
    "baijiahao.baidu.com",
    "weibo.com",
)
_SKIP_URL_HINTS = ("video", "login", "passport", "javascript:", "1x1.png", "default/1x1")
_NEWS_URL_CACHE = (
    __import__("pathlib").Path(__file__).resolve().parents[2] / "data" / "wechat_mp_discussion_news_cache.json"
)


def _norm_cache_key(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())[:48]


def _load_news_url_cache() -> dict[str, list[str]]:
    try:
        if _NEWS_URL_CACHE.is_file():
            data = json.loads(_NEWS_URL_CACHE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): [str(u) for u in v if str(u).startswith("http")] for k, v in data.items()}
    except Exception:
        pass
    return {}


def _save_news_url_cache(cache: dict[str, list[str]]) -> None:
    try:
        _NEWS_URL_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _NEWS_URL_CACHE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _cached_news_urls(query: str) -> list[str]:
    key = _norm_cache_key(query)
    if not key:
        return []
    cache = _load_news_url_cache()
    out: list[str] = []
    for k, urls in cache.items():
        if not k or not urls:
            continue
        if k in key or key in k:
            for u in urls:
                if u not in out:
                    out.append(u)
    return out


def _remember_news_urls(query: str, urls: list[str]) -> None:
    key = _norm_cache_key(query)
    if not key or not urls:
        return
    cache = _load_news_url_cache()
    merged = list(cache.get(key) or [])
    for u in urls:
        if u.startswith("http") and u not in merged:
            merged.append(u)
    cache[key] = merged[:12]
    _save_news_url_cache(cache)
_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.I)
_META_DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
    re.I,
)
_P_RE = re.compile(r"<p[^>]*>(.{40,500}?)</p>", re.I | re.S)


def discussion_research_enabled() -> bool:
    raw = (os.getenv("WECHAT_MP_DISCUSSION_RESEARCH") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _trend_blob(topic: dict[str, Any]) -> str:
    return " ".join(
        str(topic.get(k) or "")
        for k in ("trend_title", "title_zh", "hook")
    ).strip()


def _event_keywords(topic: dict[str, Any]) -> list[str]:
    blob = _trend_blob(topic)
    keys: list[str] = []
    for token in re.findall(r"[\u4e00-\u9fff]{2,8}", blob):
        if token not in keys:
            keys.append(token)
    # 长词条再拆
    trend = str(topic.get("trend_title") or "")
    for sep in ("，", ",", "、", " "):
        if sep in trend:
            for part in trend.split(sep):
                part = part.strip()
                if 2 <= len(part) <= 12 and part not in keys:
                    keys.append(part)
    return keys[:12]


def _hit_relevant(hit: ResearchHit, keywords: list[str]) -> bool:
    blob = f"{hit.title} {hit.snippet}"
    if not keywords:
        return True
    hits = sum(1 for k in keywords if k in blob)
    if hits >= 2:
        return True
    # 主词条至少命中一个长词
    trend = keywords[0] if keywords else ""
    if len(trend) >= 6 and trend in blob:
        return True
    core = (
        "出轨",
        "试管",
        "原配",
        "胚胎",
        "离婚",
        "伪造",
        "婚外",
        "删库",
        "删光",
        "程序员",
        "数据",
        "工程师",
        "私活",
        "获刑",
        "判刑",
        "算法",
        "代码",
    )
    trend_text = " ".join(keywords)
    if any(k in blob for k in core if k in trend_text):
        return True
    if re.search(r"\d+\s*TB", trend_text, flags=re.I) and re.search(
        r"删|数据|程序员|工程师|代码|私活", blob
    ):
        return True
    return False


def _fetch_html(url: str, *, timeout: float = 16.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Referer": url})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(220_000).decode("utf-8", errors="replace")


def _parse_article_page(url: str, html: str) -> ResearchHit | None:
    m = _TITLE_RE.search(html)
    title = _strip_html(m.group(1)) if m else ""
    title = re.sub(r"[_\-|].{0,30}(新浪|网易|搜狐|腾讯|中华网).*$", "", title).strip()
    desc_m = _META_DESC_RE.search(html)
    snippet = unescape(desc_m.group(1)).strip() if desc_m else ""
    if not snippet:
        for pm in _P_RE.finditer(html):
            text = _strip_html(pm.group(1))
            if len(text) >= 40 and "cookie" not in text.lower():
                snippet = text[:720]
                break
    if not title or len(snippet) < 20:
        return None
    host = urllib.parse.urlparse(url).netloc.replace("www.", "")
    return ResearchHit(
        title=title[:120],
        snippet=snippet[:720],
        source=host,
        url=url,
    )


def _enrich_hit_snippet_from_page(hit: ResearchHit) -> ResearchHit:
    """从报道正文补全摘要（meta 过短时 LLM 只能写两三句）。"""
    if len((hit.snippet or "").strip()) >= 420:
        return hit
    try:
        html = _fetch_html(hit.url)
        parts: list[str] = []
        for pm in _P_RE.finditer(html):
            text = _strip_html(pm.group(1))
            if len(text) >= 28 and "cookie" not in text.lower():
                parts.append(text)
        if not parts:
            return hit
        blob = "。".join(parts[:12])
        if len(blob) < len(hit.snippet or ""):
            return hit
        return ResearchHit(
            title=hit.title,
            snippet=blob[:1200],
            source=hit.source,
            url=hit.url,
            published=hit.published,
        )
    except Exception:
        return hit


def _collect_news_urls_from_html(html: str, *, limit: int = 10) -> list[str]:
    found: list[str] = []
    for dom in _NEWS_DOMAINS:
        for raw in re.findall(rf"https?://[^\"'\s<>]*{re.escape(dom)}[^\"'\s<>]*", html):
            u = raw.split("&")[0].rstrip(")")
            low = u.lower()
            if any(x in low for x in _SKIP_URL_HINTS):
                continue
            if "mp.weixin.qq.com" in low:
                continue
            if "qq.com" in low and "article" not in low and "news" not in low:
                continue
            if u not in found:
                found.append(u)
            if len(found) >= limit:
                return found
    return found[:limit]


def _fetch_so_news_urls(query: str, *, limit: int = 10) -> list[str]:
    q = urllib.parse.quote((query or "").strip())
    if not q:
        return []
    url = f"https://www.so.com/s?q={q}"
    try:
        html = _fetch_html(url)
    except Exception:
        return []
    return _collect_news_urls_from_html(html, limit=limit)


def _fetch_sogou_news_urls(query: str, *, limit: int = 10) -> list[str]:
    """360 新闻检索常为空时，用搜狗网页搜同题门户报道。"""
    q = urllib.parse.quote((query or "").strip())
    if not q:
        return []
    url = f"https://www.sogou.com/web?query={q}"
    try:
        html = _fetch_html(url)
    except Exception:
        return []
    return _collect_news_urls_from_html(html, limit=limit)


def _fetch_weibo_search_urls(query: str, *, limit: int = 10) -> list[str]:
    """微博搜索只负责发现可追溯原帖；后续仍需账号身份与页面限制校验。"""
    q = urllib.parse.quote((query or "").strip())
    if not q:
        return []
    url = f"https://s.weibo.com/weibo?q={q}"
    try:
        html = _fetch_html(url)
    except Exception:
        return []
    return _collect_news_urls_from_html(html, limit=limit)


def _fetch_baidu_news_urls(query: str, *, limit: int = 10) -> list[str]:
    """百度新闻检索：补 360/搜狗缺口，扩大同题报道页来源。"""
    q = urllib.parse.quote((query or "").strip())
    if not q:
        return []
    url = f"https://www.baidu.com/s?wd={q}&tn=news"
    try:
        html = _fetch_html(url)
    except Exception:
        return []
    return _collect_news_urls_from_html(html, limit=limit)


def _fetch_baidu_web_urls(query: str, *, limit: int = 10) -> list[str]:
    q = urllib.parse.quote((query or "").strip())
    if not q:
        return []
    url = f"https://www.baidu.com/s?wd={q}"
    try:
        html = _fetch_html(url)
    except Exception:
        return []
    return _collect_news_urls_from_html(html, limit=limit)


def _fetch_news_search_urls(query: str, *, limit: int = 10) -> list[str]:
    seen: list[str] = []
    for u in _cached_news_urls(query):
        if u not in seen:
            seen.append(u)
    for fetcher in (
        _fetch_weibo_search_urls,
        _fetch_baidu_news_urls,
        _fetch_sogou_news_urls,
        _fetch_so_news_urls,
        _fetch_baidu_web_urls,
    ):
        for u in fetcher(query, limit=limit):
            if u not in seen:
                seen.append(u)
            if len(seen) >= limit:
                break
        if len(seen) >= limit:
            break
    if len(seen) > len(_cached_news_urls(query)):
        _remember_news_urls(query, seen)
    return seen[:limit]


def figure_search_queries(topic: dict[str, Any]) -> list[str]:
    """配图/取材共用：从标题拆多条检索词，提高同题报道命中率。"""
    queries: list[str] = []
    trend = str(topic.get("trend_title") or "").strip()
    zh = str(topic.get("title_zh") or "").strip()
    for raw in (trend, zh):
        if raw and raw not in queries:
            queries.append(raw)
    event_date = str(topic.get("event_date") or "").strip()
    if trend:
        for variant in (
            f"{trend} 现场",
            f"{trend} {event_date}" if event_date else "",
            f"{trend} 图片",
        ):
            if variant and variant not in queries:
                queries.append(variant)
    for sep in ("，", ",", "：", ":", "、"):
        if sep in trend:
            head = trend.split(sep, 1)[0].strip()
            if len(head) >= 4 and head not in queries:
                queries.append(head)
    for token in re.findall(r"[\u4e00-\u9fff]{4,14}", trend):
        if token not in queries:
            queries.append(token)
    # 删库/数据类热搜：长标题常搜不到，补短检索词
    if any(k in trend for k in ("删", "数据", "TB", "tb", "泄露", "宕机")):
        for short in ("删光公司数据", "删库", "程序员删库", "删公司数据"):
            if short not in queries:
                queries.append(short)
    tb_m = re.search(r"(\d+)\s*TB", trend, flags=re.I)
    if tb_m:
        short = f"删光{tb_m.group(1)}TB"
        if short not in queries:
            queries.append(short)
    # 去掉英文数字后的中文核心（如「员工用代码…删光公司…」→ 更易命中门户标题）
    core = re.sub(r"[0-9A-Za-z]+", "", trend).strip()
    if len(core) >= 8 and core not in queries:
        queries.append(core[:24])
    return queries[:8]


def fetch_discussion_research(
    topic: dict[str, Any], *, limit: int = 5, include_finance: bool = False
) -> list[ResearchHit]:
    """同题社会/文娱报道：360/搜狗新闻检索 + 可选东财补充（严格相关过滤）。"""
    if not discussion_research_enabled():
        return []

    keywords = _event_keywords(topic)
    trend = str(topic.get("trend_title") or "").strip()
    seen: set[str] = set()
    merged: list[ResearchHit] = []

    extra_urls = topic.get("research_urls") or []
    if isinstance(extra_urls, str):
        extra_urls = [extra_urls]

    search_queries = figure_search_queries(topic)
    if trend and trend not in search_queries:
        search_queries = [trend, *search_queries]

    for query in search_queries[:8]:
        for page_url in _cached_news_urls(query):
            if page_url in seen:
                continue
            seen.add(page_url)
            try:
                html = _fetch_html(page_url)
                hit = _parse_article_page(page_url, html)
            except Exception:
                continue
            if hit and _hit_relevant(hit, keywords):
                merged.append(hit)

    for query in search_queries[:8]:
        for page_url in _fetch_news_search_urls(query, limit=limit + 4):
            key = page_url[:80]
            if key in seen:
                continue
            seen.add(key)
            try:
                html = _fetch_html(page_url)
                hit = _parse_article_page(page_url, html)
            except Exception:
                continue
            if not hit or not _hit_relevant(hit, keywords):
                continue
            merged.append(hit)
            if len(merged) >= limit + 2:
                break
        if len(merged) >= limit + 2:
            break

    if trend and include_finance:
        for hit in fetch_hotspot_research(trend[:20], limit=limit):
            key = re.sub(r"\s+", "", hit.title)[:24]
            if key in seen:
                continue
            if _hit_relevant(hit, keywords):
                seen.add(key)
                merged.append(hit)

    for page_url in extra_urls:
        u = str(page_url or "").strip()
        if not u.startswith("http") or u in seen:
            continue
        seen.add(u)
        try:
            html = _fetch_html(u)
            hit = _parse_article_page(u, html)
            if hit:
                merged.append(hit)
        except Exception:
            pass

    enriched = [_enrich_hit_snippet_from_page(h) for h in merged[:limit]]
    return enriched


def format_discussion_facts_block(hits: list[ResearchHit]) -> str:
    if not hits:
        return ""
    lines = [
        "【联网事实】成稿须写入下列可核对信息（可改写，禁止编造；勿写「据报道」「搜索到」）："
    ]
    for i, hit in enumerate(hits, 1):
        snip = hit.snippet[:360] + ("…" if len(hit.snippet) > 360 else "")
        lines.append(f"{i}. {hit.title}｜{hit.source}｜{snip}")
    return "\n".join(lines)


def format_discussion_imitation_block(hits: list[ResearchHit]) -> str:
    """社会话题仿写：学澎湃/新浪/网易同题稿节奏。"""
    if not hits:
        return ""
    lines = [
        "【参考文章·仿写】先读下面同题报道，学节奏再写（禁止整段照搬）：",
        "- 首段：直接写人物+地点+核心冲突（谁、在哪、发生了什么），不要「今天我们来聊」；",
        "- 中段：补 2～4 个可核对细节（时间、机构、律师观点、医院回应）；",
        "- 口吻：像转述给朋友，可稍啰嗦；禁「第一/二条线」「值得注意的是」「不难发现」；",
        "- 禁「一块…另一块」「分成两块」「只是一半/另一半」「难就难在」「二次发酵」等对称 AI 句式；",
        "- 末段：一句后续观察（官司进展、舆论还会吵什么），不要道德审判总结。",
        "",
    ]
    for i, hit in enumerate(hits[:3], 1):
        body = hit.snippet[:620] + ("…" if len(hit.snippet) > 620 else "")
        opener = body.split("。")[0].strip()
        if opener:
            opener += "。"
        lines.extend(
            [
                f"--- 参考{i}｜{hit.source}《{hit.title}》 ---",
                f"开头示范：{opener}",
                body,
                "",
            ]
        )
    return "\n".join(lines).strip()


def format_discussion_research_bundle(topic: dict[str, Any], hits: list[ResearchHit]) -> str:
    parts = [
        format_discussion_facts_block(hits),
        format_discussion_imitation_block(hits),
    ]
    return "\n\n".join(p for p in parts if p).strip()
