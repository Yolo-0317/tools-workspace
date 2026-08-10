#!/usr/bin/env python3
"""公众号「热点深评」：每日 1 主题 ×（事实 + 舆情 + 盘面 + AI 点评）。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.deepseek_client import (
    call_wechat_mp_llm,
    is_wechat_mp_llm_configured,
)
from scripts.tools.news_sentiment import sentiment_label
from scripts.tools.wechat_mp_monetization import monetization_prompt_block
from scripts.tools.wechat_mp_news_article import (
    _AI_COMMENT_BANNED,
    _infer_news_angle,
    _pick_fallback_comment,
    _sanitize_news_reader_meta,
    fetch_news_engagement,
    load_top_news_items,
    news_pick_params,
)
from scripts.tools.wechat_mp_prose import (
    HOTSPOT_BANNED_SECTION_TITLES,
    HOTSPOT_BOILERPLATE_PHRASES,
    HOTSPOT_FIELD_LABELS,
    HOTSPOT_RIGID_FIELD_LABELS,
    humanize_hotspot_boilerplate,
    humanize_hotspot_field_labels,
    strip_hotspot_subheadings,
)
from scripts.tools.wechat_mp_public import (
    PLATFORM_PROPERTY_RISK_RULE,
    PUBLIC_MP_WRITER_RULE,
)

TZ = ZoneInfo("Asia/Shanghai")

HOTSPOT_MIN_BODY_CHARS = 2000
HOTSPOT_TARGET_BODY_CHARS = 2400

_GEO_OIL_KEYWORDS = frozenset({"油服", "油运", "布伦特", "炼化", "OPEC"})

HOTSPOT_READER_META_RULE = (
    "开篇直入主题：第一句写清热搜主体、当日盘面数字、和哪条 A 股链有关。"
    "禁止结构说明、阅读路径、编审预告。"
    "禁止「今天深写」「深写这条」「牵动着…链」「为啥盯这条」「明天盯什么」等模板句。"
)

HOTSPOT_CONTEXT_RULE = (
    "禁止写选题过程：候选几条、舍弃、相较其它标题、同批素材等编审后台用语。"
)

HOTSPOT_READER_DATA_RULE = (
    "禁止向读者交代数据采集缺口：勿写「数据未获取」「样本个股…未获取」「交易时段…未获取」等。"
    "缺具体个股时改写板块梯队、指数涨跌、油价/运价是否同向等可观察现象；"
    "仍无可写数字时用「链条内个股分化，尚未形成一致定价」。"
)

HOTSPOT_RESEARCHER_VOICE_RULE = """
【热点深评口吻】仿中证报/证券时报快评：记者写稿，不是 AI 导读。
- 先读【参考文章·仿写】，学参考稿**开头第一句**怎么写（直接上数字/公司名），然后照着写。
- **禁止元叙述**：不要写「公开报道里」「值得先记住」「盘面一句」「热搜在聊」「双榜讨论」「据悉」「不难发现」等。
- 首段就是新闻本身：「7月30日收盘，市值前十里9家收涨，建行、工行创历史新高。」——不要铺垫。
- **禁止一切小标题**；每段 2～4 句、≤150 字，段间空一行（短段利于手机阅读）。
- 中段列 3～6 家公司+涨跌幅；末段一句次日观察。指数全文最多 1 次。
"""

_THEME_BUCKETS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "session_theme",
        (
            "科创50",
            "V型反转",
            "半导体领涨",
            "芯片产业链",
            "科创芯片",
            "跌停潮后半导体",
            "硬科技全线",
        ),
    ),
    (
        "policy_rescue",
        (
            "中国国新",
            "国新投资",
            "中国诚通",
            "诚通资本",
            "中央汇金",
            "汇金",
            "证金",
            "维护市场稳定",
            "维护资本市场",
            "资本市场平稳",
            "稳市机制",
            "稳市",
            "救市",
            "专项再贷款",
            "股票回购增持再贷款",
            "监管座谈",
            "央企密集增持",
        ),
    ),
    ("geo", ("伊朗", "中东", "霍尔木兹", "以军", "原油", "油价", "OPEC", "地缘")),
    ("tech", ("半导体", "芯片", "AI", "华为", "英伟达", "算力", "HBM", "存储")),
    ("space", ("火箭", "回收", "航天", "卫星", "低空", "商业航天", "发射")),
    ("macro", ("美联储", "非农", "CPI", "降息", "美债", "美元", "汇率")),
    ("policy", ("央行", "降准", "降息", "MLF", "LPR", "流动性", "国务院")),
    ("emotion", ("涨停", "连板", "龙头", "妖股", "情绪", "炸板")),
    ("earnings", ("业绩", "预增", "预亏", "净利润", "营收", "年报", "季报")),
)


@dataclass(frozen=True)
class HotspotTopic:
    item: dict[str, Any]
    bucket: str
    score: float
    section_title: str


_LAST_BUILT_HOTSPOT_TOPIC: dict[str, Any] | None = None


def get_last_built_hotspot_topic() -> dict[str, Any] | None:
    return _LAST_BUILT_HOTSPOT_TOPIC


def hotspot_topic_as_discussion(topic: HotspotTopic) -> dict[str, Any]:
    """热点深评 → 话题讨论配图/封面用的 topic dict。"""
    title = str(topic.item.get("title") or topic.section_title).strip()
    urls: list[str] = []
    for key in ("href", "url"):
        u = str(topic.item.get(key) or "").strip()
        if u.startswith("http") and u not in urls:
            urls.append(u)
    for row in topic.item.get("web_research") or []:
        if not isinstance(row, dict):
            continue
        u = str(row.get("url") or "").strip()
        if u.startswith("http") and u not in urls:
            urls.append(u)
    slug = re.sub(r"[^\w\-]+", "-", title[:28]).strip("-").lower() or "hotspot"
    return {
        "title_zh": title,
        "trend_title": title,
        "cover_slug": slug,
        "from_trend": True,
        "research_urls": urls,
    }


def hotspot_social_layout_enabled() -> bool:
    """热搜选题热点深评：同题报道配图 + 事件封面（非财经插图槽）。"""
    if hotspot_source() != "trends":
        return False
    raw = (os.getenv("WECHAT_MP_HOTSPOT_SOCIAL_FIGURES") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


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


def hotspot_min_body_gate(*, social: bool = False) -> int:
    """成稿门禁字数；社会热点 prompt 仍写 2000，默认容差 200 字。"""
    if not social:
        return HOTSPOT_MIN_BODY_CHARS
    slack = _env_int("WECHAT_MP_HOTSPOT_MIN_BODY_SLACK", 200)
    return max(1500, HOTSPOT_MIN_BODY_CHARS - slack)


def hotspot_topic_count() -> int:
    return max(1, min(3, _env_int("WECHAT_MP_HOTSPOT_TOPICS", 1)))


def hotspot_candidate_count() -> int:
    return max(3, min(10, _env_int("WECHAT_MP_HOTSPOT_CANDIDATES", 5)))


def hotspot_llm_pick_enabled() -> bool:
    """是否单独调一次 LLM 定题（慢）；默认关，改在成稿 prompt 里一并选题。"""
    return _env_bool("WECHAT_MP_HOTSPOT_LLM_PICK", False)


def hotspot_skip_engagement() -> bool:
    """默认跳过 OpenCLI 抓评论数，用库内快讯+attention 初筛（快很多）。"""
    return _env_bool("WECHAT_MP_HOTSPOT_SKIP_ENGAGEMENT", True)


def hotspot_source() -> str:
    """选题来源：trends=微博+百度热搜（默认）；news=宏观快讯库。"""
    raw = (os.getenv("WECHAT_MP_HOTSPOT_SOURCE") or "trends").strip().lower()
    if raw in {"news", "macro", "db"}:
        return "news"
    return "trends"


def hotspot_merged_llm() -> bool:
    """成稿时一次 LLM 完成「从候选定题+写正文」（热搜选题时默认关）。"""
    if hotspot_source() == "trends":
        return _env_bool("WECHAT_MP_HOTSPOT_MERGED_LLM", False)
    return _env_bool("WECHAT_MP_HOTSPOT_MERGED_LLM", True)


def manual_hotspot_topic_hint() -> str:
    return os.getenv("WECHAT_MP_HOTSPOT_TOPIC", "").strip()


def _theme_bucket(title: str) -> str:
    blob = (title or "").strip()
    for name, kws in _THEME_BUCKETS:
        if any(kw in blob for kw in kws):
            return name
    return "other"


def _topic_score(item: dict[str, Any], engagement: dict[str, dict[str, int]]) -> float:
    """初筛分：只用于排出 top-N 候选；最终 1 题由成稿 LLM 或手动指定。"""
    from scripts.tools.news_db import (
        _item_calendar_date,
        market_rescue_attention_boost,
        session_theme_attention_boost,
    )

    if hotspot_skip_engagement() and item.get("attention_score") is not None:
        base = float(item.get("attention_score") or 0)
    else:
        href = str(item.get("href") or item.get("url") or "").strip()
        comments = 0
        if href and href in engagement:
            comments = int((engagement.get(href) or {}).get("comment") or 0)
        base = comments * 0.6
    priority = max(session_theme_attention_boost(item), market_rescue_attention_boost(item))
    if priority > 0 and base < priority:
        base = priority
    # 跨日旧闻：硬封顶，避免稳市/深V 衰减后仍压过当日新稿
    day = _item_calendar_date(item)
    today = datetime.now(TZ).date()
    if day is not None and day < today:
        base = min(base * 0.12, 4.0)
    rank = int(item.get("matched_stock_rank") or 99)
    stock_bonus = max(0.0, (12 - rank) / 12.0) if item.get("matched_stock_name") else 0.0
    return base + stock_bonus * 40.0 + (10 if item.get("prefer_stock") else 0)


def _load_hotspot_raw_items(*, limit: int) -> list[dict[str, Any]]:
    """hotspot 候选池：默认微博+百度热搜；可 WECHAT_MP_HOTSPOT_SOURCE=news 回退快讯库。"""
    if hotspot_source() == "trends":
        from scripts.tools.wechat_mp_hot_trends import load_trend_hotspot_items

        items = load_trend_hotspot_items(limit=limit)
        if items:
            return items
        if not _env_bool("WECHAT_MP_HOTSPOT_TRENDS_FALLBACK_NEWS", True):
            return []
    pool_limit, _, hours, _ = news_pick_params()
    pool_limit = max(pool_limit, 40)
    engagement = None
    if not hotspot_skip_engagement():
        engagement = fetch_news_engagement(limit=pool_limit)
    from scripts.tools.news_db import pick_top_news_by_attention

    items = pick_top_news_by_attention(
        limit=limit,
        pool_limit=pool_limit,
        hours=hours,
        engagement=engagement,
        prefer_stock=False,
    )
    if items:
        return items
    if hotspot_skip_engagement():
        return []
    return load_top_news_items(limit=limit)


_GEO_SECTION_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("以色列", "伊朗", "内塔尼亚胡", "霍尔木兹", "中东"), "中东局势再升温"),
    (("俄乌", "乌克兰", "普京"), "俄乌局势"),
    (("特朗普", "美联储", "关税"), "海外政策扰动"),
)


def _topic_section_title(item: dict[str, Any]) -> str:
    stock = str(item.get("matched_stock_name") or "").strip()
    title = str(item.get("title") or "").strip()
    blob = re.sub(r"\s+", "", title)
    blob = blob.replace("\u201c", "").replace("\u201d", "").replace('"', "")

    if "V型反转" in blob or "V型" in blob:
        if "半导体" in blob or "芯片" in blob or "存储" in blob:
            return "科创50深V反转，半导体链"
        if "科创50" in blob:
            return "科创50深V反转"
        return "科技深V反转"
    if "科创50" in blob and any(k in blob for k in ("涨超", "反攻", "强势", "暴涨", "涨幅")):
        return "科创50收涨，半导体链"

    for kws, label in _GEO_SECTION_MAP:
        if any(kw in blob for kw in kws):
            return label

    if "：" in blob or ":" in blob:
        left = re.split(r"[：:]", blob, maxsplit=1)[0].strip()
        if 4 <= len(left) <= 16:
            return left

    if stock and len(title) > 18:
        short = blob[:16]
        return short if short else stock
    if stock:
        return stock
    for sep in ("，", "。", "；", "、", " "):
        if sep in blob:
            left = blob.split(sep, 1)[0]
            if len(left) >= 6:
                return left[:16]
    return blob[:14] or "当日热点"


def _rank_hotspot_items(
    items: list[dict[str, Any]],
    engagement: dict[str, dict[str, int]],
) -> list[HotspotTopic]:
    ranked: list[tuple[float, dict[str, Any]]] = [
        (_topic_score(item, engagement), item) for item in items
    ]
    ranked.sort(key=lambda x: x[0], reverse=True)
    out: list[HotspotTopic] = []
    seen_titles: set[str] = set()
    for score, item in ranked:
        section = _topic_section_title(item)
        if section in seen_titles:
            continue
        seen_titles.add(section)
        out.append(
            HotspotTopic(
                item=item,
                bucket=_theme_bucket(str(item.get("title") or "")),
                score=score,
                section_title=section,
            )
        )
    return out


def _match_manual_topic(candidates: list[HotspotTopic], hint: str) -> HotspotTopic | None:
    if not hint:
        return None
    needle = hint.strip().lower()
    for topic in candidates:
        blob = f"{topic.item.get('title') or ''} {topic.section_title}".lower()
        if needle in blob:
            return topic
    # 指定选题不在双榜时仍允许成稿（手动/补位）
    title = hint.strip()
    item = {
        "title": title,
        "summary": f"指定热搜选题：{title}",
        "href": f"trend://manual/{title}",
        "attention_score": 800.0,
        "sentiment": "neutral",
        "sources": ["指定选题"],
    }
    return HotspotTopic(
        item=item,
        bucket=_theme_bucket(title),
        score=800.0,
        section_title=title[:16],
    )


def _parse_llm_pick_index(raw: str, *, max_n: int) -> int | None:
    text = (raw or "").strip()
    m = re.search(r"(?:选题|编号|选择)?\s*[=：:]?\s*([1-9]\d*)", text)
    if m:
        idx = int(m.group(1))
        if 1 <= idx <= max_n:
            return idx
    m2 = re.match(r"^([1-9]\d*)", text)
    if m2:
        idx = int(m2.group(1))
        if 1 <= idx <= max_n:
            return idx
    return None


def llm_pick_hotspot_topic(
    candidates: list[HotspotTopic],
    *,
    trade_label: str,
) -> HotspotTopic | None:
    """从 top-N 候选里让 LLM 选 1 条「对 A 股影响最大、最值得深评」的快讯。"""
    if not candidates or not hotspot_llm_pick_enabled() or not is_wechat_mp_llm_configured():
        return None

    briefs: list[str] = []
    for i, topic in enumerate(candidates, 1):
        item = topic.item
        angle = _infer_news_angle(item)
        summary = str(item.get("summary") or item.get("title") or "")[:220]
        briefs.append(
            f"{i}. 标题：{item.get('title') or ''}\n"
            f"   摘要：{summary}\n"
            f"   关联板块线索：{angle.get('sectors') or '—'}\n"
            f"   机器初筛分：{topic.score:.1f}"
        )

    prompt = f"""你是 A 股收盘复盘编辑。数据日：{trade_label}。

