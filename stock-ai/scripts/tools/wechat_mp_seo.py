#!/usr/bin/env python3
"""公众号摘要 SEO 词表与发布后 #话题 推荐（须后台手动添加）。"""

from __future__ import annotations

import os
from typing import Any

DIGEST_MAX = 128
HASHTAG_MAX = 5

# 搜一搜：标题/摘要优先匹配；每稿型 2 个核心词 + 1 个长尾短语（勿堆砌）
MARKET_DIGEST_SEO_BY_EDITION: dict[str, tuple[str, ...]] = {
    "pre": ("A股", "盘前观察"),
    "midday": ("A股", "午间复盘"),
    "close": ("A股", "收盘复盘"),
}

DIGEST_SEO_CORE: dict[str, tuple[str, ...]] = {
    "sector": ("A股", "行业研究"),
    "market": ("A股", "收盘复盘"),
    "news": ("A股", "财经快讯"),
    "top5": ("A股", "选股观察"),
    "dragons": ("A股", "龙头复盘"),
    "workspace": ("工具工作区", "量化自动化"),
    "temp": ("开发者工具", "飞书自动化"),
    "commerce": ("租屋", "小家电"),
}

MARKET_DIGEST_PHRASE_BY_EDITION: dict[str, str] = {
    "pre": "外围映射与开盘结构",
    "midday": "上午盘面与午后节奏",
    "close": "指数外围与结构判断",
}

DIGEST_SEO_PHRASE: dict[str, str] = {
    "sector": "热点行业产业链与情绪结构观察",
    "market": "指数外围与结构判断",
    "news": "Top10要闻逐条解读",
    "top5": "领衔股收盘信号与结构观察",
    "dragons": "情绪周期与龙头梯队",
    "workspace": "收盘入库到草稿的一条龙",
    "temp": "单篇技术笔记可独立发布",
    "commerce": "合租单间买前对照",
}

COMMERCE_DIGEST_SEO_BY_SLOT: dict[str, tuple[str, ...]] = {
    "guide": ("租屋", "小家电"),
    "review": ("小家电", "测评"),
    "trend": ("租房", "季节好物"),
}

# 标题搜一搜：前 15 字内尽量出现；勿堆砌（与摘要 SEO 词表对齐）
TITLE_SEO_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sector": ("A股", "行业", "产业链", "热点", "板块", "情绪", "怎么拆", "怎么跟"),
    "market": ("A股", "收盘", "盘前", "午间", "复盘"),
    "top5": ("A股", "选股", "盯盘", "技术面", "收盘信号", "领衔", "明日盯"),
    "dragons": ("A股", "龙头", "情绪", "复盘", "连板", "怎么玩", "还在榜"),
    "news": ("A股", "快讯", "要闻", "财经"),
    "commerce": ("租屋", "合租", "单间", "小家电", "小电", "厨房", "租房"),
}

TITLE_SEO_FRONT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sector": ("A股", "行业", "产业链"),
    "market": ("A股", "收盘复盘", "盘前", "午间"),
    "top5": ("A股", "选股", "领衔", "收盘信号"),
    "dragons": ("A股", "龙头", "情绪", "怎么玩", "还在榜"),
    "news": ("A股", "快讯"),
    "commerce": ("租屋", "合租", "单间", "小家电", "租房"),
}

TITLE_SEO_PREFIX: dict[str, str | dict[str, str]] = {
    "commerce": "租屋小电｜",
    "sector": "A股行业｜",
    "top5": "A股选股｜",
    "dragons": "A股龙头｜",
    "news": "A股快讯｜",
    "market": {
        "pre": "A股盘前｜",
        "midday": "A股午间｜",
        "close": "A股收盘｜",
    },
}

# 发布后 #话题（原创通过后，最多 5 个；顺序：大词 → 垂直 → 当日可选）
HASHTAG_POOL: dict[str, dict[str, tuple[str, ...]]] = {
    "sector": {
        "default": ("A股", "行业研究", "产业链"),
    },
    "market": {
        "default": ("A股", "收盘复盘", "盘面分析"),
        "pre": ("A股", "盘前观察", "外围市场"),
        "midday": ("A股", "午间复盘", "盘面速览"),
        "close": ("A股", "收盘复盘", "结构分析"),
    },
    "news": {
        "default": ("A股", "财经快讯", "宏观解读"),
    },
    "top5": {
        "default": ("A股", "选股观察", "收盘信号"),
    },
    "dragons": {
        "default": ("A股", "龙头战法", "情绪周期"),
        "intraday": ("A股", "盘中龙头", "情绪周期"),
        "eod": ("A股", "收盘龙头", "连板梯队"),
    },
    "workspace": {
        "default": ("开发者工具", "量化自动化", "个人项目"),
    },
    "temp": {
        "default": ("开发者工具", "飞书", "效率工具"),
    },
    "commerce": {
        "default": ("租房好物", "小家电", "买前对照"),
        "guide": ("租房好物", "小家电", "买前对照"),
        "review": ("小家电测评", "租房", "避坑"),
        "trend": ("季节好物", "小家电", "租房"),
    },
}

