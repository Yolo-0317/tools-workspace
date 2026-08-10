#!/usr/bin/env python3
"""微博 + 百度热搜 → 影视选题（国产剧/韩剧/电影/流媒体，不限美剧）。"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from scripts.tools.wechat_mp_hot_trends import (
    TrendRow,
    _norm_key,
    _titles_overlap,
    fetch_baidu_hot,
    fetch_weibo_hot,
)

TZ = ZoneInfo("Asia/Shanghai")

# 影视相关：片名/类型/平台/行业词
_TV_BOOST_KEYWORDS: tuple[str, ...] = (
    "剧",
    "电影",
    "影院",
    "票房",
    "上映",
    "开播",
    "定档",
    "收官",
    "大结局",
    "续集",
    "第二季",
    "第三季",
    "番剧",
    "动漫",
    "动画",
    "纪录片",
    "网剧",
    "短剧",
    "古偶",
    "仙侠",
    "悬疑",
    "豆瓣",
    "评分",
    "烂片",
    "神作",
    "预告",
    "杀青",
    "流媒体",
    "Netflix",
    "HBO",
    "爱奇艺",
    "优酷",
    "腾讯",
    "芒果",
    "B站",
    "韩剧",
    "日剧",
    "美剧",
    "好莱坞",
    "皮克斯",
    "迪士尼",
    "漫威",
    "九门",
    "凤囚凰",
    "刑警荣誉",
    "正剧",
)

# 纯八卦降权（仍可能是影视人，但不宜写剧评）
_TV_GOSSIP_DOWNRANK: tuple[str, ...] = (
    "离婚",
    "恋情",
    "官宣恋情",
    "路透造型",
    "瘦成",
    "妆容",
    "见面会",
    "粉丝应援",
)

# 热搜标题 → 片名/主标题（优先长匹配）
_SHOW_ALIASES: tuple[tuple[str, str], ...] = (
    ("凤囚凰", "凤囚凰"),
    ("九门", "九门"),
    ("老九门", "老九门"),
    ("刑警荣誉", "刑警荣誉"),
    ("花儿与少年", "花儿与少年"),
    ("亢奋", "亢奋"),
    ("铁拳教育", "铁拳教育"),
    ("蜘蛛侠", "蜘蛛侠：崭新之日"),
    ("崭新之日", "蜘蛛侠：崭新之日"),
)


def _slugify(title: str) -> str:
    s = re.sub(r"\s+", "-", (title or "").strip().lower())
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "", s)
    return s[:48] or "tv-trend"


def extract_show_title(trend_title: str) -> str:
    """从热搜标题抽可写片名。"""
    blob = (trend_title or "").strip()
    for needle, show in _SHOW_ALIASES:
        if needle in blob:
            return show
    # 《片名》
    m = re.search(r"《([^》]{2,16})》", blob)
    if m:
        return m.group(1).strip()
    # 前段 2～6 字 + 剧/电影
    m = re.search(r"^([\u4e00-\u9fffA-Za-z0-9]{2,8})(?:开播|定档|收官|烂片|神作|评分)", blob)
    if m:
        return m.group(1).strip()
    # 去掉尾部评价，取前 2～6 字
    core = re.split(r"[，,。；;：:|｜]", blob, maxsplit=1)[0].strip()
    core = re.sub(r"(古偶|烂片|史上|难以|逾越|的|高峰|爆开|对比|出场).*$", "", core).strip()
    if 2 <= len(core) <= 8:
        return core
    return blob[:6].strip()


def is_tv_trend(title: str) -> bool:
    blob = (title or "").strip()
    if not blob:
        return False
    if re.search(r"《[^》]{2,12}》", blob):
        return True
    strong = (
        "剧",
        "电影",
        "影院",
        "票房",
        "古偶",
        "烂片",
        "豆瓣",
        "编剧",
        "定档",
        "开播",
        "收官",
        "预告",
        "动漫",
        "动画",
        "纪录片",
        "网剧",
        "短剧",
        "正剧",
        "九门",
        "凤囚凰",
        "刑警荣誉",
        "蜘蛛侠",
        "八仙",
    )
    if any(kw in blob for kw in strong):
        return True
    if any(kw in blob for kw in ("爱奇艺", "优酷", "芒果", "B站", "Netflix", "HBO")):
        return "剧" in blob or "电影" in blob or "影" in blob
    return False


def _score_tv_trend(title: str, *, ranks: list[int], sources: set[str]) -> float:
    score = 0.0
    for rank in ranks:
        score += max(0.0, 900.0 - rank * 18.0)
    if len(sources) >= 2:
        score += 400.0
    if any(kw in title for kw in _TV_BOOST_KEYWORDS):
        score += 300.0
    if any(kw in title for kw in ("烂片", "豆瓣", "魔改", "编剧", "收官", "定档", "票房")):
        score += 200.0
    if any(kw in title for kw in _TV_GOSSIP_DOWNRANK):
        score -= 350.0
    if len(title) > 28:
        score -= 60.0
    return score


def merge_tv_trends(
    weibo: list[TrendRow],
    baidu: list[TrendRow],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """合并双榜影视向热搜，输出 topic 兼容 dict（未 enrich）。"""
    buckets: dict[str, dict[str, Any]] = {}

    def ingest(row: TrendRow) -> None:
        if not is_tv_trend(row.title):
            return
        show = extract_show_title(row.title)
        key = _norm_key(show) or _norm_key(row.title)
        if not key:
            return
        entry = buckets.get(key)
        if entry is None:
            entry = {
                "trend_title": row.title,
                "show_title": show,
                "sources": [row.source],
                "ranks": {row.source: row.rank},
                "tags": [row.tag] if row.tag else [],
                "href": row.url,
            }
            buckets[key] = entry
        else:
            if row.source not in entry["sources"]:
                entry["sources"].append(row.source)
            entry["ranks"][row.source] = row.rank
            if row.rank < min(entry["ranks"].values()):
                entry["trend_title"] = row.title
            if row.tag and row.tag not in entry["tags"]:
                entry["tags"].append(row.tag)

    for row in weibo:
        ingest(row)
    for row in baidu:
        merged = False
        for entry in buckets.values():
            if _titles_overlap(row.title, str(entry.get("trend_title") or "")):
                fake = TrendRow(
                    title=entry["trend_title"],
                    source=row.source,
                    rank=row.rank,
                    tag=row.tag,
                    url=row.url,
                )
                ingest(fake)
                merged = True
                break
        if not merged:
            ingest(row)

    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in buckets.values():
        title = str(entry.get("trend_title") or "")
        ranks = [int(v) for v in (entry.get("ranks") or {}).values()]
        sources = set(entry.get("sources") or [])
        score = _score_tv_trend(title, ranks=ranks, sources=sources)
        entry["attention_score"] = score
        scored.append((score, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


_KNOWN_TREND_SHOWS: dict[str, dict[str, Any]] = {
    "凤囚凰": {
        "title_en": "Untouchable Lovers",
        "platform": "湖南卫视 / 爱奇艺",
        "year": "2018",
        "cover_slug": "feng-qiu-huang",
        "douban_subject_id": "26928226",
        "ratings": {
            "douban": {"score": 3.8, "label": "约", "votes": "13万+评"},
        },
        "reference_angles": [
            "2026年6月编剧周末澄清：40集剧仅执笔12集，署名争议再起",
            "后半段原创角色霍璇戏份过重，观众戏称「霍璇传」",
            "原著口碑高、剧版魔改，容止人设崩塌是古偶改编典型坑",
            "八年后再上热搜，与演员新作带动考古有关",
        ],
        "sources": [
            "编剧周末微博澄清（2026-06）",
            "新浪娱乐 / 今日头条：凤囚凰编剧回应热搜",
        ],
    },
    "九门": {
        "title_en": "The Mystic Nine",
        "platform": "爱奇艺",
        "year": "2016",
        "cover_slug": "jiu-men",
        "douban_subject_id": "25975243",
        "reference_angles": [
            "陈伟霆版张启山 vs 老九门经典形象，出场对比引发讨论",
            "盗墓笔记宇宙衍生，民国悬疑+探险",
        ],
    },
    "蜘蛛侠：崭新之日": {
        "title_en": "Spider-Man: Brand New Day",
        "platform": "院线 / 漫威",
        "type": "film",
        "year": "2026",
        "cover_slug": "spider-man-brand-new-day",
        "tmdb_movie_id": 969681,
        "ratings": {
            "douban": {"score": 7.8, "label": "开分", "votes": "2.6万+评"},
            "imdb": {"score": 7.2, "label": "约", "votes": "开分后"},
            "rotten_tomatoes": {
                "critics": 78,
                "label": "影评人新鲜度",
                "audience": 85,
                "audience_label": "观众",
            },
        },
        "reference_angles": [
            "荷兰弟第四部独立蜘蛛侠，承接《英雄无归》后彼得·帕克身份重置",
            "反派阵容含毒液相关线，粉丝关心与索尼宇宙的衔接",
            "百度热议「好看吗」：超级英雄片疲劳 vs 重启叙事能否拉回路人",
            "豆瓣开分约 7.8，内地首日票房破 2 亿",
            "烂番茄新鲜度开局约 91%，回归街头蜘蛛侠叙事",
        ],
        "sources": [
            "百度热搜：《蜘蛛侠：崭新之日》好看吗",
            "漫威官方物料与院线排片公开信息",
        ],
    },
}


def _enrich_known_show(topic: dict[str, Any]) -> dict[str, Any]:
    show = str(topic.get("title_zh") or "").strip()
    extra = _KNOWN_TREND_SHOWS.get(show)
    if not extra:
        return topic
    out = dict(topic)
    for k, v in extra.items():
        if k == "reference_angles":
            merged = list(v) + [x for x in (out.get("reference_angles") or []) if x not in v]
            out["reference_angles"] = merged[:6]
        elif k in {"cover_slug", "type", "platform", "year", "title_override", "title_en", "tmdb_movie_id"} and v:
            out[k] = v
        elif not out.get(k):
            out[k] = v
    return out


def trend_item_to_topic(item: dict[str, Any], *, on: date | None = None) -> dict[str, Any]:
    """把热搜条目转成 wechat_mp_tv_topics 选题 dict。"""
    on = on or datetime.now(TZ).date()
    show = str(item.get("show_title") or extract_show_title(str(item.get("trend_title") or ""))).strip()
    trend = str(item.get("trend_title") or show).strip()
    ranks = item.get("ranks") or {}
    rank_vals = [int(v) for v in ranks.values()]
    best_rank = min(rank_vals) if rank_vals else 50
    sources = "+".join(item.get("sources") or [])
    heat = max(55, min(99, int(95 - best_rank * 1.2)))
    controversy = 70
    if any(k in trend for k in ("烂片", "魔改", "编剧", "吵", "争议", "崩")):
        controversy = min(99, controversy + 18)
    write_score = min(95, 72 + (controversy - 70) // 2)

    hook = trend
    if len(hook) > 42:
        hook = f"双榜热议「{show}」：{trend.split('，')[0][:28]}"

    ref_angles = [
        f"{sources}热议：{trend}",
    ]
    if len(item.get("sources") or []) >= 2:
        ref_angles.append("微博与百度同日上榜，讨论热度高")

    return _enrich_known_show(
        {
        "title_zh": show,
        "title_en": "",
        "platform": "国产剧",
        "type": "series",
        "year": "",
        "cover_slug": _slugify(show),
        "from_trend": True,
        "trend_title": trend,
        "trend_sources": list(item.get("sources") or []),
        "trend_ranks": ranks,
        "heat_score": heat,
        "controversy_score": controversy,
        "write_score": write_score,
        "hook": hook,
        "reference_angles": ref_angles,
        "sources": [f"微博/百度热搜：{trend}"],
        "hot_until": (on + timedelta(days=21)).isoformat(),
        }
    )


def build_known_tv_topic(needle: str) -> dict[str, Any] | None:
    """WECHAT_MP_TV_TOPIC 指定片名时，即使不在当日热搜也可成稿。"""
    n = (needle or "").strip()
    if not n:
        return None
    nl = n.lower()
    for show, extra in _KNOWN_TREND_SHOWS.items():
        en = str(extra.get("title_en") or "").lower()
        if n in show or show in n or nl in show.lower() or (en and (nl in en or en in nl)):
            return trend_item_to_topic(
                {
                    "show_title": show,
                    "trend_title": show,
                    "sources": ["指定选题"],
                    "ranks": {},
                }
            )
    return None


def fetch_tv_trend_topics(*, limit: int = 8) -> list[dict[str, Any]]:
    """拉取双榜并返回影视选题列表；失败返回空列表。"""
    try:
        weibo = fetch_weibo_hot(limit=50)
        baidu = fetch_baidu_hot(limit=50)
    except Exception:
        return []
    items = merge_tv_trends(weibo, baidu, limit=limit)
    on = datetime.now(TZ).date()
    return [trend_item_to_topic(it, on=on) for it in items]


def preview_tv_trends(*, limit: int = 8) -> str:
    topics = fetch_tv_trend_topics(limit=limit)
    lines = [f"影视热搜选题 · {datetime.now(TZ).strftime('%Y-%m-%d %H:%M')}", ""]
    if not topics:
        lines.append("（抓取失败或无影视向词条）")
        return "\n".join(lines)
    for i, t in enumerate(topics, 1):
        ranks = t.get("trend_ranks") or {}
        rank_txt = "、".join(f"{k}#{v}" for k, v in sorted(ranks.items(), key=lambda x: x[1]))
        lines.append(
            f"{i}. 《{t.get('title_zh')}》 heat={t.get('heat_score')} "
            f"({rank_txt}) · {t.get('trend_title')}"
        )
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="微博+百度热搜 → 影视选题预览")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    print(preview_tv_trends(limit=args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