从下列 {len(candidates)} 条快讯中，选出 **对 A 股盘面/结构影响最大、最值得写一篇深评的 1 条**。
要求：
- 必须能映射到 A 股具体板块或个股（写清关联链，不限定行业）
- 优先「有产业/政策/业绩实质、且能在当日或次日盘面验证」> 纯情绪标题
- 勿选与 A 股几乎无映射的海外花边

候选：
{chr(10).join(briefs)}

只输出一行，格式严格：选题=N（N 为 1～{len(candidates)} 的整数），理由：一句话40字内。"""

    try:
        raw = call_wechat_mp_llm(
            [
                {
                    "role": "system",
                    "content": "你是资深 A 股编辑，只输出指定格式的一行，不要解释。",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=120,
        )
        idx = _parse_llm_pick_index(raw, max_n=len(candidates))
        if idx is not None:
            return candidates[idx - 1]
    except Exception:
        return None
    return None


def pick_hotspot_candidates(
    items: list[dict[str, Any]] | None = None,
) -> list[HotspotTopic]:
    engagement: dict[str, dict[str, int]] = {}
    if not hotspot_skip_engagement():
        pool_limit, _, _, _ = news_pick_params()
        engagement = fetch_news_engagement(limit=max(pool_limit, 40))
    raw = items if items is not None else _load_hotspot_raw_items(
        limit=max(hotspot_candidate_count() * 3, 15)
    )
    return _rank_hotspot_items(raw, engagement)


def pick_hotspot_topics(
    items: list[dict[str, Any]] | None = None,
    *,
    limit: int | None = None,
    trade_label: str | None = None,
) -> list[HotspotTopic]:
    n = limit if limit is not None else hotspot_topic_count()
    ranked = pick_hotspot_candidates(items)
    if not ranked:
        return []

    ranked = _filter_recently_used_hotspot_topics(ranked)
    if not ranked:
        return []

    candidate_n = max(hotspot_candidate_count(), n)
    candidates = ranked[:candidate_n]

    hint = manual_hotspot_topic_hint()
    if hint:
        manual = _match_manual_topic(ranked, hint)
        if manual:
            return [manual][:n]

    picked: list[HotspotTopic] = []
    if n == 1:
        if hotspot_llm_pick_enabled() and not hotspot_merged_llm():
            label = trade_label or "最近交易日收盘"
            llm_choice = llm_pick_hotspot_topic(candidates, trade_label=label)
            picked.append(llm_choice or candidates[0])
        else:
            picked.append(candidates[0])
        return picked

    used_buckets: set[str] = set()
    for topic in candidates:
        if topic.bucket in used_buckets and topic.bucket != "other":
            continue
        picked.append(topic)
        used_buckets.add(topic.bucket)
        if len(picked) >= n:
            break
    if len(picked) < n:
        for topic in candidates:
            if topic in picked:
                continue
            picked.append(topic)
            if len(picked) >= n:
                break
    return picked[:n]


def _recent_hotspot_title_hooks(*, days: int = 2) -> set[str]:
    """近 days 天已用标题钩子，避免同题连发（含定时三槽 + 手动 hotspot 槽）。"""
    from scripts.tools.wechat_mp_draft_slots import (
        HOTSPOT_SCHEDULE_SLOT_KEYS,
        get_slot_media_id,
    )

    out: set[str] = set()
    slot_keys = (*HOTSPOT_SCHEDULE_SLOT_KEYS, "hotspot")
    for key in slot_keys:
        title = ""
        updated = ""
        try:
            from scripts.tools.wechat_mp_draft_slots import _load_slots

            entry = (_load_slots().get("slots") or {}).get(key) or {}
            title = str(entry.get("title") or "").strip()
            updated = str(entry.get("updated_at") or "").strip()
        except Exception:
            continue
        if not title:
            continue
        try:
            ts = datetime.fromisoformat(updated)
            if (datetime.now(TZ) - ts).total_seconds() > days * 86400:
                continue
        except ValueError:
            pass
        hook = title
        if "｜" in hook:
            hook = hook.split("｜", 1)[1]
        for suffix in _HOTSPOT_TITLE_SUFFIXES + _HOTSPOT_TITLE_SUFFIXES_NO_A:
            if hook.endswith(suffix):
                hook = hook[: -len(suffix)]
                break
        hook = re.sub(r"\s+", "", hook)
        if hook:
            out.add(hook)
        out.add(re.sub(r"\s+", "", title))
    return out


def _filter_recently_used_hotspot_topics(
    ranked: list[HotspotTopic],
) -> list[HotspotTopic]:
    used = _recent_hotspot_title_hooks(days=2)
    if not used:
        return ranked
    kept: list[HotspotTopic] = []
    for topic in ranked:
        section = re.sub(r"\s+", "", topic.section_title or "")
        src = re.sub(r"\s+", "", str(topic.item.get("title") or ""))
        if any(u and (u in section or u in src or section in u) for u in used):
            continue
        kept.append(topic)
    return kept or ranked


def resolve_hotspot_trade_date() -> date:
    """hotspot 盘面锚点：最近 A 股交易日（不绑选股库 stale 日）。"""
    from stock_ai.trading_calendar import latest_a_share_trade_date

    return latest_a_share_trade_date()


def format_hotspot_trade_label(td: date, *, edition: str | None = "close") -> str:
    from scripts.tools.wechat_mp_market_edition import normalize_market_edition

    ed = normalize_market_edition(edition)
    if hotspot_source() == "trends":
        suffix = {"pre": "早间", "midday": "午间", "close": "晚间"}.get(ed, "")
        return f"{td.month}月{td.day}日{suffix}"
    suffix = {"pre": "盘前", "midday": "午间", "close": "收盘"}.get(ed, "收盘")
    return f"{td.month}月{td.day}日{suffix}"


def _stock_lines(item: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    name = str(item.get("matched_stock_name") or "").strip()
    code = str(item.get("matched_stock_code") or "").strip().zfill(6)
    if name and code:
        chg = float(item.get("matched_stock_change_pct") or 0.0)
        rank = int(item.get("matched_stock_rank") or 0)
        lines.append(f"{name}（{code}）人气第{rank}位，收盘约{chg:+.1f}%")
    angle = _infer_news_angle(item)
    for part in str(angle.get("sectors") or "").split("、")[:3]:
        part = part.strip()
        if part and part not in lines:
            lines.append(part)
    return lines[:4]


def _build_context_blob(
    topics: list[HotspotTopic],
    *,
    trade_label: str,
    edition: str | None = "close",
    candidates: list[HotspotTopic] | None = None,
) -> str:
    if hotspot_source() == "trends":
        parts = [f"【刊发时段】{trade_label}。", ""]
    else:
        parts = [
            f"【数据日】{trade_label}。正文须写清该数据日，禁止用「今日」指代行情日。",
            "",
        ]
    if hotspot_source() == "trends":
        parts.extend(
            [
                "【选题来源】微博热搜 + 百度热搜（双榜交叉，优先社会案/文娱/职场民生）。",
                "本篇只深拆 **1 个**热搜主题，写清人物+事件+多方观点；**禁止**股市盘面、指数涨跌、个股涨跌幅。",
                "",
            ]
        )
    else:
        parts.extend(
            [
                "【evening 同批分工】news 头条已是 10 条快讯清单；本篇禁止再写快讯列表，"
                "只深拆 **1 个**当日最值得写的主题。",
                "",
            ]
        )
    if hotspot_source() != "trends":
        primary_ctx = ""
        if topics:
            primary_ctx = str(topics[0].item.get("market_context") or "").strip()
        parts.extend(["【指数简况（正文最多引用一次，勿复读）】"])
        if primary_ctx:
            parts.append(primary_ctx)
        else:
            try:
                from scripts.tools.daily_briefing_report import fetch_market_indices

                idx_lines = [
                    ln
                    for ln in fetch_market_indices()[:3]
                    if ln and "获取失败" not in ln and "为空" not in ln
                ]
                parts.append(idx_lines[0] if idx_lines else "（指数暂不可用）")
            except Exception:
                parts.append("（指数暂不可用）")

    pool = candidates if candidates else topics
    if candidates and hotspot_merged_llm():
        label = "热搜" if hotspot_source() == "trends" else "快讯"
        parts.extend(["", f"【候选{label} Top{len(candidates)}（须从中选 1 条写深评）】"])
        for i, topic in enumerate(candidates, 1):
            item = topic.item
            angle = _infer_news_angle(item)
            parts.append(
                f"{i}. {item.get('title') or ''}｜{str(item.get('summary') or '')[:120]}"
                f"｜板块线索：{angle.get('sectors') or '—'}"
            )
        parts.append(
            "定题规则（仅 Agent 内部，**正文禁止复述**）：选对 A 股映射最大的一条写深评。"
        )

    topic = topics[0]
    item = topic.item
    tag = sentiment_label(str(item.get("sentiment") or "neutral"))
    angle = _infer_news_angle(item)
    if not (candidates and hotspot_merged_llm()):
        parts.extend(
            [
                "",
                f"【本篇唯一主题 · {topic.section_title}】",
                f"标题：{item.get('title') or ''}",
                f"摘要：{item.get('summary') or item.get('title') or ''}",
                f"舆情标签：{tag}；主题桶：{topic.bucket}；初筛分：{topic.score:.1f}",
                f"关联板块线索：{angle.get('sectors') or ''}",
                f"验证点：{angle.get('watch') or ''}",
            ]
        )
        if hotspot_source() != "trends":
            parts.extend(
                [
                    "关联个股/样本：",
                    *(
                        _stock_lines(item)
                        or ["（上下文无列名样本：只写板块/指数现象，禁止写数据未获取）"]
                    ),
                ]
            )
    research_blob = str(item.get("web_research_blob") or "").strip()
    if research_blob:
        parts.extend(["", research_blob])

    try:
        from scripts.tools.wechat_mp_market_edition import build_market_news_context, normalize_market_edition

        if os.getenv("WECHAT_MP_HOTSPOT_FULL_MARKET_CTX", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }:
            blob, _ = build_market_news_context(normalize_market_edition(edition))
            parts.extend(["", blob])
    except Exception:
        pass
    return "\n".join(parts)


def _filter_research_hits(hits: list[Any], title: str) -> list[Any]:
    """优先保留与热搜同题的参考报道，减少跑题摘句。"""
    from scripts.tools.wechat_mp_hotspot_research import ResearchHit

    if not hits:
        return hits
    keys = {
        k
        for k in re.findall(r"[\u4e00-\u9fff]{2,}", title)
        if len(k) >= 2 and k not in {"今日", "市场", "数据", "消息", "报道"}
    }
    if not keys:
        return hits

    def score(hit: ResearchHit) -> float:
        blob = f"{hit.title}{hit.snippet}"
        return float(sum(1 for k in keys if k in blob))

    ranked = sorted(hits, key=score, reverse=True)
    good = [h for h in ranked if score(h) >= 2]
    return good[:6] if good else ranked[:5]


def _is_finance_trend_item(item: dict[str, Any]) -> bool:
    """财经向热搜走东财取材 + 财经深评 prompt（skill: hotspot-deep-review）。"""
    if item.get("prefer_stock"):
        return True
    title = str(item.get("title") or "")
    markers = (
        "A股", "涨停", "跌停", "市值", "沪指", "创业板", "科创", "板块",
        "龙头", "大涨", "收跌", "收盘", "个股", "券商", "半导体", "芯片",
    )
    return any(m in title for m in markers)


def _attach_hotspot_research(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or "").strip()
    out = dict(item)
    if hotspot_source() == "trends" and not _is_finance_trend_item(item):
        from scripts.tools.wechat_mp_discussion_research import (
            fetch_discussion_research,
            format_discussion_imitation_block,
            format_discussion_research_bundle,
        )

        slug = re.sub(r"[^\w\-]+", "-", title[:28]).strip("-").lower() or "hotspot"
        seed_urls: list[str] = []
        for key in ("href", "url"):
            u = str(item.get(key) or "").strip()
            if u.startswith("http") and u not in seed_urls:
                seed_urls.append(u)
        topic_dict = {
            "trend_title": title,
            "title_zh": title,
            "cover_slug": slug,
            "from_trend": True,
            "research_urls": seed_urls,
        }
        hits = fetch_discussion_research(topic_dict)
        out["web_research"] = [
            {
                "title": h.title,
                "snippet": h.snippet,
                "source": h.source,
                "url": h.url,
                "published": h.published,
            }
            for h in hits
        ]
        bundle = format_discussion_research_bundle(topic_dict, hits)
        refs = format_discussion_imitation_block(hits)
        out["web_research_blob"] = "\n\n".join(x for x in (bundle, refs) if x).strip()
        out["web_reference_block"] = refs
        return out

    from scripts.tools.wechat_mp_hotspot_research import (
        fetch_hotspot_research,
        format_hotspot_reference_imitation_block,
        format_hotspot_research_block,
    )

    hits = _filter_research_hits(fetch_hotspot_research(title), title)
    out["web_research"] = [
        {
            "title": h.title,
            "snippet": h.snippet,
            "source": h.source,
            "url": h.url,
            "published": h.published,
        }
        for h in hits
    ]
    facts = format_hotspot_research_block(hits)
    refs = format_hotspot_reference_imitation_block(hits)
    out["web_research_blob"] = "\n\n".join(x for x in (facts, refs) if x).strip()
    out["web_reference_block"] = refs
    return out


def _hotspot_imitate_rewrite_enabled() -> bool:
    raw = (os.getenv("WECHAT_MP_HOTSPOT_IMITATE_REWRITE") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _hotspot_llm_max_attempts() -> int:
    return max(1, _env_int("WECHAT_MP_HOTSPOT_MAX_ATTEMPTS", 1))


def _rewrite_trends_hotspot_against_references(
    body: str,
    *,
    reference_block: str,
) -> str:
    if not reference_block or not is_wechat_mp_llm_configured():
        return body
    prompt = f"""对照【参考文章】的写法，重写下面这篇社会热点深评初稿。