PUBLISH_STEPS_COMMERCE = (
    "1. mp.weixin.qq.com 草稿 → 确认简选小电顶栏 banner",
    "2. 发布勾选「原创」（分类选 生活/家居，勿选财经）",
    "3. 发布成功后点 #，粘贴终端推荐话题（最多 5 个）",
    "4. 可选：朋友圈发预览截图（清单一节）引流",
)

PUBLISH_STEPS_COMMERCE_AUTO = (
    "1. 已走 freepublish API 直接发表（无原创/#话题）",
    "2. 可在 mp.weixin.qq.com 已发表列表核对 CPS 与版式",
    "3. 要原创时改用 wechat_mp_commerce_draft --no-publish",
)

HASHTAG_BANNED = frozenset(
    {
        "牛股推荐",
        "荐股",
        "涨停预测",
        "内幕",
        "稳赚",
        "必涨",
    }
)

PUBLISH_STEPS_USER = (
    "1. mp.weixin.qq.com 打开草稿 → 预览",
    "2. 发布时勾选「原创」（分类选财经/科技）",
    "3. 发布成功后点文章右侧 #，粘贴下方推荐话题（最多 5 个）",
    "4. 可选：文末或朋友圈提醒读者点「推荐 ♡」（朋友推荐流权重高）",
)


def market_digest_core(edition: str | None) -> tuple[str, ...]:
    from scripts.tools.wechat_mp_market_edition import normalize_market_edition

    ed = normalize_market_edition(edition) if edition else "close"
    return MARKET_DIGEST_SEO_BY_EDITION.get(ed, DIGEST_SEO_CORE["market"])


def market_digest_phrase(edition: str | None) -> str:
    from scripts.tools.wechat_mp_market_edition import normalize_market_edition

    ed = normalize_market_edition(edition) if edition else "close"
    return MARKET_DIGEST_PHRASE_BY_EDITION.get(ed, DIGEST_SEO_PHRASE["market"])


def clip_digest(text: str, *, max_len: int = DIGEST_MAX) -> str:
    """微信 draft digest 上限为 max_len **字节**（非字符数）。"""
    t = " ".join(text.split())
    raw = t.encode("utf-8")
    if len(raw) <= max_len:
        return t
    cut = raw[:max_len]
    while cut:
        try:
            return cut.decode("utf-8")
        except UnicodeDecodeError:
            cut = cut[:-1]
    return ""


def title_has_search_keywords(
    title: str,
    kind: str,
    *,
    edition: str | None = None,
) -> bool:
    del edition
    keys = TITLE_SEO_KEYWORDS.get(kind, ())
    t = (title or "").strip()
    return any(k in t for k in keys)


def title_front_has_search_keywords(
    title: str,
    kind: str,
    *,
    edition: str | None = None,
) -> bool:
    del edition
    front = (title or "").strip()[:15]
    keys = TITLE_SEO_FRONT_KEYWORDS.get(kind, TITLE_SEO_KEYWORDS.get(kind, ()))
    return any(k in front for k in keys)


def title_sousou_hook_score(title: str, kind: str) -> int:
    """搜一搜看板验证过的标题句式加分（2026-06 牛马也智能）。"""
    t = title or ""
    if kind == "dragons":
        return (
            (2 if "怎么玩" in t else 0)
            + (2 if "还在榜" in t else 0)
            + (1 if "情绪" in t[:18] else 0)
        )
    if kind == "top5":
        return (
            (2 if "领衔" in t else 0)
            + (2 if "收盘信号" in t else 0)
            + (1 if "明日盯" in t else 0)
        )
    if kind == "sector":
        return (
            (2 if "产业链" in t else 0)
            + (2 if "怎么拆" in t or "怎么跟" in t else 0)
            + (1 if "A股" in t[:15] or "行业" in t[:15] else 0)
        )
    return 0


def title_search_rank_key(
    title: str,
    kind: str,
    *,
    edition: str | None = None,
) -> tuple:
    """越大越优先（供标题池排序）。"""
    t = title or ""
    hook = "？" in t or "?" in t or "！" in t or "!" in t
    return (
        title_sousou_hook_score(t, kind),
        title_front_has_search_keywords(t, kind, edition=edition),
        title_has_search_keywords(t, kind, edition=edition),
        hook,
        -len(t),
    )


