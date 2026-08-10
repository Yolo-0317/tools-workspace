#!/usr/bin/env python3
"""微博 + 百度热搜 → hotspot 选题池（公开页面接口，非微信搜一搜）。"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")

WEIBO_HOT_URL = "https://weibo.com/ajax/side/hotSearch"
BAIDU_BOARD_URL = "https://top.baidu.com/api/board?platform=wise&tab=realtime"

UA_PC = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# 热点评论主轴：社会/文娱/职场可写题加分；财经与纯八卦降权
_DISCUSSION_TREND_BOOST: tuple[str, ...] = (
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

_FINANCE_TREND_DOWNRANK: tuple[str, ...] = (
    "A股",
    "沪指",
    "创业板",
    "科创",
    "涨停",
    "跌停",
    "芯片",
    "半导体",
    "存储",
    "股市",
    "券商",
    "央行",
    "GDP",
    "公积金",
    "降准",
    "降息",
)

_GOSSIP_TREND_DOWNRANK: tuple[str, ...] = (
    "路透",
    "造型",
    "耳环",
    "穿搭",
    "哭穷",
    "私服",
    "粉丝",
    "恋情",
    "剧宣",
    "官宣",
    "MV",
)

# 东财人气榜映射仍用产业关键词
_AGU_BOOST_KEYWORDS: tuple[str, ...] = (
    "A股",
    "沪指",
    "创业板",
    "科创",
    "芯片",
    "半导体",
    "存储",
    "科技",
    "股市",
    "涨停",
    "跌停",
    "券商",
    "央行",
    "降准",
    "降息",
    "油价",
    "原油",
    "黄金",
    "汇率",
    "美联储",
    "关税",
    "新规",
    "政策",
    "新能源",
    "光伏",
    "锂电",
    "汽车",
    "小米",
    "华为",
    "英伟达",
)


@dataclass(frozen=True)
class TrendRow:
    title: str
    source: str
    rank: int
    tag: str = ""
    url: str = ""


def _fetch_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 20.0) -> Any:
    req = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": UA_PC, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def fetch_weibo_hot(*, limit: int = 30) -> list[TrendRow]:
    data = _fetch_json(
        WEIBO_HOT_URL,
        headers={"User-Agent": UA_PC, "Accept": "application/json", "Referer": "https://weibo.com/"},
    )
    rows: list[TrendRow] = []
    realtime = (data.get("data") or {}).get("realtime") or []
    for i, item in enumerate(realtime[:limit], 1):
        title = str(item.get("word") or item.get("note") or "").strip()
        if not title:
            continue
        rows.append(
            TrendRow(
                title=title,
                source="weibo",
                rank=i,
                tag=str(item.get("icon_desc") or item.get("flag_desc") or "").strip(),
                url=str(item.get("url") or item.get("scheme") or "").strip(),
            )
        )
    return rows


def fetch_baidu_hot(*, limit: int = 30) -> list[TrendRow]:
    data = _fetch_json(BAIDU_BOARD_URL)
    rows: list[TrendRow] = []
    tag_map = {"1": "新", "2": "商", "3": "热", "4": "沸", "5": "爆"}
    for card in (data.get("data") or {}).get("cards") or []:
        for block in card.get("content") or []:
            for item in block.get("content") or []:
                title = str(item.get("word") or "").strip()
                if not title:
                    continue
                rank = int(item.get("index") or len(rows) + 1)
                hot_tag = str(item.get("hotTag") or "")
                rows.append(
                    TrendRow(
                        title=title,
                        source="baidu",
                        rank=rank,
                        tag=tag_map.get(hot_tag, hot_tag),
                        url=str(item.get("url") or "").strip(),
                    )
                )
                if len(rows) >= limit:
                    return rows
    return rows


def _norm_key(text: str) -> str:
    s = re.sub(r"\s+", "", (text or "").strip())
    s = re.sub(r"[「」""''？?！!，,。；;：:]", "", s)
    return s[:24]


def _titles_overlap(a: str, b: str) -> bool:
    ka, kb = _norm_key(a), _norm_key(b)
    if not ka or not kb:
        return False
    if ka in kb or kb in ka:
        return True
    # 共享连续 4 字以上视为同题
    shorter, longer = (ka, kb) if len(ka) <= len(kb) else (kb, ka)
    for n in range(min(8, len(shorter)), 3, -1):
        for i in range(0, len(shorter) - n + 1):
            if shorter[i : i + n] in longer:
                return True
    return False


def _score_title(title: str, *, ranks: list[int], sources: set[str]) -> float:
    score = 0.0
    for rank in ranks:
        score += max(0.0, 1200.0 - rank * 25.0)
    if len(sources) >= 2:
        score += 600.0
    boost_hits = sum(1 for kw in _DISCUSSION_TREND_BOOST if kw in title)
    if boost_hits:
        score += min(boost_hits, 3) * 320.0
    if any(kw in title for kw in _FINANCE_TREND_DOWNRANK):
        score -= 1400.0
    if any(kw in title for kw in _GOSSIP_TREND_DOWNRANK):
        score -= 650.0
    # 过长标题略降（不适合做路牌）
    if len(title) > 22:
        score -= 80.0
    return score


def merge_and_rank_trends(
    weibo: list[TrendRow],
    baidu: list[TrendRow],
    *,
    limit: int = 15,
) -> list[dict[str, Any]]:
    """合并双榜，按热度 + 社会/文娱可写度排序，输出 hotspot 兼容 item dict。"""
    buckets: dict[str, dict[str, Any]] = {}

    def ingest(row: TrendRow) -> None:
        key = _norm_key(row.title)
        if not key:
            return
        entry = buckets.get(key)
        if entry is None:
            entry = {
                "title": row.title,
                "summary": f"微博/百度热搜：{row.title}",
                "href": row.url or f"trend://{row.source}",
                "source": row.source,
                "sources": [row.source],
                "ranks": {row.source: row.rank},
                "tags": [row.tag] if row.tag else [],
                "attention_score": 0.0,
                "prefer_stock": False,
                "sentiment": "neutral",
            }
            buckets[key] = entry
        else:
            if row.source not in entry["sources"]:
                entry["sources"].append(row.source)
            entry["ranks"][row.source] = row.rank
            if row.tag and row.tag not in entry["tags"]:
                entry["tags"].append(row.tag)

    for row in weibo:
        ingest(row)
    for row in baidu:
        # 尝试并入已有同题（模糊）
        merged = False
        for entry in buckets.values():
            if _titles_overlap(row.title, str(entry.get("title") or "")):
                fake = TrendRow(title=entry["title"], source=row.source, rank=row.rank, tag=row.tag, url=row.url)
                ingest(fake)
                merged = True
                break
        if not merged:
            ingest(row)

    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in buckets.values():
        title = str(entry["title"] or "")
        ranks = [int(v) for v in (entry.get("ranks") or {}).values()]
        sources = set(entry.get("sources") or [])
        score = _score_title(title, ranks=ranks, sources=sources)
        entry["attention_score"] = score
        entry["prefer_stock"] = any(kw in title for kw in _FINANCE_TREND_DOWNRANK)
        if len(sources) >= 2:
            entry["summary"] = f"微博与百度同日热议：{title}"
        scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    out = [item for _, item in scored[:limit]]
    return out


def _title_keywords(title: str) -> set[str]:
    """从热搜标题抽可匹配板块/热股的关键词。"""
    blob = re.sub(r"\s+", "", (title or "").strip())
    keys: set[str] = set()
    for kw in _AGU_BOOST_KEYWORDS:
        if kw in blob:
            keys.add(kw)
    for rules in (
        ("半导体", "芯片", "存储", "算力", "光模块", "封测", "HBM"),
        ("原油", "油价", "油服", "黄金", "券商", "军工", "医药", "光伏", "锂电"),
        ("涨停", "跌停", "连板", "龙头", "市值", "沪指", "创业板", "科创"),
    ):
        for kw in rules:
            if kw in blob:
                keys.add(kw)
    return keys


def _match_hot_stocks_to_title(title: str, *, top_n: int = 3) -> list[dict[str, Any]]:
    """按标题关键词从东财人气榜挑样本股（供成稿写量价）。"""
    keys = _title_keywords(title)
    if not keys:
        return []
    try:
        from scripts.tools.wechat_mp_hot_stocks import fetch_hot_stock_rows

        rows = fetch_hot_stock_rows(top_n=20)
    except Exception:
        return []
    scored: list[tuple[float, Any]] = []
    for row in rows:
        bonus = 0.0
        name = row.name or ""
        if any(k in title for k in (name[:2], name[:3])) and len(name) >= 2:
            bonus += 500.0
        if any(k in title for k in keys if k in ("半导体", "芯片", "存储", "算力")):
            bonus += max(0.0, 30.0 - row.rank)
        score = bonus + max(0.0, 25.0 - row.rank)
        if bonus > 0 or keys & {"A股", "涨停", "市值", "沪指", "创业板", "科创"}:
            scored.append((score, row))
    scored.sort(key=lambda x: (-x[0], x[1].rank))
    out: list[dict[str, Any]] = []
    for _, row in scored[:top_n]:
        out.append(
            {
                "matched_stock_name": row.name,
                "matched_stock_code": row.code,
                "matched_stock_rank": row.rank,
                "matched_stock_change_pct": row.change_pct,
            }
        )
    return out


def _build_trend_market_context(title: str) -> str:
    """指数 + 涨跌家数，写入热搜 item 供成稿引用。"""
    try:
        from scripts.tools.daily_briefing_report import fetch_market_indices

        lines = [ln for ln in fetch_market_indices()[:6] if ln and "获取失败" not in ln]
        if lines:
            return "；".join(lines)
    except Exception:
        pass
    return ""


def enrich_trend_hotspot_item(item: dict[str, Any]) -> dict[str, Any]:
    """给热搜条目补盘面样本与可读摘要（避免成稿只剩「微博热搜：标题」）。"""
    out = dict(item)
    title = str(out.get("title") or "").strip()
    if not title:
        return out

    market_ctx = _build_trend_market_context(title)
    if market_ctx:
        out["market_context"] = market_ctx

    stocks = _match_hot_stocks_to_title(title, top_n=3)
    if stocks and not out.get("matched_stock_name"):
        lead = stocks[0]
        out.update(lead)

    sources = "+".join(out.get("sources") or [])
    rank_bits: list[str] = []
    for src, rank in sorted((out.get("ranks") or {}).items(), key=lambda x: x[1]):
        rank_bits.append(f"{src}第{rank}")
    rank_txt = "、".join(rank_bits) if rank_bits else "双榜"

    summary_parts = [f"{rank_txt}热议「{title}」"]
    if market_ctx:
        summary_parts.append(market_ctx.split("；")[0])
    if stocks:
        sample = stocks[0]
        summary_parts.append(
            f"人气样本{sample['matched_stock_name']}（{sample['matched_stock_code']}）"
            f"收盘约{float(sample['matched_stock_change_pct']):+.1f}%"
        )
    out["summary"] = "。".join(summary_parts) + "。"
    out["prefer_stock"] = bool(out.get("matched_stock_name"))
    return out


def _trend_enrich_enabled() -> bool:
    """社会热点深评默认关：enrich 会逐条拉东财指数/热股，慢且污染正文。"""
    raw = os.getenv("WECHAT_MP_HOTSPOT_TREND_ENRICH", "0").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def enrich_trend_hotspot_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_trend_hotspot_item(it) for it in items]


def load_trend_hotspot_items(*, limit: int = 15) -> list[dict[str, Any]]:
    """拉取双榜并返回 hotspot 选题 item 列表；失败返回空列表。"""
    try:
        weibo = fetch_weibo_hot(limit=30)
        baidu = fetch_baidu_hot(limit=30)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []
    if not weibo and not baidu:
        return []
    items = merge_and_rank_trends(weibo, baidu, limit=limit)
    if _trend_enrich_enabled():
        return enrich_trend_hotspot_items(items)
    return items


def preview_trends(*, limit: int = 10) -> str:
    items = load_trend_hotspot_items(limit=limit)
    lines = [f"热搜选题预览 · {datetime.now(TZ).strftime('%Y-%m-%d %H:%M')}", ""]
    if not items:
        lines.append("（抓取失败或为空）")
        return "\n".join(lines)
    for i, item in enumerate(items, 1):
        src = "+".join(item.get("sources") or [])
        score = item.get("attention_score")
        lines.append(f"{i}. [{src}] {item.get('title')} (score={score:.0f})")
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="微博+百度热搜 → hotspot 选题预览")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    print(preview_trends(limit=args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