要求：
- 学参考稿：首句直接写人物+事实，删掉「值得注意的是」「热搜在聊」等套话
- 每段 2～4 句；保留正确事实，可补参考稿里有、初稿缺的可核对细节
- 纯段落，禁止小标题；禁止股市盘面、指数、涨跌幅、个股
- {HOTSPOT_MIN_BODY_CHARS}字以上；禁止编造

【参考文章】
{reference_block}

【初稿】
{body}

只输出重写后的正文。"""
    try:
        raw = call_wechat_mp_llm(
            [
                {
                    "role": "system",
                    "content": "仿写社会新闻报道，口语但有细节。只输出正文。",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=3400,
        )
        out = _polish_hotspot_llm_body(raw)
        if len(out) >= max(1500, int(len(body) * 0.7)):
            return out
    except Exception:
        pass
    return body


def _rewrite_hotspot_against_references(
    body: str,
    *,
    reference_block: str,
    trade_label: str,
) -> str:
    if not reference_block or not is_wechat_mp_llm_configured():
        return body
    prompt = f"""你是财经公众号编辑。对照【参考文章】的写法，重写下面的热点深评初稿。

要求：
- 学参考稿开头：直接写事实和数字，删掉「公开报道」「值得先记住」「盘面一句」「热搜在聊」等 AI 套话
- 每段 2～4 句、不超过 150 字；段间空一行
- 删掉空话、套话；保留正确事实
- 纯段落，禁止小标题；指数涨跌最多 1 次（{trade_label}）
- 2000字以上；禁止编造数字