def _title_seo_prefix(kind: str, *, edition: str | None = None) -> str:
    raw = TITLE_SEO_PREFIX.get(kind, "")
    if isinstance(raw, dict):
        from scripts.tools.wechat_mp_market_edition import normalize_market_edition

        ed = normalize_market_edition(edition) if edition else "close"
        return raw.get(ed, raw.get("close", ""))
    return str(raw)


def enrich_title_for_search(
    title: str,
    kind: str,
    *,
    edition: str | None = None,
    max_len: int = 32,
    clip_fn=None,
) -> str:
    """标题前 15 字缺搜一搜词时，加短前缀（≤32 字）。"""
    clip = clip_fn or (lambda x: x[:max_len])
    t = clip((title or "").strip())
    if not kind or kind not in TITLE_SEO_KEYWORDS:
        return t
    if title_front_has_search_keywords(t, kind, edition=edition):
        return t
    prefix = _title_seo_prefix(kind, edition=edition)
    if not prefix or t.startswith(prefix.rstrip("｜")):
        return t
    return clip(f"{prefix}{t}")


def _digest_contains_keyword(digest: str, keyword: str) -> bool:
    return keyword in digest


def commerce_digest_core(slot: str | None) -> tuple[str, ...]:
    s = (slot or "guide").strip().lower()
    return COMMERCE_DIGEST_SEO_BY_SLOT.get(s, DIGEST_SEO_CORE["commerce"])


def enrich_digest(base: str, kind: str, *, edition: str | None = None) -> str:
    """在摘要中自然嵌入稿型 SEO 核心词（已有则跳过）。"""
    if kind == "market" and edition:
        core = market_digest_core(edition)
        phrase = market_digest_phrase(edition)
    elif kind == "commerce" and edition:
        core = commerce_digest_core(edition)
        phrase = DIGEST_SEO_PHRASE["commerce"]
    else:
        core = DIGEST_SEO_CORE.get(kind, ())
        phrase = DIGEST_SEO_PHRASE.get(kind, "")
    out = base.strip()
    missing = [k for k in core if k and not _digest_contains_keyword(out, k)]
    if missing and phrase:
        tail = f"{'、'.join(missing)}·{phrase}"
        if len(out) + len(tail) + 1 <= DIGEST_MAX:
            out = f"{out} {tail}".strip()
        elif missing:
            tail = missing[0]
            if len(out) + len(tail) + 1 <= DIGEST_MAX:
                out = f"{out} {tail}".strip()
    elif missing and len(out) + len(missing[0]) + 1 <= DIGEST_MAX:
        out = f"{out} {missing[0]}".strip()
    return clip_digest(out)


def _normalize_tag(tag: str) -> str:
    t = (tag or "").strip().lstrip("#").strip()
    if not t or t in HASHTAG_BANNED:
        return ""
    return t[:20]


def recommended_hashtags(
    kind: str,
    *,
    edition: str | None = None,
    dragon_slot: str | None = None,
    theme: str | None = None,
    phase: str | None = None,
    extra: str | None = None,
) -> list[str]:
    """返回最多 HASHTAG_MAX 个话题名（不含 # 前缀）。"""
    pools = HASHTAG_POOL.get(kind, {})
    if kind == "market" and edition:
        base = list(pools.get(edition) or pools.get("default") or ())
    elif kind == "commerce" and edition:
        base = list(pools.get(edition) or pools.get("default") or ())
    elif kind == "dragons" and dragon_slot:
        base = list(pools.get(dragon_slot) or pools.get("default") or ())
    else:
        base = list(pools.get("default") or ())

    tags: list[str] = []
    for raw in base:
        t = _normalize_tag(raw)
        if t and t not in tags:
            tags.append(t)

    if theme:
        t = _normalize_tag(str(theme)[:8])
        if t and t not in tags and len(tags) < HASHTAG_MAX:
            tags.append(t)

    if phase and kind == "dragons":
        t = _normalize_tag(f"情绪{str(phase)[:4]}")
        if t and t not in tags and len(tags) < HASHTAG_MAX:
            tags.append(t)

    if extra:
        t = _normalize_tag(extra)
        if t and t not in tags and len(tags) < HASHTAG_MAX:
            tags.append(t)

    return tags[:HASHTAG_MAX]


def format_hashtag_line(tags: list[str]) -> str:
    if not tags:
        return "推荐 #话题: （无）"
    return "推荐 #话题: " + " ".join(f"#{t}" for t in tags)


def hashtag_inline_enabled() -> bool:
    raw = os.getenv("WECHAT_MP_HASHTAG_INLINE", "").strip().lower()
    if raw:
        return raw not in ("0", "false", "no", "off")
    # 兼容旧开关
    legacy = os.getenv("WECHAT_MP_HASHTAG_FOOTER", "1").strip().lower()
    return legacy not in ("0", "false", "no", "off")


