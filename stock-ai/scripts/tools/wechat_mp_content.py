"""公众号日更正文：宏观盘面 / 要闻精选 / Top5 / 龙头 / 工作区技术分享。"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import ROOT

from scripts.tools.news_ai_interpret import sanitize_public_ai_summary
from scripts.tools.portfolio_db import load_emotion_cycle_checklist
from scripts.tools.wechat_format import normalize_wechat_spacing
from scripts.tools.wechat_mp_client import text_to_html
from scripts.tools.wechat_mp_prose import humanize_mp_text

if TYPE_CHECKING:
    from scripts.tools.wechat_mp_codex_hotspot import CodexHotspotDraft

TZ = ZoneInfo("Asia/Shanghai")
TITLE_MAX = 32
WEEKDAY_CN = "一二三四五六日"
DISCLAIMER = (
    "本文为作者个人市场信息整理与复盘笔记，非证券投资咨询、非理财推介，"
    "不构成投资建议；市场有风险，决策自负。"
)
COMMENTARY_DISCLAIMER = (
    "本公众号整理公开报道与网络讨论，仅供阅读与交流，不构成任何专业建议或事实背书。"
    "文中观点不代表本号立场。"
)
TECH_DISCLAIMER = "本文为作者个人工程笔记，仅供学习交流。"
TECH_DRAFT_KINDS = frozenset({"workspace", "temp", "tech", "lab", "dev"})


def disclaimer_for_kind(kind: str | None) -> str:
    """行情稿用投资免责；热点评论用信息整理说明；技术分享用工程笔记说明。"""
    k = (kind or "").strip().lower()
    if k == "guba":
        return ""
    if k == "hotspot":
        return COMMENTARY_DISCLAIMER
    if k in {"tv_review", "tv", "film", "movie"}:
        return ""
    if k in TECH_DRAFT_KINDS:
        return TECH_DISCLAIMER
    return DISCLAIMER


def _clip_wechat_title(text: str, *, max_len: int = TITLE_MAX) -> str:
    """公众号标题上限 32 字；优先在 ｜、· 处截断。"""
    text = re.sub(r"\s+", "", (text or "").strip())
    if len(text) <= max_len:
        return text
    for sep in ("｜", "·", "：", "—"):
        parts = text.split(sep)
        buf = ""
        for i, part in enumerate(parts):
            chunk = part if i == 0 else sep + part
            if len(buf) + len(chunk) <= max_len:
                buf += chunk
            else:
                break
        if buf:
            return buf
    return text[:max_len]


def _cn_date(d: date | datetime) -> str:
    if isinstance(d, datetime):
        d = d.date()
    return f"{d.month}月{d.day}日"


def _weekday_cn(d: date) -> str:
    return f"周{WEEKDAY_CN[d.weekday()]}"


def _market_publish_label(*, edition: str | None = None) -> str:
    from scripts.tools.wechat_mp_market_edition import edition_label, normalize_market_edition

    try:
        return edition_label(normalize_market_edition(edition))
    except ValueError:
        return "收盘"


_MARKET_TITLE_BANNED = ()  # 分时段发稿后按 edition 生成标题，不再一律替换为「收盘」


def _sanitize_market_title(text: str, *, edition: str | None = None) -> str:
    del edition
    return (text or "").strip()


def _extract_market_hook(ai: str, *, max_len: int = 14) -> str:
    """从宏观 AI 摘要提炼标题钩子（题材/事件关键词）。"""
    candidates: list[tuple[int, str]] = []
    for line in ai.splitlines():
        s = line.strip()
        if not s or s.startswith("【"):
            continue
        score = 0
        if re.match(r"^[\-·]", s) or re.match(r"^\d+\.", s):
            score += 2
        if s.startswith(("📊", "📰", "📋", "👀", "⚠️")):
            s = s[1:].strip()
            score += 1
        s = re.sub(r"^\d+\.\s*", "", s)
        s = re.sub(r"^\[.*?\]\s*", "", s)
        s = re.sub(r"^[\-·]\s*", "", s)
        if len(s) < 6:
            continue
        if re.search(r"(仍是|主要|整体|总体|来看|方面)", s) and score < 2:
            continue
        if re.search(r"(拟约|收购|销量|立案|子公司|\d+\.\d+亿)", s):
            score -= 3
        for cut in ("，", "。", "；", "：", " "):
            if cut in s:
                s = s.split(cut, 1)[0]
        s = s.strip()
        if 4 <= len(s) <= 28:
            candidates.append((score, s))
    candidates.sort(key=lambda x: (-x[0], -len(x[1])))
    plain = [c[1] for c in candidates]
    if not plain:
        return "宏观快讯与外围脉络"

    priority = (
        "中东",
        "霍尔木兹",
        "原油",
        "服务业",
        "半导体",
        "政策",
        "板块",
        "华为",
        "电力",
        "煤炭",
        "情绪",
        "扩能",
    )
    for kw in priority:
        for c in plain:
            if kw in c:
                return c[:max_len]

    hook = plain[0][:max_len]
    if len(plain) >= 2 and len(hook) < max_len - 1:
        second = plain[1][: max(4, max_len - len(hook) - 1)]
        combo = f"{hook}·{second}"
        return combo[:max_len]
    return hook


def _compress_market_tags(ai: str, *, edition: str | None = None) -> str:
    """标题用短标签；优先多源挖掘当日热门行业（wechat_mp_hot_theme）。"""
    from scripts.tools.wechat_mp_market_edition import normalize_market_edition

    blob = ai
    try:
        ed = normalize_market_edition(edition) if edition else "close"
    except ValueError:
        ed = "close"

    if os.getenv("WECHAT_MP_HOT_THEME", "1").strip() not in {"0", "false", "no"}:
        try:
            from scripts.tools.wechat_mp_hot_theme import discover_hot_themes, format_title_tags

            report = discover_hot_themes(
                edition=ed,
                draft_blob=blob,
                include_opencli=os.getenv("WECHAT_MP_HOT_THEME_OPENCLI", "0").strip()
                in {"1", "true", "yes"},
            )
            tags = format_title_tags(report, max_len=12)
            if tags and tags != "盘面结构":
                return tags
        except Exception:
            pass

    if ed == "pre":
        pairs = (
            ("A50", "A50偏弱"),
            ("富时中国", "A50期货"),
            ("煤化工", "煤化工"),
            ("MLCC", "MLCC缺口"),
            ("日经", "日股强势"),
            ("商业航天", "航天IPO"),
            ("创业板", "创业板"),
            ("开盘", "开盘结构"),
            ("原油", "油价脉冲"),
            ("半导体", "半导体"),
        )
    elif ed == "midday":
        pairs = (
            ("上午", "上午主线"),
            ("半日", "半日结构"),
            ("涨停", "涨停梯队"),
            ("情绪", "情绪"),
            ("半导体", "半导体"),
            ("原油", "油价"),
            ("主线", "主线"),
        )
    else:
        pairs = (
            ("霍尔木兹", "霍尔木兹"),
            ("中东", "中东局势"),
            ("原油", "油价"),
            ("服务业", "服务业"),
            ("半导体", "半导体"),
            ("华为", "华为链"),
            ("山东", "山东政策"),
            ("涨停", "涨停潮"),
            ("跌停", "亏钱效应"),
        )
    tags: list[str] = []
    for kw, label in pairs:
        if kw in blob and label not in tags:
            tags.append(label)
        if len(tags) >= 2:
            break
    if tags:
        from scripts.tools.wechat_mp_market_titles import join_market_title_tags

        return join_market_title_tags(tags)
    return _extract_market_hook(ai, max_len=10)


_MARKET_TITLE_LOG = ROOT / "data" / "wechat_mp_market_title_log.json"


def _load_last_market_title(edition: str) -> str | None:
    """读取最近一次指定时段 market 标题（用于盘前避开昨日盘后钩子）。"""
    if not _MARKET_TITLE_LOG.is_file():
        return None
    try:
        data = json.loads(_MARKET_TITLE_LOG.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    # 优先同日 close；否则最近一条 close
    today = datetime.now(TZ).date().isoformat()
    if edition == "close":
        row = data.get(today) if isinstance(data.get(today), dict) else None
        if row and row.get("close"):
            return str(row["close"])
    best: str | None = None
    for day_key in sorted(data.keys(), reverse=True):
        row = data.get(day_key)
        if isinstance(row, dict) and row.get(edition):
            best = str(row[edition])
            break
    return best


MARKET_BODY_CACHE = ROOT / "data" / "wechat_mp_market_body_cache.json"


def _save_market_body_cache(
    *,
    edition: str,
    body_text: str,
    title: str,
    digest: str,
) -> None:
    MARKET_BODY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    MARKET_BODY_CACHE.write_text(
        json.dumps(
            {
                "edition": edition,
                "title": title,
                "digest": digest,
                "body_text": body_text,
                "saved_at": datetime.now(TZ).isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_market_body_cache() -> dict[str, Any] | None:
    if not MARKET_BODY_CACHE.is_file():
        return None
    try:
        data = json.loads(MARKET_BODY_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) and data.get("body_text") else None


def _record_market_title(*, edition: str, title: str) -> None:
    day = datetime.now(TZ).date().isoformat()
    data: dict[str, Any] = {}
    if _MARKET_TITLE_LOG.is_file():
        try:
            raw = json.loads(_MARKET_TITLE_LOG.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
        except Exception:
            pass
    row = data.get(day) if isinstance(data.get(day), dict) else {}
    row[str(edition)] = title[:32]
    data[day] = row
    _MARKET_TITLE_LOG.parent.mkdir(parents=True, exist_ok=True)
    _MARKET_TITLE_LOG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _pick_clickbait_title(
    options: list[str],
    *,
    peer_title: str | None = None,
    kind: str | None = None,
    edition: str | None = None,
) -> str:
    """优先选用带悬念、且不超过 32 字的标题；可与配对稿标题去重。"""
    from scripts.tools.wechat_mp_seo import title_search_rank_key

    def _rank(t: str) -> tuple:
        seo = title_search_rank_key(t, kind, edition=edition) if kind else (False, False, False, 0)
        risky = "必读" in t or "先看" in t or "怎么玩" in t or "还在榜" in t
        return (
            seo,
            ("？" in t or "?" in t or "！" in t),
            not risky,
            -len(t),
        )

    ranked = sorted(options, key=_rank, reverse=True)
    for text in ranked:
        clipped = _clip_wechat_title(text)
        if peer_title and _titles_too_similar(clipped, peer_title):
            continue
        if 10 <= len(clipped) <= TITLE_MAX:
            return clipped
    for text in reversed(ranked):
        clipped = _clip_wechat_title(text)
        if not peer_title or not _titles_too_similar(clipped, peer_title):
            return clipped
    return _clip_wechat_title(ranked[0])


_TITLE_COMPARE_DROP = (
    "收盘",
    "今晚",
    "别漏看",
    "必读",
    "10条",
    "要闻",
    "快讯",
    "复盘",
    "A股",
    "盘后",
    "逐条",
    "改写盘面",
    "怎么影响盘面",
    "7×24",
    "精选",
    "宏观",
)


def _title_compare_key(text: str) -> str:
    s = re.sub(r"[？！?｜，。、：\s]", "", (text or "").strip())
    for w in _TITLE_COMPARE_DROP:
        s = s.replace(w, "")
    return s


def _titles_too_similar(a: str, b: str) -> bool:
    """market / news 同日标题勿共用同一钩子或高度雷同。"""
    ka, kb = _title_compare_key(a), _title_compare_key(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    shorter, longer = (ka, kb) if len(ka) <= len(kb) else (kb, ka)
    if len(shorter) >= 4 and shorter in longer:
        return True
    if len(shorter) >= 6 and len(longer) >= 6:
        overlap = sum(1 for i in range(len(shorter) - 2) if shorter[i : i + 3] in longer)
        if overlap / max(len(shorter) - 2, 1) >= 0.55:
            return True
    return False


def _market_title(
    ai: str,
    *,
    now: datetime,
    slot: str = "",
    peer_title: str | None = None,
    edition: str | None = None,
) -> str:
    from scripts.tools.wechat_mp_market_edition import normalize_market_edition
    from scripts.tools.wechat_mp_market_titles import (
        build_market_title_options,
        load_recent_market_titles,
        pick_rotated_market_title,
    )

    ed = normalize_market_edition(edition)
    tags = _compress_market_tags(ai, edition=ed)
    wd = _weekday_cn(now.date())
    options = build_market_title_options(ed, wd=wd, tags=tags)
    recent = load_recent_market_titles(ed, log_path=_MARKET_TITLE_LOG, today=now.date())
    from scripts.tools.wechat_mp_seo import enrich_title_for_search

    raw = pick_rotated_market_title(
        options,
        now=now,
        edition=ed,
        peer_title=peer_title,
        recent_titles=recent,
        clip_fn=_clip_wechat_title,
        too_similar_fn=_titles_too_similar,
    )
    return _sanitize_market_title(
        enrich_title_for_search(
            raw,
            "market",
            edition=ed,
            clip_fn=_clip_wechat_title,
        ),
        edition=edition,
    )


def _market_digest(
    ai: str,
    *,
    now: datetime,
    slot: str = "",
    edition: str | None = None,
) -> str:
    del slot
    from scripts.tools.wechat_mp_seo import enrich_digest

    tags = _compress_market_tags(ai, edition=edition)
    label = _market_publish_label(edition=edition)
    base = (
        f"【{now.strftime('%m-%d')} {label}】{tags}——"
        "指数、外围与结构判断；3分钟读完盘面逻辑。个人观察，非荐股。"
    )
    return enrich_digest(base, "market", edition=edition)


def _news_title(
    items: list[dict[str, Any]],
    *,
    now: datetime,
    peer_title: str | None = None,
) -> str:
    blob = " ".join(str(it.get("title") or "") for it in items[:3])
    hook = _extract_market_hook(blob, max_len=12)
    hook_alt = _extract_market_hook(
        " ".join(str(it.get("title") or "") for it in items[1:4]),
        max_len=12,
    )
    wd = _weekday_cn(now.date())
    from scripts.tools.wechat_mp_seo import enrich_title_for_search

    from scripts.tools.wechat_mp_news_article import (
        is_hot_stock_news_mode,
        is_weekend_news_batch,
        news_pick_params,
    )

    top_n, _, _, _ = news_pick_params()
    n_label = str(top_n)
    from scripts.tools.wechat_mp_news_titles import (
        build_generic_news_title_options,
        build_hot_stock_news_title_options,
    )

    if is_hot_stock_news_mode():
        pools = build_hot_stock_news_title_options(
            items,
            now=now,
            n_label=n_label,
            weekend=is_weekend_news_batch(),
        )
    else:
        pools = build_generic_news_title_options(
            items,
            now=now,
            n_label=n_label,
            hook=hook,
            hook_alt=hook_alt,
            weekday_cn=wd,
        )
    for pool_idx, options in enumerate(pools):
        if not options:
            continue
        if pool_idx == 0:
            daily = _clip_wechat_title(options[0])
            if not peer_title or not _titles_too_similar(daily, peer_title):
                return enrich_title_for_search(daily, "news", clip_fn=_clip_wechat_title)
        title = _pick_clickbait_title(
            options,
            peer_title=peer_title,
            kind="news",
        )
        if not peer_title or not _titles_too_similar(title, peer_title):
            return enrich_title_for_search(title, "news", clip_fn=_clip_wechat_title)
    title = _pick_clickbait_title(pools[-1], peer_title=None, kind="news")
    return enrich_title_for_search(title, "news", clip_fn=_clip_wechat_title)


def _news_digest(items: list[dict[str, Any]], *, now: datetime) -> str:
    from scripts.tools.wechat_mp_seo import enrich_digest
    from scripts.tools.wechat_mp_news_article import (
        is_hot_stock_news_mode,
        is_weekend_news_batch,
        news_pick_params,
    )

    hook = _extract_market_hook(
        " ".join(str(it.get("title") or "") for it in items[:2]),
        max_len=14,
    )
    top_n, _, hours, _ = news_pick_params()
    if is_hot_stock_news_mode():
        names = [
            str(it.get("matched_stock_name") or "").strip()
            for it in items[:3]
            if str(it.get("matched_stock_name") or "").strip()
        ]
        name_blob = "、".join(names) if names else hook
        anchor_label = str(
            (items[0] or {}).get("hot_stock_anchor_label") or "上一交易日收盘"
        )
        lead = names[0] if names else hook
        if is_weekend_news_batch():
            base = (
                f"【周末{now.strftime('%m-%d')}】{anchor_label}人气Top{top_n}锚"
                f"+{hours}h快讯（{lead}等）；休市榜为快照。摘要+AI点评，非荐股。"
            )
        else:
            base = (
                f"【{now.strftime('%m-%d')} 人气】{anchor_label}Top{top_n}"
                f"+{hours}h快讯（{lead}等）；摘要+AI点评，非荐股。"
            )
    else:
        base = (
            f"【{now.strftime('%m-%d')} 要闻】Top{top_n} 快讯，"
            f"主线 {hook}，每条附 AI 点评。信息整理，非荐股。"
        )
    return enrich_digest(base, "news")


def _top5_title(picks: list[Any], *, trade_date: date) -> str:
    names = [str(getattr(p, "name", "") or "").strip() for p in picks]
    names = [n for n in names if n and not n.isdigit()]
    n = len(names) or len(picks)
    wd = _weekday_cn(trade_date)
    from scripts.tools.wechat_mp_seo import enrich_title_for_search

    if names:
        lead = names[0]
        if n >= 2:
            raw = _clip_wechat_title(f"A股观察｜{lead}等{n}只，结构怎么读？")
            return enrich_title_for_search(raw, "top5", clip_fn=_clip_wechat_title)
        title = _pick_clickbait_title(
            [
                f"A股观察｜{lead}结构怎么读？",
                f"{wd}收盘｜{lead}量价观察",
                f"A股选股观察｜{lead}待验证",
            ],
            kind="top5",
        )
        return enrich_title_for_search(title, "top5", clip_fn=_clip_wechat_title)
    return enrich_title_for_search(
        _clip_wechat_title(f"A股观察｜{wd}{n}只结构对照"),
        "top5",
        clip_fn=_clip_wechat_title,
    )


def _top5_digest(picks: list[Any], *, trade_date: date) -> str:
    from scripts.tools.wechat_mp_seo import enrich_digest

    names = [str(getattr(p, "name", "") or "") for p in picks[:3] if getattr(p, "name", None)]
    names_s = "、".join(names) if names else "当日标的"
    base = (
        f"收盘综合选股：{names_s} 等 {len(picks)} 只进入结构拆解。"
        f"逐只梳理逻辑、量价与技术位置——信息整理，非荐股。"
    )
    return enrich_digest(base, "top5")


def _dragon_lead_name(dragons: list[dict[str, Any]]) -> tuple[str, str, int | None]:
    if not dragons:
        return "", "", None
    d0 = dragons[0]
    code = str(d0.get("ts_code") or "").split(".")[0].zfill(6)
    name = str(d0.get("name") or "").strip()
    if not name or re.fullmatch(r"\d{6}", name):
        from scripts.tools.portfolio_db import load_stock_names_by_codes

        name = load_stock_names_by_codes([code]).get(code, "")
    short = (name[:4] if name else "龙头") or "龙头"
    boards = d0.get("board_height")
    boards_s = f"{boards}板" if boards is not None else ""
    return short, boards_s, boards if isinstance(boards, int) else None


def _dragon_title(hdr: dict[str, Any], dragons: list[dict[str, Any]], *, trade_date: date) -> str:
    phase = str(hdr.get("phase") or "情绪").strip()
    theme = str(hdr.get("main_theme") or "").strip()[:6]
    lead, boards_s, _ = _dragon_lead_name(dragons)
    wd = _weekday_cn(trade_date)
    from scripts.tools.wechat_mp_evening_align import dragons_title_phase_label

    phase_q = dragons_title_phase_label(phase)
    phase_hint = {
        "退潮": "退潮节奏观察",
        "发酵": "发酵梯队观察",
        "高潮": "高潮波动观察",
        "冰点": "冰点广度观察",
        "分歧": "分歧结构观察",
        "启动": "启动梯队观察",
    }.get(phase, f"{phase[:2]}观察")

    from scripts.tools.wechat_mp_seo import enrich_title_for_search

    title = _pick_clickbait_title(
        [
            f"{phase_q}梯队｜{lead}{boards_s}结构",
            f"A股龙头｜{phase_q}·{lead}{boards_s}观察",
            f"情绪周期·{theme}｜{lead}{boards_s}复盘",
            f"A股龙头复盘｜{phase_hint}·{lead}{boards_s}",
            f"{wd}连板梯队｜{theme}{lead}怎么读？",
        ],
        kind="dragons",
    )
    return enrich_title_for_search(title, "dragons", clip_fn=_clip_wechat_title)


def _dragon_digest(hdr: dict[str, Any], dragons: list[dict[str, Any]], *, trade_date: date) -> str:
    from scripts.tools.wechat_mp_seo import enrich_digest

    phase = hdr.get("phase") or "—"
    theme = hdr.get("main_theme") or "—"
    pool = "、".join(
        str(d.get("name") or d.get("ts_code") or "")[:6] for d in dragons[:3]
    ) or "暂无"
    base = (
        f"今日情绪「{phase}」，主线 {theme}，龙头池 {pool}。"
        "炸板率、情绪参考与次日验证清单——市场结构观察，非交易指引。"
    )
    return enrich_digest(base, "dragons")


# 旧版/测试草稿标题（清理用）
OBSOLETE_DRAFT_TITLE_PATTERNS = (
    re.compile(r"^市场评论\s"),
    re.compile(r"^选股Top5宏观"),
    re.compile(r"^龙头宏观\s"),
    re.compile(r"^宏观复盘\s"),
    re.compile(r"逻辑观察$"),
    re.compile(r"^6月\d+日收盘｜(?!.*[？?！])"),  # 上一版平淡标题
    re.compile(r"^6月\d+日甄选｜(?!.*[？?！])"),
    re.compile(r"^6月\d+日｜退潮｜"),  # 上一版龙头标题
)


def is_obsolete_draft_title(title: str) -> bool:
    from scripts.tools.wechat_mp_client import normalize_draft_text

    title = normalize_draft_text((title or "").strip())
    if not title:
        return False
    if any(p.search(title) for p in OBSOLETE_DRAFT_TITLE_PATTERNS):
        return True
    # 自动脚本旧版（无悬念标点）
    if re.match(r"^6月\d+日(收盘|甄选)｜", title) and not re.search(r"[？?！]", title):
        return True
    if re.match(r"^6月\d+日｜", title) and "｜" in title[6:] and not re.search(r"[？?！]", title):
        return True
    return False

# Top5 公众号正文去掉持仓操作段（SOP 微信摘要里的 2) 结合持仓）
_TOP5_HOLDINGS_SECTION_RE = re.compile(
    r"(?:\n|^)\s*2\)\s*[^\n]*持仓[^\n]*\n.*",
    re.DOTALL,
)


def _author() -> str:
    return os.getenv("WECHAT_MP_AUTHOR", "R2D2")[:16]


def content_source_url_enabled() -> bool:
    """是否写入草稿「阅读原文」链接（默认关，避免暴露看板）。"""
    raw = os.getenv("WECHAT_MP_READ_SOURCE_URL", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _source_url() -> str:
    if not content_source_url_enabled():
        return ""
    url = os.getenv("WECHAT_MP_SOURCE_URL", "").strip()
    if url.lower() in ("0", "false", "no", "off", "none"):
        return ""
    if not url.startswith(("http://", "https://")):
        return ""
    return url[:1024]


def render_article_content_html(
    body_text: str,
    *,
    kind: str | None = None,
    engagement_kind: str | None = None,
    masthead_kind: str | None = None,
    upload_figures: bool = True,
) -> tuple[str, str]:
    """正文区 HTML + 合并后的 body_text（单一免责块）。"""
    from scripts.tools.wechat_mp_masthead import masthead_html
    from scripts.tools.wechat_mp_monetization import (
        polish_for_traffic,
        split_disclaimer,
        strip_inline_disclaimer_blocks,
    )
    from scripts.tools.wechat_mp_public import (
        finalize_public_body_text,
        information_notice_for_kind,
        strip_information_notices,
    )
    from scripts.tools.wechat_mp_rich_html import disclaimer_html

    core, _disc_tail = split_disclaimer(body_text)
    core = strip_inline_disclaimer_blocks(core)
    core = strip_information_notices(core)
    if kind and (kind or "").strip().lower() != "guba":
        core = polish_for_traffic(core, kind=kind, engagement_kind=engagement_kind)
    core = finalize_public_body_text(
        core, kind=kind, engagement_kind=engagement_kind
    )
    if (kind or "").strip().lower() == "hotspot":
        from scripts.tools.wechat_mp_hotspot_polish import reflow_hotspot_body

        core = reflow_hotspot_body(core)
    eng = (engagement_kind or "").strip().lower()
    if eng == "discussion":
        from scripts.tools.wechat_mp_discussion_polish import finalize_discussion_body

        core = finalize_discussion_body(core)
    notice = information_notice_for_kind(kind)
    if notice:
        core = f"{notice}\n\n{core}" if core else notice
    disc_text = disclaimer_for_kind(kind)
    merged_body = f"{core}\n\n{disc_text}" if disc_text else core

    html_kind = (kind or "").strip().lower()
    if (engagement_kind or "").strip().lower() == "discussion":
        html_kind = "discussion"

    body_html = text_to_html(core, upload_figures=upload_figures, article_kind=html_kind)
    disc_html = disclaimer_html(disc_text, kind=kind) if disc_text else ""
    masthead = masthead_html(
        masthead_kind or engagement_kind or kind,
        upload_images=upload_figures,
    )
    content = f"{masthead}{body_html}{disc_html}" if masthead else f"{body_html}{disc_html}"
    return content, merged_body


def _article_shell(
    *,
    title: str,
    digest: str,
    body_text: str,
    upload_figures: bool = True,
    kind: str | None = None,
    engagement_kind: str | None = None,
    masthead_kind: str | None = None,
) -> dict[str, str]:
    from scripts.tools.wechat_mp_monetization import comment_settings
    from scripts.tools.wechat_mp_seo import clip_digest

    content, merged_body = render_article_content_html(
        body_text,
        kind=kind,
        engagement_kind=engagement_kind,
        masthead_kind=masthead_kind,
        upload_figures=upload_figures,
    )
    from scripts.tools.wechat_mp_product import attach_footer_product

    safe_title = title[:32]
    try:
        from scripts.tools.wechat_mp_public import sanitize_public_title

        safe_title = sanitize_public_title(safe_title, kind=kind)[:32]
    except Exception:
        pass

    article: dict[str, str] = {
        "title": safe_title,
        "author": _author(),
        "digest": clip_digest(digest),
        "body_text": merged_body,
        "content": content,
        "article_type": "news",
    }
    if engagement_kind:
        article["engagement_kind"] = engagement_kind
    article.update({k: str(v) for k, v in comment_settings().items()})
    hub = _source_url()
    if not hub and kind:
        try:
            from scripts.tools.wechat_mp_stock_ai_cta import read_source_url_for_kind

            hub = read_source_url_for_kind(kind)
        except Exception:
            hub = ""
    if hub:
        article["content_source_url"] = hub
    from scripts.tools.wechat_mp_product import attach_footer_product

    article = attach_footer_product(article, kind=kind)
    try:
        from scripts.tools.wechat_mp_stock_ai_cta import attach_stock_ai_cta

        article = attach_stock_ai_cta(article, kind=kind)
        if kind and article.get("body_text"):
            content, merged = render_article_content_html(
                article["body_text"],
                kind=kind,
                engagement_kind=engagement_kind,
                masthead_kind=masthead_kind,
                upload_figures=upload_figures,
            )
            article["content"] = content
            article["body_text"] = merged
    except Exception:
        pass
    return article


def _redact_account_hints(line: str) -> str:
    """公众号公开稿弱化个人账户仓位表述。"""
    line = re.sub(r"仓位\s*[\d.]+%[^；。\n]*", "仓位纪律约束", line)
    line = re.sub(r"P[0-5][^\n]*", "", line)
    return line.strip()


def sanitize_top5_public_text(text: str) -> str:
    """去掉 Top5 SOP 摘要中的持仓操作建议，保留个股宏观评述。"""
    if not text:
        return text
    cleaned = _TOP5_HOLDINGS_SECTION_RE.sub("\n", text)
    cleaned = re.sub(
        r"(?:\n|^)\s*3\)\s*[^\n]*风险[^\n]*\n.*",
        "\n",
        cleaned,
        count=1,
        flags=re.DOTALL,
    )
    cleaned = sanitize_public_ai_summary(cleaned)
    lines = [_redact_account_hints(ln) for ln in cleaned.splitlines()]
    cleaned = "\n".join(ln for ln in lines if ln)
    return normalize_wechat_spacing(cleaned.strip())


def build_hotspot_article(
    *,
    edition: str | None = None,
    codex_draft: CodexHotspotDraft | None = None,
) -> dict[str, str]:
    from scripts.tools import wechat_mp_hotspot_article as hotspot_mod
    from scripts.tools.wechat_mp_figures import inject_market_figures
    from scripts.tools.wechat_mp_hotspot_article import (
        build_hotspot_digest,
        build_hotspot_title,
        format_hotspot_trade_label,
        generate_hotspot_body,
        hotspot_social_layout_enabled,
        hotspot_topic_as_discussion,
        resolve_hotspot_trade_date,
        validate_codex_hotspot_body,
    )
    from scripts.tools.wechat_mp_hotspot_polish import finalize_hotspot_body

    ed = edition or "close"
    now = datetime.now(TZ)
    if codex_draft is None:
        raw_body, topics, trade_label = generate_hotspot_body(now=now, edition=ed)
        title_override = ""
        digest_override = ""
        topic_override: dict[str, object] | None = None
    else:
        raw_body = validate_codex_hotspot_body(
            codex_draft.body,
            topic=codex_draft.topic,
        )
        topics = []
        trade_label = format_hotspot_trade_label(
            resolve_hotspot_trade_date(),
            edition=ed,
        )
        title_override = codex_draft.title
        digest_override = codex_draft.digest
        topic_override = codex_draft.as_discussion_topic()
    polished = humanize_mp_text(raw_body)
    from scripts.tools.wechat_mp_hotspot_polish import reflow_hotspot_body

    polished = reflow_hotspot_body(polished)
    primary = topics[0].section_title if topics else (codex_draft.topic if codex_draft else "")
    polished = finalize_hotspot_body(
        polished,
        trade_label=trade_label,
        primary_theme=primary,
    )
    title = title_override or build_hotspot_title(topics, body=polished)
    digest = digest_override or build_hotspot_digest(topics, trade_label=trade_label)

    body_core = polished
    hotspot_mod._LAST_BUILT_HOTSPOT_TOPIC = None
    if hotspot_social_layout_enabled() and (topics or topic_override):
        from scripts.tools.wechat_mp_discussion_figures import (
            discussion_body_figure_target,
            ensure_discussion_cover,
            inject_discussion_figures,
        )
        from scripts.tools.wechat_mp_codex_images import prepare_hotspot_topic_images

        topic_dict = topic_override or hotspot_topic_as_discussion(topics[0])
        hotspot_mod._LAST_BUILT_HOTSPOT_TOPIC = topic_dict
        from scripts.tools.wechat_mp_hotspot_body_cache import save_hotspot_body_cache

        save_hotspot_body_cache(
            topic_dict,
            body_core=polished,
            title=title,
            digest=digest,
            slot_key=(
                os.getenv("WECHAT_MP_HOTSPOT_SLOT_KEY", "").strip()
                or (codex_draft.slot_key if codex_draft else "")
            ),
        )
        figure_target = discussion_body_figure_target()
        figures_required = os.getenv(
            "WECHAT_MP_HOTSPOT_REQUIRE_FIGURES", "1"
        ).strip().lower() not in {"0", "false", "no", "off"}
        prepare_hotspot_topic_images(
            topic_dict,
            body_count=figure_target if figures_required else 0,
        )
        body_core = inject_discussion_figures(polished, topic_dict)
        if body_core.count("[[fig:") < figure_target and figures_required:
            raise RuntimeError(
                f"热点深评正文配图不足 {figure_target} 张可用事件图（当前 {body_core.count('[[fig:')}），"
                f"已拒绝推送：{topic_dict.get('title_zh') or ''}"
            )
        ensure_discussion_cover(topic_dict)
    else:
        body_core = inject_market_figures(polished)

    body = body_core
    from scripts.tools.wechat_mp_seo import attach_publish_hints

    return attach_publish_hints(
        _article_shell(title=title, digest=digest, body_text=body, kind="hotspot"),
        "hotspot",
        theme=primary or None,
    )


def build_sector_article(*, edition: str | None = None) -> dict[str, str]:
    from scripts.tools.wechat_mp_figures import inject_market_figures
    from scripts.tools.wechat_mp_prose import SECTOR_SECTION_TITLES, ensure_blockquote_sections
    from scripts.tools.wechat_mp_sector_article import (
        build_sector_digest,
        build_sector_title,
        format_sector_trade_label,
        generate_sector_research_body,
        resolve_sector_trade_date,
    )
    from scripts.tools.wechat_mp_sector_polish import finalize_sector_body
    from scripts.tools.wechat_mp_sector_stocks import fetch_hot_stock_watch_rows

    ed = edition or "close"
    now = datetime.now(TZ)
    raw_body, themes, _report = generate_sector_research_body(now=now, edition=ed)
    polished = ensure_blockquote_sections(humanize_mp_text(raw_body), SECTOR_SECTION_TITLES)

    trade_label = format_sector_trade_label(
        resolve_sector_trade_date(_report), edition=ed
    )
    primary = themes[0].name if themes else ""
    hot_watch_rows = fetch_hot_stock_watch_rows()
    polished = finalize_sector_body(
        polished,
        trade_label=trade_label,
        primary_theme=primary,
        hot_watch_rows=hot_watch_rows,
    )
    title = build_sector_title(themes, now=now, hot_watch_rows=hot_watch_rows)
    td = now.date()
    try:
        from scripts.tools.selection_results import merge_selection_strategies_df

        td, _, _ = merge_selection_strategies_df()
    except Exception:
        pass
    digest = build_sector_digest(themes, trade_date=td, edition=ed)
    body = f"{inject_market_figures(polished)}\n\n{DISCLAIMER}"
    from scripts.tools.wechat_mp_seo import attach_publish_hints

    return attach_publish_hints(
        _article_shell(title=title, digest=digest, body_text=body, kind="sector"),
        "sector",
        theme=themes[0].name if themes else None,
    )


def build_market_article(*, edition: str | None = None) -> dict[str, str]:
    from scripts.tools.wechat_mp_market_edition import normalize_market_edition
    from scripts.tools.wechat_mp_market_article import generate_researcher_market_body
    from scripts.tools.wechat_mp_market_polish import align_market_title_mood, finalize_market_body
    from scripts.tools.wechat_mp_prose import MARKET_SECTION_TITLES, ensure_blockquote_sections

    ed = normalize_market_edition(edition)
    now = datetime.now(TZ)
    slot = now.strftime("%H:%M")
    raw_body = ensure_blockquote_sections(
        generate_researcher_market_body(now=now, edition=ed),
        MARKET_SECTION_TITLES,
    )
    polished = finalize_market_body(humanize_mp_text(raw_body), edition=ed)
    polished = ensure_blockquote_sections(polished, MARKET_SECTION_TITLES)
    peer_title = _load_last_market_title("close") if ed == "pre" else None
    if peer_title is None and ed == "pre":
        peer_title = os.getenv("WECHAT_MP_PEER_CLOSE_TITLE", "").strip() or None
    title = _market_title(
        polished,
        now=now,
        slot=slot,
        peer_title=peer_title,
        edition=ed,
    )
    title = align_market_title_mood(title, polished)
    from scripts.tools.wechat_mp_figures import inject_market_figures

    body = f"{inject_market_figures(polished)}\n\n{DISCLAIMER}"
    digest = _market_digest(polished, now=now, slot=slot, edition=ed)
    _record_market_title(edition=ed, title=title)
    _save_market_body_cache(
        edition=ed,
        body_text=body,
        title=title,
        digest=digest,
    )
    from scripts.tools.wechat_mp_seo import attach_publish_hints

    return attach_publish_hints(
        _article_shell(title=title, digest=digest, body_text=body, kind="market"),
        "market",
        edition=ed,
    )


def build_news_article(*, peer_market_title: str | None = None) -> dict[str, str]:
    from scripts.tools.wechat_mp_figures import inject_news_figures
    from scripts.tools.wechat_mp_news_article import (
        generate_news_feature_body,
        load_top_news_items,
    )
    from scripts.tools.wechat_mp_prose import NEWS_SECTION_TITLES, ensure_blockquote_sections

    now = datetime.now(TZ)
    items = load_top_news_items()
    if not items:
        from scripts.tools.wechat_mp_news_article import is_hot_stock_news_mode

        if is_hot_stock_news_mode():
            raise RuntimeError(
                "热股要闻生成失败：请确认 OpenCLI 可访问东财热股榜与 7×24 快讯"
            )
        raise RuntimeError("无可用快讯，请先运行 sync_macro_news")
    title = _news_title(items, now=now, peer_title=peer_market_title)
    raw_body = ensure_blockquote_sections(
        generate_news_feature_body(now=now),
        NEWS_SECTION_TITLES,
    )
    from scripts.tools.wechat_mp_news_article import reflow_news_article_body

    body_core = reflow_news_article_body(humanize_mp_text(raw_body))
    from scripts.tools.wechat_mp_news_polish import finalize_news_body

    body_core = finalize_news_body(body_core)
    body = f"{inject_news_figures(body_core)}\n\n{DISCLAIMER}"
    digest = _news_digest(items, now=now)
    from scripts.tools.wechat_mp_seo import attach_publish_hints

    return attach_publish_hints(
        _article_shell(title=title, digest=digest, body_text=body, kind="news"),
        "news",
    )


def build_top5_article() -> dict[str, str]:
    from scripts.tools.selection_watchlist import enrich_pick_names, load_wechat_top5_picks
    from scripts.tools.wechat_mp_top5_article import generate_top5_trader_body

    td, picks, _source = load_wechat_top5_picks()
    picks = enrich_pick_names(picks)
    if not picks:
        raise RuntimeError("选股 Top5 为空，请先运行综合选股任务")

    title = _top5_title(picks, trade_date=td)
    raw_body = generate_top5_trader_body(picks, trade_date=td, pool_source=_source)
    from scripts.tools.wechat_mp_figures import inject_top5_figures
    from scripts.tools.wechat_mp_top5_article import sanitize_top5_analysis_text

    from scripts.tools.wechat_mp_prose import TOP5_SECTION_TITLES, ensure_blockquote_sections

    from scripts.tools.wechat_mp_top5_article import strip_top5_title_echo

    sector_primary = ""
    try:
        from scripts.tools.wechat_mp_evening_align import sector_primary_label

        sector_primary = sector_primary_label()
    except Exception:
        pass

    body = sanitize_top5_analysis_text(
        ensure_blockquote_sections(
            humanize_mp_text(
                strip_top5_title_echo(
                    f"{inject_top5_figures(raw_body)}\n\n{DISCLAIMER}",
                    title=title,
                )
            ),
            TOP5_SECTION_TITLES,
        )
    )
    from scripts.tools.wechat_mp_top5_polish import finalize_top5_body

    body = finalize_top5_body(
        body,
        picks,
        trade_date=td,
        sector_primary=sector_primary,
    )
    digest = _top5_digest(picks, trade_date=td)
    from scripts.tools.wechat_mp_seo import attach_publish_hints

    return attach_publish_hints(
        _article_shell(title=title, digest=digest, body_text=body, kind="top5"),
        "top5",
    )


def build_workspace_article(*, variant: str | None = None) -> dict[str, str]:
    import os

    from scripts.tools.wechat_mp_workspace_article import (
        generate_workspace_overview_body,
        workspace_overview_digest,
        workspace_overview_title,
    )

    from scripts.tools.wechat_format import (
        normalize_wechat_spacing,
        prepare_static_mp_body,
        strip_markdown_for_wechat,
    )
    from scripts.tools.wechat_mp_public import sanitize_public_mp_text

    v = (variant or os.getenv("WECHAT_MP_WORKSPACE_VARIANT", "overview")).strip().lower()
    if v == "english_buddy":
        from scripts.tools.wechat_mp_english_buddy_article import (
            english_buddy_article_digest,
            english_buddy_article_title,
            english_buddy_recommended_hashtags,
            generate_english_buddy_article_body,
        )

        title = english_buddy_article_title()
        raw_body = generate_english_buddy_article_body()
        digest_fn = english_buddy_article_digest
        hashtag_override = english_buddy_recommended_hashtags()
        merged = prepare_static_mp_body(
            f"{raw_body}\n\n{disclaimer_for_kind('workspace')}"
        )
    else:
        title = workspace_overview_title()
        raw_body = generate_workspace_overview_body()
        digest_fn = workspace_overview_digest
        hashtag_override = None
        merged = normalize_wechat_spacing(
            strip_markdown_for_wechat(f"{raw_body}\n\n{disclaimer_for_kind('workspace')}")
        )

    body = sanitize_public_mp_text(merged)
    from scripts.tools.wechat_mp_seo import attach_publish_hints, clip_digest, enrich_digest

    base_digest = digest_fn()
    digest = (
        clip_digest(base_digest)
        if hashtag_override
        else enrich_digest(base_digest, "workspace")
    )
    return attach_publish_hints(
        _article_shell(
            title=title,
            digest=digest,
            body_text=body,
            kind="workspace",
            engagement_kind="english_buddy" if v == "english_buddy" else None,
        ),
        "workspace",
        hashtag_override=hashtag_override,
        engagement_kind="english_buddy" if v == "english_buddy" else None,
    )


_FINANCE_TEMP_VARIANTS = frozenset({"world_cup"})


def build_temp_article(*, variant: str | None = None) -> dict[str, str]:
    from scripts.tools.wechat_mp_temp_article import (
        generate_temp_article_body,
        resolve_temp_variant,
        temp_article_digest,
        temp_article_title,
    )

    from scripts.tools.wechat_format import prepare_static_mp_body
    from scripts.tools.wechat_mp_public import sanitize_public_mp_text

    v = resolve_temp_variant(variant)
    content_kind = "market" if v in _FINANCE_TEMP_VARIANTS else "temp"
    title = temp_article_title(variant=variant)
    raw_body = generate_temp_article_body(variant=variant)
    hashtag_override = None
    if v == "harryputter":
        from scripts.tools.wechat_mp_harryputter_article import (
            harryputter_recommended_hashtags,
        )

        hashtag_override = harryputter_recommended_hashtags()
    merged = prepare_static_mp_body(
        f"{raw_body}\n\n{disclaimer_for_kind(content_kind)}"
    )
    body = sanitize_public_mp_text(merged)
    from scripts.tools.wechat_mp_seo import attach_publish_hints, clip_digest, enrich_digest

    base_digest = temp_article_digest(variant=variant)
    digest = (
        clip_digest(base_digest)
        if hashtag_override
        else enrich_digest(base_digest, content_kind)
    )
    shell_kwargs: dict[str, Any] = {
        "title": title,
        "digest": digest,
        "body_text": body,
        "kind": content_kind,
    }
    if v == "harryputter":
        shell_kwargs["engagement_kind"] = "harryputter"
        shell_kwargs["masthead_kind"] = "harryputter"
    return attach_publish_hints(
        _article_shell(**shell_kwargs),
        content_kind,
        hashtag_override=hashtag_override,
        engagement_kind="harryputter" if v == "harryputter" else None,
    )


def build_dragons_article(*, checklist_slot: str | None = None) -> dict[str, str]:
    from scripts.tools.wechat_mp_dragons_article import (
        generate_dragons_trader_body,
        sanitize_dragons_public_text,
    )

    slot = (checklist_slot or os.getenv("WECHAT_MP_DRAGON_SLOT", "eod")).strip()
    bundle = load_emotion_cycle_checklist(checklist_slot=slot)
    if not bundle:
        bundle = load_emotion_cycle_checklist()
    if not bundle:
        raise RuntimeError(
            "无情绪周期/龙头数据，请先运行 sync_emotion_cycle 或 emotion_cycle_checklist save"
        )

    hdr = bundle["header"]
    dragons = bundle.get("dragon_items") or []
    td_val = hdr.get("trade_date")
    if isinstance(td_val, date):
        td_date = td_val
    else:
        td_date = datetime.fromisoformat(str(td_val)[:10]).date()

    title = _dragon_title(hdr, dragons, trade_date=td_date)
    raw_body = generate_dragons_trader_body(bundle, checklist_slot=slot)
    from scripts.tools.wechat_mp_dragons_article import strip_dragon_title_echo
    from scripts.tools.wechat_mp_dragons_polish import finalize_dragons_body
    from scripts.tools.wechat_mp_figures import inject_dragons_figures
    from scripts.tools.wechat_mp_prose import DRAGON_SECTION_TITLES, ensure_blockquote_sections

    polished = finalize_dragons_body(
        strip_dragon_title_echo(humanize_mp_text(raw_body), title=title),
        hdr=hdr,
    )
    body = sanitize_dragons_public_text(
        ensure_blockquote_sections(
            f"{inject_dragons_figures(polished)}\n\n{DISCLAIMER}",
            DRAGON_SECTION_TITLES,
        )
    )
    digest = _dragon_digest(hdr, dragons, trade_date=td_date)
    from scripts.tools.wechat_mp_seo import attach_publish_hints

    return attach_publish_hints(
        _article_shell(title=title, digest=digest, body_text=body, kind="dragons"),
        "dragons",
        dragon_slot=slot,
        theme=str(hdr.get("main_theme") or "").strip() or None,
        phase=str(hdr.get("phase") or "").strip() or None,
    )


# 定时 evening 两篇：热股 news（10 条）+ hotspot；dragons/sector/market 仅手动
DAILY_DRAFT_KINDS = ("hotspot", "sector", "dragons", "news", "top5", "workspace")
DRAFT_KINDS = (*DAILY_DRAFT_KINDS, "market", "news", "temp", "guba", "tv_review")


def build_article(
    kind: str,
    *,
    peer_market_title: str | None = None,
    edition: str | None = None,
    variant: str | None = None,
    codex_draft: CodexHotspotDraft | None = None,
) -> dict[str, str]:
    k = kind.strip().lower()
    if k in {"hotspot", "hot_topic", "topic_pulse"}:
        return build_hotspot_article(
            edition=edition or "close",
            codex_draft=codex_draft,
        )
    if k in {"sector", "industry", "theme"}:
        return build_sector_article(edition=edition or "close")
    if k == "market":
        return build_market_article(edition=edition)
    if k in {"news", "kuaixun", "macro_news"}:
        return build_news_article(peer_market_title=peer_market_title)
    if k == "top5":
        return build_top5_article()
    if k in {"dragons", "dragon", "leaders"}:
        return build_dragons_article()
    if k in {"workspace", "tech", "lab", "dev"}:
        return build_workspace_article(variant=variant)
    if k in {"temp", "adhoc", "extra"}:
        return build_temp_article(variant=variant)
    if k == "guba":
        return build_guba_article(edition=edition or "close")
    if k in {"tv_review", "tv", "film", "movie"}:
        from scripts.tools.wechat_mp_tv_review_article import build_tv_review_article

        return build_tv_review_article()
    raise ValueError(f"未知 kind={kind!r}，可选: {', '.join(DRAFT_KINDS)}")


def build_guba_article(*, edition: str | None = "close") -> dict[str, str]:
    from scripts.tools.wechat_mp_guba_sector import build_guba_draft_article

    return build_guba_draft_article(edition=edition)