【参考文章】
{reference_block}

【初稿】
{body}

只输出重写后的正文 Markdown，不要解释。"""
    try:
        raw = call_wechat_mp_llm(
            [
                {
                    "role": "system",
                    "content": "仿写财经媒体报道，信息密度高，像人写的评论。只输出正文。",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=3400,
        )
        out = _polish_hotspot_llm_body(raw)
        if len(out) >= max(1500, int(len(body) * 0.7)):
            return out
    except Exception:
        pass
    return body


def _extract_topic_section_from_body(body: str) -> str | None:
    """从成稿中解析第一个内容型 `> ` 小标题。"""
    banned = set(HOTSPOT_BANNED_SECTION_TITLES)
    for line in body.splitlines():
        if not line.strip().startswith("> "):
            continue
        bare = line.strip().lstrip("> ").strip()
        if bare in banned or len(bare) < 4:
            continue
        return bare
    return None


def _resolve_topic_after_body(
    body: str,
    candidates: list[HotspotTopic],
    fallback: HotspotTopic,
) -> HotspotTopic:
    chosen = _extract_topic_section_from_body(body)
    for topic in candidates:
        title = str(topic.item.get("title") or "")
        if chosen and (topic.section_title == chosen or chosen in title or title.startswith(chosen[:6])):
            return HotspotTopic(
                item=topic.item,
                bucket=topic.bucket,
                score=topic.score,
                section_title=chosen or topic.section_title,
            )
    best: HotspotTopic | None = None
    best_len = 0
    for topic in candidates:
        title = str(topic.item.get("title") or "")
        if title and title in body and len(title) > best_len:
            best = topic
            best_len = len(title)
    if best:
        return HotspotTopic(
            item=best.item,
            bucket=best.bucket,
            score=best.score,
            section_title=chosen or best.section_title,
        )
    if chosen:
        return HotspotTopic(
            item=fallback.item,
            bucket=fallback.bucket,
            score=fallback.score,
            section_title=chosen,
        )
    return fallback


def _fetch_index_snippet(*, max_chars: int = 220) -> str:
    try:
        from scripts.tools.daily_briefing_report import fetch_market_indices

        lines = [
            ln
            for ln in fetch_market_indices()[:6]
            if ln and "获取失败" not in ln and "为空" not in ln
        ]
        blob = "；".join(lines)
        return blob[:max_chars]
    except Exception:
        return ""


def _paragraph_count(text: str) -> int:
    return len([p for p in re.split(r"\n\n+", text or "") if len(p.strip()) >= 40])


def _hotspot_extension_paragraphs(
    topic: HotspotTopic,
    *,
    trade_label: str,
    watch: str,
    chain_hint: str,
    sectors: str,
) -> tuple[str, ...]:
    title_raw = str(topic.item.get("title") or topic.section_title).strip()[:24]
    return (
        (
            f"若把{trade_label}拆成两层：热搜带来的叙事溢价，和{chain_hint}在{sectors}里的真实成交。"
            f"两层叠在一起时，容易出现「讨论很热、持仓很虚」——尾盘偷袭、早盘兑现都算典型信号。"
            f"别用榜单位次代替量价证据；{watch}才是次日最先能核对的东西。"
        ),
        (
            f"资金类型也要分开看：游资脉冲和机构配置不是同一套节奏。"
            f"{chain_hint}若由前者主导，日内振幅往往大于趋势斜率；后者参与则更像沿均线逐级抬升。"
            f"收盘截图区分不了这两种力量，只能等首小时：放量站不稳均价，多半是情绪单在撤退。"
        ),
        (
            f"把「{title_raw}」这类话题放到全市场仓位结构里，它往往扮演的是分流器而不是发动机："
            f"高位题材退潮时，资金需要新故事承接，热搜恰好提供了叙事入口。"
            f"入口不等于出口——能不能走成两三天行情，仍取决于龙头能否把分歧收成共识。"
        ),
        (
            f"{trade_label}还有一个容易被忽略的变量：外盘与人民币汇率的日内波动，"
            f"会改变外资对{chain_hint}的风险定价。若外盘同向、内盘背离，更像是内需主导；"
            f"若内外盘同涨同跌，叙事更容易被当成全球共振。对照北向与期指升贴水，"
            f"能把「热搜故事」和「资金故事」分开。"
        ),
        (
            f"最后落到可执行的观察：盘面数字是否还在、龙头愿不愿意领跌领涨、舆论是否开始自我修正。"
            f"任一环节断了，把{chain_hint}当插曲即可；三个环节接上，才值得在复盘笔记里跟踪两三天。"
        ),
        (
            f"对上班族投资者来说，这类热搜最大的价值不是「买不买」，而是把次日开盘前该看什么写清楚："
            f"竞价量能、龙头分时、同主题第二梯队是否出现。"
            f"清单短一点没关系，关键是可核对——核对不过，就说明故事还停在评论区，没有进入成交。"
            f"第二遍热搜往往卖给后知后觉的人，盘面若已兑现，复述再多也难改变仓位。"
        ),
    )


def _ensure_hotspot_min_length(
    body: str,
    topic: HotspotTopic,
    *,
    trade_label: str,
) -> str:
    text = (body or "").strip()
    if len(text) >= HOTSPOT_MIN_BODY_CHARS:
        return text
    item = topic.item
    angle = _infer_news_angle(item)
    sectors = str(angle.get("sectors") or topic.section_title)
    watch = str(angle.get("watch") or "龙头竞价与首小时量价")
    chain_hint = sectors.split("、")[0].split("（")[0].strip() or topic.section_title
    for para in _hotspot_extension_paragraphs(
        topic,
        trade_label=trade_label,
        watch=watch,
        chain_hint=chain_hint,
        sectors=sectors,
    ):
        if len(text) >= HOTSPOT_MIN_BODY_CHARS:
            break
        chunk = para.strip()
        if chunk and chunk not in text:
            text = f"{text.rstrip()}\n\n{chunk}"
    if len(text) < HOTSPOT_MIN_BODY_CHARS:
        tail = (
            f"如果你只在热搜里读完这条线，很容易高估次日波动；"
            f"把{watch}写进备忘录，开盘对照一次，比多刷几遍评论更有用。"
        )
        if tail not in text:
            text = f"{text.rstrip()}\n\n{tail}"
    return text


def _polish_hotspot_llm_body(raw: str) -> str:
    from scripts.tools.wechat_mp_hotspot_polish import (
        delist_hotspot_body,
        reflow_hotspot_body,
        reflow_hotspot_layout,
        sanitize_hotspot_reader_meta,
    )
    from scripts.tools.wechat_mp_prose import strip_hotspot_meta_commentary

    body = _sanitize_news_reader_meta((raw or "").strip())
    body = sanitize_hotspot_reader_meta(body)
    body = reflow_hotspot_body(body)
    body = strip_hotspot_subheadings(
        humanize_hotspot_boilerplate(humanize_hotspot_field_labels(body))
    )
    body = strip_hotspot_meta_commentary(body)
    body = delist_hotspot_body(body)
    return reflow_hotspot_layout(body)


def _hotspot_body_reject_reasons(
    body: str, *, bucket: str, min_chars: int | None = None
) -> list[str]:
    from scripts.tools.wechat_mp_prose import strip_hotspot_meta_commentary

    floor = min_chars if min_chars is not None else HOTSPOT_MIN_BODY_CHARS
    text = strip_hotspot_meta_commentary(
        humanize_hotspot_boilerplate(humanize_hotspot_field_labels((body or "").strip()))
    )
    reasons: list[str] = []
    if len(text) < floor:
        reasons.append(f"字数{len(text)}<{floor}")
    paras = _paragraph_count(text)
    if paras < 5:
        reasons.append(f"段落{paras}<5")
    if re.search(r"^>\s", text, flags=re.MULTILINE):
        reasons.append("含blockquote小标题")
    if re.search(r"^#+\s", text, flags=re.MULTILINE):
        reasons.append("含markdown标题")
    if any(title in text for title in HOTSPOT_BANNED_SECTION_TITLES):
        reasons.append("含禁节名")
    if any(label.rstrip("：:") in text for label in HOTSPOT_RIGID_FIELD_LABELS):
        reasons.append("含刚性字段标签")
    hit_phrase = next((p for p in HOTSPOT_BOILERPLATE_PHRASES if p in text), "")
    if hit_phrase:
        reasons.append(f"含套话:{hit_phrase[:12]}")
    if not re.search(r"\d", text):
        reasons.append("无数字")
    if bucket != "geo" and any(kw in text for kw in _GEO_OIL_KEYWORDS):
        reasons.append("含地缘油价套话")
    return reasons


def validate_codex_hotspot_body(body: str, *, topic: str) -> str:
    """清洗 Codex 成稿并复用热点正文硬门禁；失败时不做生成兜底。"""

    polished = _polish_hotspot_llm_body(body)
    reasons = _hotspot_body_reject_reasons(
        polished,
        bucket=_theme_bucket(topic),
    )
    if reasons:
        raise ValueError(f"Codex 热点正文未通过质量门禁：{'、'.join(reasons)}")
    return polished


def _hotspot_body_usable(
    body: str, *, bucket: str, min_chars: int | None = None
) -> bool:
    from scripts.tools.wechat_mp_prose import strip_hotspot_meta_commentary

    floor = min_chars if min_chars is not None else HOTSPOT_MIN_BODY_CHARS
    text = strip_hotspot_meta_commentary(
        humanize_hotspot_boilerplate(humanize_hotspot_field_labels((body or "").strip()))
    )
    if len(text) < floor:
        return False
    if _paragraph_count(text) < 5:
        return False
    if re.search(r"^>\s", text, flags=re.MULTILINE):
        return False
    if re.search(r"^#+\s", text, flags=re.MULTILINE):
        return False
    if any(title in text for title in HOTSPOT_BANNED_SECTION_TITLES):
        return False
    if any(label.rstrip("：:") in text for label in HOTSPOT_RIGID_FIELD_LABELS):
        return False
    if any(phrase in text for phrase in HOTSPOT_BOILERPLATE_PHRASES):
        return False
    if not re.search(r"\d", text):
        return False
    if bucket != "geo" and any(kw in text for kw in _GEO_OIL_KEYWORDS):
        return False
    return True


def _template_hotspot_body(
    topics: list[HotspotTopic],
    *,
    trade_label: str,
) -> str:
    from scripts.tools.wechat_mp_hotspot_polish import (
        delist_hotspot_body,
        reflow_hotspot_layout,
    )
    from scripts.tools.wechat_mp_prose import strip_hotspot_meta_commentary

    topic = topics[0]
    item = topic.item
    title_raw = str(item.get("title") or topic.section_title).strip()
    sentences: list[str] = []
    for row in list(item.get("web_research") or [])[:8]:
        snip = str(row.get("snippet") or row.get("title") or "").strip()
        for part in re.split(r"(?<=[。！？])", snip):
            part = part.strip()
            if len(part) >= 10:
                sentences.append(part)

    paragraphs: list[str] = []
    if hotspot_source() == "trends":
        if sentences:
            paragraphs.append(sentences[0].rstrip("。") + "。")
            for sent in sentences[1:12]:
                line = sent if sent.endswith(("。", "！", "？")) else sent + "。"
                paragraphs.append(line)
        else:
            paragraphs.append(f"{title_raw}。")
        body = strip_hotspot_meta_commentary("\n\n".join(paragraphs))
        body = delist_hotspot_body(body)
        return reflow_hotspot_layout(body)

    angle = _infer_news_angle(item)
    watch = str(angle.get("watch") or "龙头竞价与首小时量价")
    index_snippet = str(item.get("market_context") or "") or _fetch_index_snippet(max_chars=120)
    idx_line = index_snippet.split("；")[0] if index_snippet else ""

    sentences: list[str] = []
    for row in list(item.get("web_research") or [])[:6]:
        snip = str(row.get("snippet") or row.get("title") or "").strip()
        for part in re.split(r"(?<=[。！？])", snip):
            part = part.strip()
            if len(part) >= 10:
                sentences.append(part)

    paragraphs: list[str] = []
    if sentences:
        lead = sentences[0].rstrip("。")
        open_para = f"{trade_label}，{lead}。"
        if idx_line and idx_line not in open_para and len(paragraphs) == 0:
            if "指数" in idx_line or "沪指" in idx_line or "上证" in idx_line:
                open_para = open_para.rstrip("。") + f"。{idx_line}。"
        paragraphs.append(open_para)
        for sent in sentences[1:8]:
            line = sent if sent.endswith(("。", "！", "？")) else sent + "。"
            if line not in paragraphs[-1]:
                paragraphs.append(line)
    else:
        paragraphs.append(f"{trade_label}，{title_raw}。")
        if idx_line:
            paragraphs.append(idx_line + "。")

    stock_lines = _stock_lines(item)
    if stock_lines and stock_lines[0]:
        paragraphs.append(stock_lines[0] + "。")

    paragraphs.append(
        f"次日重点看{watch}——竞价量能和首小时分时，比热搜排名更接近盘面验证。"
    )

    body = strip_hotspot_meta_commentary("\n\n".join(paragraphs))
    body = delist_hotspot_body(body)
    body = reflow_hotspot_layout(body)
    if len(body) < HOTSPOT_MIN_BODY_CHARS and len(sentences) > 8:
        extra = "\n\n".join(
            s if s.endswith(("。", "！", "？")) else s + "。"
            for s in sentences[8:14]
        )
        body = reflow_hotspot_layout(f"{body}\n\n{extra}")
    return body


def _generate_trends_hotspot_body(
    topics: list[HotspotTopic],
    *,
    trade_label: str,
    edition: str | None = "close",
) -> tuple[str, list[HotspotTopic], str]:
    """微博/百度热搜 → 社会热点深评（非股市快评）。"""
    from scripts.tools.wechat_mp_hotspot_polish import (
        dedupe_hotspot_index_mentions,
        delist_hotspot_body,
    )
    from scripts.tools.wechat_mp_report_voice import scan_report_voice
    from scripts.tools.wechat_mp_tv_review_article import _discussion_voice_prompt_block

    topic = topics[0]
    title = str(topic.item.get("title") or topic.section_title).strip()
    ref_block = str(topic.item.get("web_reference_block") or "").strip()
    gate_min = hotspot_min_body_gate(social=True)
    context = _build_context_blob(
        topics, trade_label=trade_label, edition=edition
    )

    prompt = f"""为微信公众号「牛马也智能」写一篇**社会热点深评**（单主题纯段落长文）。