def format_hashtag_inline_line(tags: list[str]) -> str:
    """正文文末一行话题（直接写入，无发布说明）。"""
    if not tags:
        return ""
    return "\n\n" + " ".join(f"#{t}" for t in tags)


def insert_hashtags_after_intro(body: str, tags: list[str]) -> str:
    """在首段后插入 #话题行（简选小电正文内展示）。"""
    if not tags:
        return body
    line = " ".join(f"#{t}" for t in tags)
    if line in body:
        return body
    text = body.strip()
    if not text:
        return line
    parts = text.split("\n\n", 1)
    if len(parts) == 1:
        return f"{parts[0]}\n\n{line}"
    intro, rest = parts[0], parts[1]
    return f"{intro}\n\n{line}\n\n{rest}"


def body_has_inline_hashtags(body_text: str, tags: list[str]) -> bool:
    if not tags:
        return True
    line = " ".join(f"#{t}" for t in tags)
    return line in body_text


def append_hashtag_inline_to_body(body_text: str, tags: list[str]) -> str:
    """免责声明前追加一行 #话题（供搜一搜与读者可见）。"""
    if not tags or not hashtag_inline_enabled():
        return body_text
    if body_has_inline_hashtags(body_text, tags):
        return body_text
    from scripts.tools.wechat_mp_monetization import split_disclaimer

    block = format_hashtag_inline_line(tags)
    if not block:
        return body_text
    core, disc = split_disclaimer(body_text)
    if disc:
        return f"{core.rstrip()}{block}\n\n{disc}"
    return f"{core.rstrip()}{block}"


# 兼容旧名
hashtag_footer_enabled = hashtag_inline_enabled
append_hashtag_footer_to_body = append_hashtag_inline_to_body


def sync_article_content_from_body(
    article: dict[str, Any],
    *,
    kind: str,
    engagement_kind: str | None = None,
) -> dict[str, Any]:
    """body_text 变更后重建 content（与 _article_shell 同一套 HTML 规则）。"""
    from scripts.tools.wechat_mp_client import mp_configured
    from scripts.tools.wechat_mp_content import render_article_content_html
    from scripts.tools.wechat_mp_product import attach_footer_product

    body = str(article.get("body_text") or "")
    can_upload = mp_configured()
    ek = engagement_kind or article.get("engagement_kind")
    content, merged_body = render_article_content_html(
        body,
        kind=kind,
        engagement_kind=ek,
        upload_figures=can_upload,
    )
    out = dict(article)
    out["body_text"] = merged_body
    out["content"] = content
    return attach_footer_product(out, kind=kind)


def format_publish_reminder(*, kind: str | None = None) -> str:
    if (kind or "").strip().lower() == "commerce":
        import os

        auto = os.getenv("WECHAT_MP_COMMERCE_AUTO_PUBLISH", "0").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        steps = PUBLISH_STEPS_COMMERCE_AUTO if auto else PUBLISH_STEPS_COMMERCE
        return "发布提醒: " + " → ".join(steps)
    return "发布提醒: " + " → ".join(PUBLISH_STEPS_USER)


def attach_publish_hints(
    article: dict[str, Any],
    kind: str,
    *,
    edition: str | None = None,
    dragon_slot: str | None = None,
    theme: str | None = None,
    phase: str | None = None,
    hashtag_override: list[str] | None = None,
    engagement_kind: str | None = None,
) -> dict[str, Any]:
    """写入非 API 字段，供 CLI / 通知展示。"""
    if hashtag_override is not None:
        tags = [_normalize_tag(t) for t in hashtag_override]
        tags = [t for t in tags if t][:HASHTAG_MAX]
    else:
        tags = recommended_hashtags(
            kind,
            edition=edition,
            dragon_slot=dragon_slot,
            theme=theme,
            phase=phase,
        )
    article["recommended_hashtags"] = tags
    article["publish_reminder"] = format_publish_reminder(kind=kind)
    if tags and hashtag_inline_enabled():
        article["body_text"] = append_hashtag_inline_to_body(
            str(article.get("body_text") or ""),
            tags,
        )
        if kind != "commerce":
            article = sync_article_content_from_body(
                article,
                kind=kind,
                engagement_kind=engagement_kind or article.get("engagement_kind"),
            )
    return article


def print_publish_hints(
    kind: str,
    article: dict[str, Any],
    *,
    edition: str | None = None,
) -> None:
    tags = article.get("recommended_hashtags")
    if not tags:
        slot = None
        if kind == "dragons":
            import os

            slot = os.getenv("WECHAT_MP_DRAGON_SLOT", "").strip() or None
        tags = recommended_hashtags(kind, edition=edition, dragon_slot=slot)
    print(format_hashtag_line(list(tags)))
    print(format_publish_reminder(kind=kind))
