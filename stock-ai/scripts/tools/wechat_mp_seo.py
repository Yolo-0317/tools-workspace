#!/usr/bin/env python3
"""公众号摘要 SEO 词表与发布后 #话题 推荐（须后台手动添加）。"""

from __future__ import annotations

import os
import re
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
    "hotspot": ("热点观察", "话题评论"),
    "hot_business": ("热点商业", "商业观察"),
    "silver": ("退休生活", "中年生活"),
    "short_drama_feature": ("短剧推荐", "热门短剧"),
    "tv_review": ("热点观察", "话题讨论"),
    "workspace": ("工具工作区", "量化自动化"),
    "temp": ("开发者工具", "飞书自动化"),
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
    "hotspot": "整理公开信息与多方观点，供阅读与讨论",
    "hot_business": "从热点看公司、生意与利益关系",
    "silver": "从关系、健康和钱财细节重新安排退休生活",
    "short_drama_feature": "一部短剧的核心冲突与追剧看点",
    "tv_review": "社会文娱公共热点，呈现多方说法",
    "workspace": "收盘入库到草稿的一条龙",
    "temp": "单篇技术笔记可独立发布",
}

# 标题搜一搜：前 15 字内尽量出现；勿堆砌（与摘要 SEO 词表对齐）
TITLE_SEO_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sector": ("A股", "行业", "产业链", "热点", "板块", "情绪", "怎么拆"),
    "market": ("A股", "收盘", "盘前", "午间", "复盘"),
    "news": ("A股", "快讯", "要闻", "财经", "人气"),
    "hotspot": ("热点", "社会", "话题", "事件", "公共", "评论", "讨论"),
    "hot_business": ("品牌", "公司", "生意", "成本", "渠道", "商业"),
    "silver": ("退休", "退休生活", "中年生活", "夫妻", "健康", "养老金", "防骗"),
    "short_drama_feature": ("短剧", "逆袭", "反击", "反转", "追妻", "职场", "家庭"),
    "tv_review": ("热点", "社会", "话题", "事件", "公共", "讨论"),
}

TITLE_SEO_FRONT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sector": ("A股", "行业", "产业链"),
    "market": ("A股", "收盘复盘", "盘前", "午间"),
    "news": ("A股", "快讯"),
    "hotspot": ("热点", "社会", "话题", "事件"),
    "hot_business": ("品牌", "公司", "生意", "成本", "渠道", "商业"),
    "silver": ("退休", "退休生活", "夫妻", "健康", "养老金", "防骗"),
    "short_drama_feature": ("短剧",),
    "tv_review": ("热点", "社会", "话题", "事件"),
}

TITLE_SEO_PREFIX: dict[str, str | dict[str, str]] = {
    "sector": "A股行业｜",
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
    "workspace": {
        "default": ("开发者工具", "量化自动化", "个人项目"),
    },
    "temp": {
        "default": ("开发者工具", "飞书", "效率工具"),
    },
    "hotspot": {
        "default": ("热点观察", "社会话题", "公共事件"),
    },
    "short_drama_feature": {
        "default": ("短剧", "短剧推荐", "追剧"),
    },
    "hot_business": {
        "default": ("热点商业", "商业观察", "品牌故事"),
    },
    "silver": {
        "default": ("退休生活", "中年生活", "生活方式"),
        "relation": ("退休生活", "家庭关系", "夫妻相处"),
        "health": ("退休生活", "健康生活", "生活习惯"),
        "money": ("退休生活", "养老防骗", "理性消费"),
    },
    "tv_review": {
        "default": ("热点观察", "话题讨论", "社会观察"),
    },
}

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
    "2. 发布时勾选「原创」（分类选社会/娱乐/资讯，勿默认财经）",
    "3. 发布成功后点文章右侧 #，粘贴下方推荐话题（最多 5 个）",
    "4. 可选：文末星标引导；tv_review 可弱化推荐 ♡",
)

PUBLISH_STEPS_HOTSPOT = (
    "1. mp.weixin.qq.com 草稿 → 预览",
    "2. 勾选「原创」（分类选社会/娱乐/资讯）",
    "3. # 话题优先实体词（案由/片名/事件），勿 #A股 打头",
    "4. 确认摘要含「热点观察」或标题实体词已在正文首段出现",
)