{context}

## 写作要求
- **必须写满 {HOTSPOT_MIN_BODY_CHARS}～2800 汉字**（首稿即达标，勿写短稿）；6～9 段，纯段落
- **仅使用【联网事实】【参考文章】中已出现的信息**；禁止编造群聊截图、使馆介入、赔偿金额、等待时长等素材未写明的细节
- 先读【参考文章·仿写】再写；禁止整段照搬
- 首段：谁+在哪+发生了什么（与标题同题）；禁止「刷到热搜」「值得注意的是」
- 中段：可核对细节、通报与民间说法、多方观点
- 末段：一句后续观察或问句；禁止股市/A股/指数/涨跌幅/个股
- 禁止买卖建议、禁止 emoji、禁止 markdown 标题

{_discussion_voice_prompt_block()}

只输出正文。"""

    def _draft_once(extra_user: str = "") -> str:
        user_prompt = prompt + (f"\n\n{extra_user}" if extra_user else "")
        raw = call_wechat_mp_llm(
            [
                {
                    "role": "system",
                    "content": (
                        "你是读者转述者，写社会热点深评：口语、有细节、像人写的评论。"
                        "只输出正文；事实须来自【联网事实】，禁止编造。"
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=3400,
            temperature=0.55,
        )
        return delist_hotspot_body(
            dedupe_hotspot_index_mentions(_polish_hotspot_llm_body(raw))
        )

    if not is_wechat_mp_llm_configured():
        return _template_hotspot_body(topics, trade_label=trade_label), topics, trade_label

    try:
        allow_voice = os.getenv(
            "WECHAT_MP_DISCUSSION_ALLOW_REPORT_VOICE", ""
        ).strip().lower() in {"1", "true", "yes"} or os.getenv(
            "WECHAT_MP_HOTSPOT_ALLOW_REPORT_VOICE", ""
        ).strip().lower() in {"1", "true", "yes"}
        body = ""
        voice_fixed = False
        for attempt in range(_hotspot_llm_max_attempts()):
            extra = ""
            if attempt > 0:
                if not voice_fixed:
                    voice_hits = scan_report_voice(body)
                    if voice_hits and not allow_voice:
                        labels = "、".join(h[0] for h in voice_hits[:6])
                        extra = (
                            f"【重写】删除分析报告腔（{labels}），改成像朋友转述热搜的口语评论。"
                            f"写满 {gate_min} 字，事实仅来自【联网事实】。"
                        )
                        voice_fixed = True
                    else:
                        voice_fixed = True
                if not extra:
                    extra = (
                        f"【扩写】上一稿约 {len(body)} 字，未达标。"
                        f"必须写满 {gate_min} 字、6～9 段纯段落；"
                        f"把【联网事实】每条展开成议论，事实仅来自素材，禁止编造。"
                    )
            body = _draft_once(extra)
            if (
                ref_block
                and _hotspot_imitate_rewrite_enabled()
                and attempt <= 1
            ):
                rewritten = _rewrite_trends_hotspot_against_references(
                    body, reference_block=ref_block
                )
                if len(rewritten) >= max(1500, int(len(body) * 0.85)):
                    body = rewritten
            if _hotspot_body_usable(body, bucket=topic.bucket, min_chars=gate_min):
                return body, topics, trade_label
        raise RuntimeError(
            f"热点深评成稿未达 {gate_min} 字（社会热点）：{title}；"
            f"末稿约 {len(body)} 字；"
            f"未过：{'、'.join(_hotspot_body_reject_reasons(body, bucket=topic.bucket, min_chars=gate_min)) or '未知'}"
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"热点深评 LLM 成稿失败：{title}；{exc}") from exc


def generate_hotspot_body(
    *,
    now: datetime | None = None,
    edition: str | None = "close",
) -> tuple[str, list[HotspotTopic], str]:
    now = now or datetime.now(TZ)
    td = resolve_hotspot_trade_date()
    trade_label = format_hotspot_trade_label(td, edition=edition)
    candidates = pick_hotspot_candidates()
    if not candidates:
        if hotspot_source() == "trends":
            raise RuntimeError(
                "热点深评：微博/百度热搜抓取失败或为空，请检查网络或稍后重试"
            )
        raise RuntimeError("热点深评：无可用快讯/热股素材，请先 sync_macro_news 或检查 OpenCLI")
    topics = pick_hotspot_topics(trade_label=trade_label)
    if not topics:
        topics = [candidates[0]]

    topic = topics[0]
    topic = HotspotTopic(
        item=_attach_hotspot_research(topic.item),
        bucket=topic.bucket,
        score=topic.score,
        section_title=topic.section_title,
    )
    topics = [topic]
    if hotspot_source() == "trends" and not _is_finance_trend_item(topic.item):
        return _generate_trends_hotspot_body(
            topics, trade_label=trade_label, edition=edition
        )

    candidate_pool = candidates[: hotspot_candidate_count()]
    merged = hotspot_merged_llm()
    if topic.bucket in {"policy_rescue", "session_theme"}:
        merged = False
    context = _build_context_blob(
        topics,
        trade_label=trade_label,
        edition=edition,
        candidates=candidate_pool if merged else None,
    )

    if not is_wechat_mp_llm_configured():
        return _template_hotspot_body(topics, trade_label=trade_label), topics, trade_label

    banned = "、".join(_AI_COMMENT_BANNED[:10])
    pick_rule = ""
    if merged:
        pick_rule = (
            f"0a. 从【候选快讯 Top{len(candidate_pool)}】中**内部**选定 1 条写深评（读者不可见候选过程）。"
            f"{HOTSPOT_CONTEXT_RULE}"
        )
    prompt = f"""你是一位财经媒体记者，为公众号写「热点深评」（**单主题**快评长文，非快讯清单）。
{PUBLIC_MP_WRITER_RULE}
{HOTSPOT_RESEARCHER_VOICE_RULE}
{PLATFORM_PROPERTY_RISK_RULE}

