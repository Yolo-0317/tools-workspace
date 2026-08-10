#!/usr/bin/env python3
"""影视选题：热度 / 争议度 / 可写性；支持 TMDB 补充 + 人工 curated 队列。"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
TRIAL_PATH = ROOT / "data/wechat_mp_tv_trial.json"
USAGE_PATH = ROOT / "data/wechat_mp_tv_topic_usage.json"
TZ = ZoneInfo("Asia/Shanghai")

# 中文常用译名（TMDB 英文 → 写作用）
_ZH_NAMES: dict[str, str] = {
    "Teach You a Lesson": "铁拳教育",
    "Get Schooled": "铁拳教育",
    "Euphoria": "亢奋",
    "House of the Dragon": "龙族前传",
    "Game of Thrones": "权力的游戏",
    "Stranger Things": "怪奇物语",
    "The Bear": "大熊餐厅",
    "His & Hers": "他和她的，谎",
    "Beef": "怒呛人生",
    "The Pitt": "匹兹堡医护前线",
    "A Knight of the Seven Kingdoms": "七王国的骑士",
    "Michael Jackson: The Verdict": "迈克尔·杰克逊：审判",
    "Wednesday": "星期三",
    "Avatar: The Last Airbender": "降世神通：最后的气宗",
    "The Night Manager": "夜班经理",
    "One Piece": "海贼王",
    "Landman": "石油天王",
    "Silo": "羊毛战记",
}

# 2026-06 网络高热 + 有讨论度（HBO / Netflix 为主；附来源摘要）
CURATED_HOT: list[dict[str, Any]] = [
    {
        "title_en": "Teach You a Lesson",
        "title_zh": "铁拳教育",
        "platform": "Netflix",
        "type": "series",
        "year": "2026",
        "cover_slug": "teach-you-a-lesson",
        "title_override": "追完《铁拳教育》，爽完为什么没特痛快？",
        "ratings_as_of": "2026-06",
        "ratings": {
            "douban": {
                "score": 7.8,
                "label": "约",
                "votes": "开分后",
            },
            "imdb": {
                "score": 7.6,
                "label": "约",
            },
            "rotten_tomatoes": {
                "critics": 80,
                "label": "影评人新鲜度",
                "audience": 72,
                "audience_label": "观众",
            },
            "metacritic": {
                "score": 64,
                "label": "约",
            },
            "tmdb": {
                "score": 7.9,
                "votes": "开分后",
            },
        },
        "heat_score": 99,
        "controversy_score": 96,
        "write_score": 94,
        "hook": "6月5日上线即冲全球榜：教权保护局能否扳回失控校园？",
        "reference_angles": [
            "上线首周韩国 TV-OTT 话题度约 40% 登顶，金武烈演员榜第一",
            "改编网漫《极权教师》原著争议 vs 导演洪钟灿《少年法庭》背书",
            "爽感来自制度失灵出口，不安来自私刑边界",
            "第五集恐龙家长线引发韩国小学教师工会公开声援",
            "85 国 Netflix Top10 vs 教育界团体事前抗议",
        ],
        "sources": [
            "Wikipedia / Good Data：2026-06 韩国话题度与全球 Top10",
            "换日线 / 自由娱乐：真实校暴事件原型与两极评价",
            "Netflix 2026 Korea Showcase：对原著争议公开回应",
        ],
        "hot_until": "2026-07-20",
        "pick_on": "2026-06-18",
    },
    {
        "title_en": "Euphoria",
        "title_zh": "亢奋",
        "platform": "HBO",
        "type": "series",
        "year": "2026",
        "season": 3,
        "title_override": "HBO这部青春剧，为什么老观众吵起来了？",
        "cover_slug": "euphoria",
        "douban_subject_id": "34874603",
        "ratings_as_of": "2026-06",
        "ratings": {
            "douban": {
                "score": 8.0,
                "label": "全季",
                "votes": "30 万+评",
            },
            "imdb": {
                "score": 8.2,
                "label": "全季约",
            },
            "rotten_tomatoes": {
                "critics": 42,
                "label": "S3 影评人新鲜度",
                "audience": 68,
                "audience_label": "S3 观众新鲜度",
            },
            "metacritic": {
                "score": 54,
                "label": "S3 metascore 约",
            },
            "tmdb": {
                "score": 8.1,
                "votes": "1.2 万+评",
            },
        },
        "heat_score": 95,
        "controversy_score": 90,
        "write_score": 88,
        "hook": "第三季回归：收视创新高，但烂番茄创系列新低，值不值得追？",
        "reference_angles": [
            "四年空窗后 premiere 三天 850 万观看 vs  critics 42% 的分裂",
            "Zendaya / Sydney Sweeney 双主线，青春剧是否只剩视觉与争议",
            "毒瘾与成长叙事是否还能打动老观众",
        ],
        "sources": [
            "Collider：Euphoria S3 premiere 850 万观看、RT 42%",
            "FlixPatrol：2026-04 HBO Max 全球榜 #1",
        ],
        "hot_until": "2026-07-15",
    },
    {
        "title_en": "Michael Jackson: The Verdict",
        "title_zh": "迈克尔·杰克逊：审判",
        "platform": "Netflix",
        "type": "series",
        "year": "2026",
        "cover_slug": "michael-jackson-the-verdict",
        "tmdb_id": 323111,
        "title_override": "追完《杰克逊：审判》，全网吵的不是有罪无罪？",
        "ratings_as_of": "2026-06",
        "ratings": {
            "imdb": {"score": 7.4, "label": "约"},
            "rotten_tomatoes": {
                "critics": 80,
                "label": "影评人新鲜度",
                "audience": 6,
                "audience_label": "观众 Popcornmeter",
            },
            "metacritic": {"score": 59, "label": "约"},
            "tmdb": {"score": 7.2, "votes": "开分后"},
        },
        "heat_score": 92,
        "controversy_score": 98,
        "write_score": 85,
        "hook": "网飞全球榜第一却被粉丝刷低分：纪录片与传记电影的对打",
        "reference_angles": [
            "2005 年庭审纪录片 vs 同期 nephew 主演传记片「零提及指控」",
            "Popcornmeter 6% 与 Netflix 美国 Top1 的「评价/流量」背离",
            "名人纪录片是真相还是二次消费",
        ],
        "sources": [
            "ScreenRant：The Verdict 登 Netflix 美国 Top1（2026-06）",
            "与 Michael 传记片 RT 39% vs 观众 97% 的对比",
        ],
        "hot_until": "2026-06-30",
        "pick_on": "2026-06-20",
    },
    {
        "title_en": "Avatar: The Last Airbender",
        "title_zh": "降世神通：最后的气宗",
        "platform": "Netflix",
        "type": "series",
        "year": "2026",
        "season": 2,
        "cover_slug": "avatar-last-airbender",
        "tmdb_id": 82452,
        "title_override": "《降世神通》真人版S2：土之国这一趟，比我想的沉",
        "ratings_as_of": "2026-06",
        "ratings": {
            "douban": {"score": 6.8, "label": "S1 真人版约", "votes": "开分后"},
            "imdb": {"score": 7.3, "label": "S1 约"},
            "rotten_tomatoes": {
                "critics": 62,
                "label": "S1 影评人",
                "audience": 70,
                "audience_label": "S1 观众",
            },
            "metacritic": {"score": None, "label": "S2 影评分待齐"},
            "tmdb": {"score": 7.6, "votes": "S1 约"},
        },
        "heat_score": 94,
        "controversy_score": 82,
        "write_score": 90,
        "hook": "6月25日七集全放：Toph、Azula、Ba Sing Se 齐登场",
        "reference_angles": [
            "S1 RT 62% vs 84 国 Netflix #1 的流量/口碑分裂",
            "Book Two 动画 87% 对照真人压缩 7 集",
            "Toph Miyako 选角与提前进 Ba Sing Se 的时间线争议",
        ],
        "sources": [
            "Netflix Tudum S2 2026-06-25",
            "What's On Netflix 单集时长与集名",
            "Rotten Tomatoes 2024 live-action 页面",
        ],
        "hot_until": "2026-07-15",
        "pick_on": "2026-06-23",
    },
    {
        "title_en": "House of the Dragon",
        "title_zh": "龙族前传",
        "platform": "HBO",
        "type": "series",
        "year": "2026",
        "season": 3,
        "heat_score": 90,
        "controversy_score": 75,
        "write_score": 82,
        "hook": "权游前传第三季：大场面依旧，原著党为何仍不买账",
        "reference_angles": [
            "黑党 vs 绿党内战升级，是否必须看过权游才能入坑",
            "改编与原著「对着干」的争议",
            "2026 六月 HBO 旗舰 vs 短视频剧透文化",
        ],
        "sources": [
            "Winter is Coming：S3 ambitious but undermining source material",
            "Yahoo 台湾 6 月片单：龙族前传 S3 重磅",
        ],
        "hot_until": "2026-07-01",
    },
    {
        "title_en": "His & Hers",
        "title_zh": "他和她的，谎",
        "platform": "Netflix",
        "type": "series",
        "year": "2026",
        "heat_score": 88,
        "controversy_score": 55,
        "write_score": 90,
        "hook": "6 集迷你悬疑： critics 一般，但 Nielsen 称 2026 年最大剧之一",
        "reference_angles": [
            "限集 thriller 是否比 10 季长篇更适合流媒体",
            "每集结尾反转 vs 逻辑漏洞，观众要的是爽还是严丝合缝",
            "Tessa Thompson + Jon Bernthal 双视角叙事",
        ],
        "sources": [
            "Collider：His & Hers 35 天 2560 万观看量级报道",
            "Red Scarf / 中文片单：我会找到你、His & Hers 悬疑档",
        ],
        "hot_until": "2026-07-10",
    },
    {
        "title_en": "Stranger Things",
        "title_zh": "怪奇物语",
        "platform": "Netflix",
        "type": "series",
        "year": "2026",
        "season": 5,
        "heat_score": 86,
        "controversy_score": 70,
        "write_score": 80,
        "hook": "九年终章：最暗的一季，粉丝与影评人为何又吵起来了",
        "reference_angles": [
            "最终季是否「解释太多」牺牲留白",
            " Hawkins 童年终结 vs 成年观众的情感账单",
            "2026 年仍值得补完还是只追热点",
        ],
        "sources": [
            "Red Scarf：2026 最受期待回归之一",
            "Antre du dragon：S5 divided but impactful 讨论",
        ],
        "hot_until": "2026-08-01",
    },
    {
        "title_en": "Beef",
        "title_zh": "怒呛人生",
        "platform": "Netflix",
        "type": "series",
        "year": "2026",
        "season": 2,
        "cover_slug": "beef",
        "douban_subject_id": "35413042",
        "ratings_as_of": "2026-06",
        "ratings": {
            "douban": {"score": 6.3, "label": "S2", "votes": "7000+评"},
            "imdb": {"score": 8.5, "label": "S2 约"},
            "rotten_tomatoes": {"critics": 92, "label": "S2 影评人新鲜度约"},
        },
        "heat_score": 78,
        "controversy_score": 60,
        "write_score": 85,
        "hook": "第二季 8 集短跑： Netflix 迷你剧策略与第一季光环",
        "reference_angles": [
            "路怒升维成阶级寓言，第二季是否还能复制情绪密度",
            "8 集 × 35 分钟 vs 传统 13 集时代",
            "亚裔身份与洛杉矶焦虑的续写",
        ],
        "sources": [
            "Entertainment Substack：2026 Netflix 短季策略与 Beef 收视讨论",
        ],
        "hot_until": "2026-07-20",
    },
    {
        "title_en": "The Pitt",
        "title_zh": "匹兹堡医护前线",
        "platform": "HBO",
        "type": "series",
        "year": "2026",
        "season": 2,
        "heat_score": 75,
        "controversy_score": 40,
        "write_score": 78,
        "hook": "打工人必看医疗剧？第二季接棒 Euphoria 前的 HBO 底盘",
        "reference_angles": [
            "单集病例 vs 长线人物，医疗剧如何不变成 CSI",
            "Noah Wyle 回归与 HBO 2026 剧集矩阵",
        ],
        "sources": [
            "FlixPatrol / ComingSoon：The Pitt 曾居 HBO Max #2",
            "Red Scarf：匹兹堡医护前线 S2",
        ],
        "hot_until": "2026-07-15",
    },
    {
        "title_en": "A Knight of the Seven Kingdoms",
        "title_zh": "七王国的骑士",
        "platform": "HBO",
        "type": "series",
        "year": "2026",
        "heat_score": 72,
        "controversy_score": 35,
        "write_score": 80,
        "hook": "权游宇宙小品：小人物叙事是否比龙族前传更耐看",
        "reference_angles": [
            " Dunk 与 Egg 故事线，低预算高口碑的可能",
            "与 House of the Dragon 同宇宙不同节奏",
        ],
        "sources": [
            "Entertainment Substack：HBO 2026 开年 A Knight of the Seven Kingdoms",
        ],
        "hot_until": "2026-07-01",
    },
]


def tv_topic_source() -> str:
    """curated=仅人工队列；trends=优先热搜；mixed=热搜+curated（默认）。"""
    raw = (os.getenv("WECHAT_MP_TV_SOURCE") or "mixed").strip().lower()
    if raw in {"trend", "trends", "hot", "热搜"}:
        return "trends"
    if raw in {"curated", "manual"}:
        return "curated"
    return "mixed"


def _match_tv_topic_override(topic: dict[str, Any], needle: str) -> bool:
    n = (needle or "").strip().lower()
    if not n:
        return False
    for key in ("title_zh", "title_en", "trend_title", "hook", "cover_slug"):
        val = str(topic.get(key) or "").strip().lower()
        if val and (n in val or val in n):
            return True
    if n in ("蜘蛛侠", "spider-man", "spiderman") and "蜘蛛侠" in str(topic.get("title_zh") or ""):
        return True
    return False


def _topic_from_env_override(queue: list[dict[str, Any]]) -> dict[str, Any] | None:
    needle = (os.getenv("WECHAT_MP_TV_TOPIC") or "").strip()
    if not needle:
        return None
    for t in queue:
        if _match_tv_topic_override(t, needle):
            return dict(t)
    # 尝试从当日热搜即时构造
    try:
        from scripts.tools.wechat_mp_tv_trend_topics import build_known_tv_topic, fetch_tv_trend_topics

        known = build_known_tv_topic(needle)
        if known:
            return known
        for t in fetch_tv_trend_topics(limit=15):
            if _match_tv_topic_override(t, needle):
                return dict(t)
    except Exception:
        pass
    return None


def load_tv_trial_config(*, path: Path | None = None) -> dict[str, Any]:
    p = path or TRIAL_PATH
    if not p.is_file():
        return {"enabled": False, "queue": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"enabled": False, "queue": []}


def tv_trial_active(*, when: datetime | None = None) -> bool:
    cfg = load_tv_trial_config()
    if not cfg.get("enabled"):
        return False
    until = str(cfg.get("until") or "").strip()
    if until:
        try:
            if (when or datetime.now(TZ)).date() > date.fromisoformat(until):
                return False
        except ValueError:
            pass
    queue = cfg.get("queue") or []
    return bool(queue) or bool(CURATED_HOT)


def save_tv_trial_config(data: dict[str, Any], *, path: Path | None = None) -> None:
    p = path or TRIAL_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(TZ).isoformat(timespec="seconds")
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_usage() -> dict[str, Any]:
    if not USAGE_PATH.is_file():
        return {"used": {}}
    try:
        return json.loads(USAGE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"used": {}}


def _save_usage(data: dict[str, Any]) -> None:
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(TZ).isoformat(timespec="seconds")
    USAGE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _topic_key(topic: dict[str, Any]) -> str:
    en = str(topic.get("title_en") or "").strip()
    season = topic.get("season")
    return f"{en}#S{season}" if season else en


def _parse_date(raw: str) -> date | None:
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError:
        return None


def _is_hot(topic: dict[str, Any], *, on: date) -> bool:
    until = _parse_date(str(topic.get("hot_until") or ""))
    if until and on > until:
        return False
    return True


def _score_topic(topic: dict[str, Any]) -> float:
    heat = float(topic.get("heat_score") or 0)
    controversy = float(topic.get("controversy_score") or 0)
    write = float(topic.get("write_score") or 0)
    # 可写 + 有争议更容易出稿；热度打底
    return heat * 0.45 + controversy * 0.25 + write * 0.30


def rank_topics(topics: list[dict[str, Any]], *, on: date | None = None) -> list[dict[str, Any]]:
    on = on or datetime.now(TZ).date()
    alive = [t for t in topics if _is_hot(t, on=on)]
    return sorted(alive, key=_score_topic, reverse=True)


def _fetch_tmdb_trending(*, limit: int = 8) -> list[dict[str, Any]]:
    read_token = os.getenv("TMDB_READ_ACCESS_TOKEN", "").strip()
    api_key = os.getenv("TMDB_API_KEY", "").strip()
    if not read_token and not api_key:
        return []
    try:
        import requests

        url = "https://api.themoviedb.org/3/trending/tv/week"
        params: dict[str, str] = {"language": "zh-CN"}
        if read_token:
            resp = requests.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {read_token}"},
                timeout=15,
            )
        else:
            params["api_key"] = api_key
            resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results") or []
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for row in results[:limit]:
        if not isinstance(row, dict):
            continue
        en = str(row.get("name") or row.get("original_name") or "").strip()
        if not en:
            continue
        zh = _ZH_NAMES.get(en) or str(row.get("name") or "").strip()
        platform = "Netflix" if "netflix" in en.lower() else "HBO"
        overview = str(row.get("overview") or "").strip()[:120]
        out.append(
            {
                "title_en": en,
                "title_zh": zh if zh != en else "",
                "platform": platform,
                "type": "series",
                "year": str((row.get("first_air_date") or "2026")[:4]),
                "heat_score": min(99, int(float(row.get("popularity") or 50))),
                "controversy_score": 45,
                "write_score": 70,
                "hook": overview or f"TMDB 本周 trending：{en}",
                "reference_angles": [f"TMDB 本周热度 {row.get('popularity')}"],
                "sources": ["TMDB trending/tv/week"],
                "hot_until": (datetime.now(TZ).date() + timedelta(days=40)).isoformat(),
                "from_tmdb": True,
            }
        )
    return out


def merge_topic_queues(
    curated: list[dict[str, Any]],
    tmdb: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for t in curated:
        merged[_topic_key(t)] = dict(t)
    for t in tmdb:
        k = _topic_key(t)
        if k in merged:
            merged[k]["heat_score"] = max(
                int(merged[k].get("heat_score") or 0),
                int(t.get("heat_score") or 0),
            )
            continue
        merged[k] = dict(t)
    return rank_topics(list(merged.values()))


def refresh_tv_queue(*, include_tmdb: bool = True) -> dict[str, Any]:
    """刷新 data/wechat_mp_tv_trial.json 的 queue（保留 enabled/until 等开关）。"""
    cfg = load_tv_trial_config()
    tmdb = _fetch_tmdb_trending() if include_tmdb else []
    trend_topics: list[dict[str, Any]] = []
    src = tv_topic_source()
    if src in {"trends", "mixed"}:
        try:
            from scripts.tools.wechat_mp_tv_trend_topics import fetch_tv_trend_topics

            trend_topics = fetch_tv_trend_topics(limit=10)
        except Exception:
            trend_topics = []
    base = [] if src == "trends" else list(CURATED_HOT)
    queue = merge_topic_queues(base, tmdb)
    if trend_topics:
        queue = merge_topic_queues(trend_topics, queue)
    cfg["queue"] = queue
    cfg["selection_mode"] = cfg.get("selection_mode") or "heat_rank"
    cfg["tv_source"] = src
    cfg["curated_refreshed_at"] = datetime.now(TZ).isoformat(timespec="seconds")
    cfg["curated_sources"] = [
        "微博 + 百度热搜（影视向，WECHAT_MP_TV_SOURCE）",
        "ScreenRant / Collider / FlixPatrol（curated）",
        "Red Scarf / Yahoo 台湾片单",
        "TMDB trending/tv/week（可选，需 TMDB_READ_ACCESS_TOKEN）",
    ]
    save_tv_trial_config(cfg)
    return cfg


def pick_tv_topic(*, when: datetime | None = None) -> dict[str, Any]:
    cfg = load_tv_trial_config()
    queue = [q for q in (cfg.get("queue") or []) if isinstance(q, dict)]
    now = when or datetime.now(TZ)
    today = now.date()

    override = _topic_from_env_override(queue)
    if override:
        topic = dict(override)
        topic["_day_index"] = 0
        return topic

    try:
        from scripts.tools.wechat_mp_tv_morning_discussion import (
            pick_morning_discussion_topic,
            tv_morning_pick_mode,
        )

        if tv_morning_pick_mode() == "discussion":
            topic = pick_morning_discussion_topic(when=now)
            topic["_day_index"] = 0
            return topic
    except Exception:
        pass

    if not queue:
        src = tv_topic_source()
        if src in {"trends", "mixed"}:
            try:
                from scripts.tools.wechat_mp_tv_trend_topics import fetch_tv_trend_topics

                trend_queue = fetch_tv_trend_topics(limit=10)
                if trend_queue:
                    queue = trend_queue if src == "trends" else merge_topic_queues(trend_queue, rank_topics(CURATED_HOT))
            except Exception:
                pass
        if not queue:
            queue = rank_topics(CURATED_HOT)
    else:
        src = tv_topic_source()
        if src in {"trends", "mixed"}:
            try:
                from scripts.tools.wechat_mp_tv_trend_topics import fetch_tv_trend_topics

                trend_queue = fetch_tv_trend_topics(limit=8)
                if trend_queue:
                    queue = (
                        trend_queue
                        if src == "trends"
                        else merge_topic_queues(trend_queue, queue)
                    )
            except Exception:
                pass
    queue = rank_topics(queue, on=today)
    if not queue:
        raise RuntimeError(f"影视队列无有效条目：请运行 refresh 或编辑 {TRIAL_PATH}")

    usage = _load_usage()
    used: dict[str, str] = dict(usage.get("used") or {})

    # 1) 显式指定 pick_on=YYYY-MM-DD
    for t in queue:
        pick_on = _parse_date(str(t.get("pick_on") or ""))
        if pick_on == today:
            topic = dict(t)
            topic["_day_index"] = queue.index(t)
            return topic

    # 2) 优先未写过且分数高
    for t in queue:
        key = _topic_key(t)
        if key not in used:
            topic = dict(t)
            topic["_day_index"] = queue.index(t)
            used[key] = today.isoformat()
            usage["used"] = used
            _save_usage(usage)
            return topic

    # 3) 都写过则取得分最高且最久未写
    def _last_used(k: str) -> date:
        raw = used.get(k) or "1970-01-01"
        return _parse_date(raw) or date(1970, 1, 1)

    queue.sort(key=lambda t: (_last_used(_topic_key(t)), -_score_topic(t)))
    topic = dict(queue[0])
    topic["_day_index"] = 0
    used[_topic_key(topic)] = today.isoformat()
    usage["used"] = used
    _save_usage(usage)
    return topic


def format_topic_brief(topic: dict[str, Any]) -> str:
    label = topic.get("title_zh") or topic.get("title_en")
    return (
        f"{label} | {topic.get('platform')} | "
        f"heat={topic.get('heat_score')} controversy={topic.get('controversy_score')}"
    )