PUBLISH_STEPS_TV_REVIEW = (
    "1. mp.weixin.qq.com 草稿 → 预览正文剧照与封面",
    "2. 勾选「原创」（分类选 生活/娱乐，勿选财经）",
    "3. 确认配图说明在文末；敏感剧照勿留",
    "4. 发布成功后 # 话题（美剧/HBO/剧评等，最多 5 个）",
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
    """标题句式加分：优先平台推荐安全表述（2026-06 调整后）。"""
    t = title or ""
    if kind == "sector":
        return (
            (2 if "产业链" in t else 0)
            + (2 if "怎么拆" in t else 0)
            + (1 if "A股" in t[:15] or "行业" in t[:15] else 0)
            - (2 if "怎么跟" in t or "领衔" in t else 0)
        )
    if kind == "news":
        return (
            (2 if "快讯" in t or "要闻" in t or "人气" in t else 0)
            + (1 if "对照" in t else 0)
            - (2 if "领衔" in t or "热股" in t else 0)
            - (3 if "必读" in t else 0)
            - (2 if "怎么读" in t else 0)
        )
    if kind in {"hotspot", "hot_business", "tv_review", "literary"}:
        front = t[:15]
        return (
            (2 if re.search(r"\d", front) else 0)
            + (1 if any(k in front for k in ("热点", "社会", "话题", "事件")) else 0)
            + (1 if len(front.strip()) >= 10 else 0)
            - (3 if "A股" in front[:6] else 0)
            - (2 if "复盘" in front or "龙头" in front else 0)
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
        from scripts.tools.wechat_mp_public import sanitize_public_title

        return sanitize_public_title(t, kind=kind)
    prefix = _title_seo_prefix(kind, edition=edition)
    if not prefix or t.startswith(prefix.rstrip("｜")):
        from scripts.tools.wechat_mp_public import sanitize_public_title

        return sanitize_public_title(t, kind=kind)
    from scripts.tools.wechat_mp_public import sanitize_public_title

    return sanitize_public_title(clip(f"{prefix}{t}"), kind=kind)


def _digest_contains_keyword(digest: str, keyword: str) -> bool:
    return keyword in digest


def enrich_digest(base: str, kind: str, *, edition: str | None = None) -> str:
    """在摘要中自然嵌入稿型 SEO 核心词（已有则跳过）。"""
    if kind == "market" and edition:
        core = market_digest_core(edition)
        phrase = market_digest_phrase(edition)
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
    theme: str | None = None,
    extra: str | None = None,
) -> list[str]:
    """返回最多 HASHTAG_MAX 个话题名（不含 # 前缀）。"""
    pools = HASHTAG_POOL.get(kind, {})
    if kind == "market" and edition:
        base = list(pools.get(edition) or pools.get("default") or ())
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
    attach_promotion: bool = True,
    upload_figures: bool | None = None,
) -> dict[str, Any]:
    """body_text 变更后重建 content（与 _article_shell 同一套 HTML 规则）。"""
    from scripts.tools.wechat_mp_client import mp_configured
    from scripts.tools.wechat_mp_content import render_article_content_html
    from scripts.tools.wechat_mp_short_drama import attach_short_drama

    body = str(article.get("body_text") or "")
    can_upload = mp_configured() if upload_figures is None else upload_figures
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
    return attach_short_drama(out, kind=kind) if attach_promotion else out


def format_publish_reminder(*, kind: str | None = None) -> str:
    k = (kind or "").strip().lower()
    if k == "tv_review":
        return "发布提醒: " + " → ".join(PUBLISH_STEPS_TV_REVIEW)
    if k in {"hotspot", "hot_business"}:
        return "发布提醒: " + " → ".join(PUBLISH_STEPS_HOTSPOT)
    return "发布提醒: " + " → ".join(PUBLISH_STEPS_USER)


def attach_publish_hints(
    article: dict[str, Any],
    kind: str,
    *,
    edition: str | None = None,
    theme: str | None = None,
    hashtag_override: list[str] | None = None,
    engagement_kind: str | None = None,
    attach_promotion: bool = True,
    upload_figures: bool | None = None,
) -> dict[str, Any]:
    """写入非 API 字段，供 CLI / 通知展示。"""
    if hashtag_override is not None:
        tags = [_normalize_tag(t) for t in hashtag_override]
        tags = [t for t in tags if t][:HASHTAG_MAX]
    else:
        tags = recommended_hashtags(
            kind,
            edition=edition,
            theme=theme,
        )
    article["recommended_hashtags"] = tags
    article["publish_reminder"] = format_publish_reminder(kind=kind)
    if tags and hashtag_inline_enabled():
        article["body_text"] = append_hashtag_inline_to_body(
            str(article.get("body_text") or ""),
            tags,
        )
        article = sync_article_content_from_body(
            article,
            kind=kind,
            engagement_kind=engagement_kind or article.get("engagement_kind"),
            attach_promotion=attach_promotion,
            upload_figures=upload_figures,
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
        tags = recommended_hashtags(kind, edition=edition)
    print(format_hashtag_line(list(tags)))
    print(format_publish_reminder(kind=kind))