{context}

## 写作要求
0. 全文 **{HOTSPOT_MIN_BODY_CHARS}～2800 字**。{HOTSPOT_READER_META_RULE}
{pick_rule}
1. **先读【参考文章·仿写】**，按财经媒体报道的节奏写：事实→个股/板块→怎么验证；禁止研报模板腔。
2. 全文 **纯段落**，6～9 段，禁止一切小标题。
3. 必须写入参考稿中的至少 4 个具体事实（公司名、涨跌幅、只数、时间）；禁止空泛复述热搜标题。
4. **指数涨跌全文最多 1 次**；后文只写个股、板块、资金。
5. {HOTSPOT_CONTEXT_RULE} {HOTSPOT_READER_DATA_RULE}
6. 禁止买卖建议；禁止 emoji；禁止 markdown 标题
7. 禁止套话：{banned} 等
8. 只使用上下文与参考报道中的事实，勿编造数字
{monetization_prompt_block("hotspot")}"""

    system_msg = (
        "仿写中国证券报/证券时报类财经快评：首句报事实+数字，中段列公司，末段一句观察。"
        "2000字以上纯段落，禁止小标题与空话。只输出正文 Markdown。"
    )
    try:
        raw = call_wechat_mp_llm(
            [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            max_tokens=5200,
        )
        body = _polish_hotspot_llm_body(raw)
        body = re.sub(r"\bdomestic\b", "国内", body, flags=re.IGNORECASE)
        if not _hotspot_body_usable(body, bucket=topic.bucket) and len(body) >= 1500:
            expand_prompt = (
                f"{prompt}\n\n"
                f"【扩写】上一稿仅约 {len(body)} 字，不合格。"
                f"请补充【联网参考】里尚未写入的具体事实（公司名、涨跌幅、政策细节），"
                f"不要增加小标题，不要重复指数涨跌，不要重复同义句。"
            )
            raw2 = call_wechat_mp_llm(
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": expand_prompt},
                ],
                max_tokens=5200,
            )
            body2 = _polish_hotspot_llm_body(raw2)
            body2 = re.sub(r"\bdomestic\b", "国内", body2, flags=re.IGNORECASE)
            if len(body2) > len(body):
                body = body2
        ref_block = str(topic.item.get("web_reference_block") or "").strip()
        if _hotspot_imitate_rewrite_enabled() and ref_block:
            body = _rewrite_hotspot_against_references(
                body,
                reference_block=ref_block,
                trade_label=trade_label,
            )
        from scripts.tools.wechat_mp_hotspot_polish import (
            dedupe_hotspot_index_mentions,
            delist_hotspot_body,
        )

        body = delist_hotspot_body(body)
        body = dedupe_hotspot_index_mentions(body)
        if _hotspot_body_usable(body, bucket=topic.bucket):
            if merged:
                topic = _resolve_topic_after_body(body, candidate_pool, topic)
                topics = [topic]
            return body, topics, trade_label
    except Exception:
        pass
    return _template_hotspot_body(topics, trade_label=trade_label), topics, trade_label


_HOTSPOT_TITLE_PREFIX = ""
_WECHAT_TITLE_MAX = 32

_TITLE_HOOK_COMPRESS: tuple[tuple[str, str], ...] = (
    (r"从中东返回法国", "返港"),
    (r"从中东返港", "返港"),
    (r"从中东返回", "返港"),
    (r"返回法国", "返法"),
    (r"暂时关闭", "暂闭"),
)

_INCOMPLETE_HOOK_TAIL = frozenset("返从在与和在对向至及将被把")


def _compress_title_hook(text: str) -> str:
    out = re.sub(r"\s+", "", (text or "").strip())
    for pattern, repl in _TITLE_HOOK_COMPRESS:
        out = re.sub(pattern, repl, out)
    return out


def _title_hook(text: str, *, max_len: int = 10) -> str:
    """标题钩子：先压缩冗语，再截断；禁止「从中东返…」类半句话与冒号后硬切。"""
    cleaned = _compress_title_hook(text)
    # 带冒号的通稿标题：优先取冒号前主体（「以色列国防部长：…」→「以色列国防部长」）
    if "：" in cleaned or ":" in cleaned:
        left = re.split(r"[：:]", cleaned, maxsplit=1)[0].strip()
        if len(left) >= 4:
            cleaned = left
    if len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[:max_len]
    for sep in ("，", ",", "、", "；", ";"):
        if sep in cut:
            left = cut.rsplit(sep, 1)[0]
            if len(left) >= 6:
                cut = left
                break
    cut = cut.rstrip("，,、")
    while cut and cut[-1] in _INCOMPLETE_HOOK_TAIL and len(cut) > 1:
        cut = cut[:-1]
    cut = cut.rstrip("，,、")
    if len(cleaned) > len(cut) and len(cut) >= max_len - 1:
        cut += "…"
    return cut


_HOTSPOT_TITLE_SUFFIXES_NO_A: tuple[str, ...] = (
    "会怎么走？",
    "该关注啥？",
    "影响大吗？",
    "该怎么看？",
    "意味着啥？",
    "有关系吗？",
    "有啥影响？",
    "怎么映射？",
)


def _hotspot_title_suffix_pool(hook: str) -> tuple[str, ...]:
    """钩子已含「A股」时，后缀不再重复 A股。"""
    if "A股" in (hook or ""):
        return _HOTSPOT_TITLE_SUFFIXES_NO_A
    return _HOTSPOT_TITLE_SUFFIXES


_HOTSPOT_TITLE_SUFFIXES: tuple[str, ...] = (
    "对A股有什么影响？",
    "对A股有啥影响？",
    "A股会怎么走？",
    "跟A股有啥关系？",
    "对A股影响大吗？",
    "A股该关注啥？",
    "对A股重要吗？",
    "A股该怎么看？",
    "对A股意味着啥？",
    "和A股有关系吗？",
)

_HOTSPOT_STOCK_SUFFIXES: tuple[str, ...] = (
    "会受影响吗？",
    "跟这事啥关系？",
    "该盯吗？",
    "怎么映射？",
    "有啥关系？",
)


def _pick_hotspot_suffix(hook: str, pool: tuple[str, ...]) -> str:
    import hashlib

    pick = int(hashlib.sha1(hook.encode()).hexdigest(), 16) % len(pool)
    return pool[pick]


def _hotspot_hook_budget(*, with_stock: bool, stock: str = "", hook: str = "") -> int:
    if with_stock:
        max_stock_suffix = max(len(s) for s in _HOTSPOT_STOCK_SUFFIXES)
        fixed = len(stock) + len("：") + max_stock_suffix
    else:
        suffix_pool = _hotspot_title_suffix_pool(hook)
        max_suffix = max(len(s) for s in suffix_pool)
        fixed = len(_HOTSPOT_TITLE_PREFIX) + max_suffix
    return max(8, _WECHAT_TITLE_MAX - fixed)


def _research_hits_from_topic(topic: HotspotTopic) -> list[Any]:
    from scripts.tools.wechat_mp_hotspot_research import ResearchHit

    raw = topic.item.get("web_research") or []
    hits: list[ResearchHit] = []
    for row in raw:
        if not isinstance(row, dict) or not row.get("title"):
            continue
        hits.append(
            ResearchHit(
                title=str(row.get("title") or ""),
                snippet=str(row.get("snippet") or ""),
                source=str(row.get("source") or ""),
                url=str(row.get("url") or ""),
                published=str(row.get("published") or ""),
            )
        )
    return hits


def llm_build_hotspot_title(
    *,
    topic: HotspotTopic,
    hits: list[Any],
    body: str = "",
) -> str | None:
    if not is_wechat_mp_llm_configured():
        return None
    from scripts.tools.wechat_mp_hotspot_research import (
        format_hotspot_research_block,
        sanitize_hotspot_title,
        title_is_acceptable,
    )

    facts = format_hotspot_research_block(hits) if hits else ""
    trend = str(topic.item.get("title") or topic.section_title).strip()
    prompt = f"""为公众号写标题（≤32字，**不要**以「热点深评｜」「A股」开头）。

像新闻编辑的路牌：前 15 字说清**具体事实**（人物/案由/片名/数字），表意完整。

禁止：
- 「影响大吗」「该关注啥」「怎么看」「和A股啥关系」等模板尾缀
- 半句话、省略号、热榜播报腔

热搜：{trend}
{facts}
正文开篇：{(body or '')[:280]}

只输出一行标题。"""
    try:
        raw = call_wechat_mp_llm(
            [
                {
                    "role": "system",
                    "content": "只输出标题一行。好例子：伪造结婚证做试管，丈夫第三者是谁？",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=120,
        )
        lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
        if not lines:
            return None
        title = sanitize_hotspot_title(lines[0])
        if title_is_acceptable(title):
            return title
    except Exception:
        pass
    return None


def build_hotspot_title(topics: list[HotspotTopic], *, body: str = "") -> str:
    if not topics:
        return "当日热点话题解读？"
    topic = topics[0]
    hits = _research_hits_from_topic(topic)
    trend = str(topic.item.get("title") or topic.section_title).strip()

    llm_title = llm_build_hotspot_title(topic=topic, hits=hits, body=body)
    if llm_title:
        from scripts.tools.wechat_mp_content import _clip_wechat_title
        from scripts.tools.wechat_mp_public import sanitize_public_title
        from scripts.tools.wechat_mp_seo import enrich_title_for_search

        clean = sanitize_public_title(llm_title, kind="hotspot")
        return enrich_title_for_search(
            clean,
            "hotspot",
            clip_fn=lambda t, _m=_WECHAT_TITLE_MAX: _clip_wechat_title(t, max_len=_m),
        )

    from scripts.tools.wechat_mp_hotspot_research import build_hotspot_title_from_facts

    raw = build_hotspot_title_from_facts(hits, trend=trend)
    from scripts.tools.wechat_mp_content import _clip_wechat_title
    from scripts.tools.wechat_mp_public import sanitize_public_title
    from scripts.tools.wechat_mp_seo import enrich_title_for_search

    clean = sanitize_public_title(raw, kind="hotspot")
    clean = clean.replace("\u201c", "").replace("\u201d", "").replace('"', "")
    return enrich_title_for_search(
        clean,
        "hotspot",
        clip_fn=lambda t, _m=_WECHAT_TITLE_MAX: _clip_wechat_title(t, max_len=_m),
    )


def build_hotspot_digest(
    topics: list[HotspotTopic],
    *,
    trade_label: str,
) -> str:
    hook = topics[0].section_title if topics else "当日热点"
    base = (
        f"【{trade_label} 热点深评】{hook}——"
        f"整理公开信息与多方观点，供阅读与讨论。"
    )
    from scripts.tools.wechat_mp_seo import enrich_digest

    return enrich_digest(base, "hotspot")
