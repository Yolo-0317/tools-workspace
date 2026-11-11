#!/usr/bin/env python3
"""公众号要闻精选稿：关注度 Top10，每条附 AI 点评（独立于 A 股盘面稿）。"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.deepseek_client import (
    call_wechat_mp_llm,
    is_wechat_mp_llm_configured,
)
from scripts.tools.news_db import pick_top_news_by_attention
from scripts.tools.news_sentiment import sentiment_label
from scripts.tools.wechat_mp_prose import NEWS_SECTION_TITLES, mp_section_header
from scripts.tools.wechat_mp_monetization import monetization_prompt_block
from scripts.tools.wechat_mp_public import RESEARCHER_VOICE_RULE

TZ = ZoneInfo("Asia/Shanghai")

SECTION_LIST = mp_section_header("要闻精选")


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


def summary_max_len() -> int:
    return _env_int("WECHAT_MP_NEWS_SUMMARY_MAX", 250)


def summary_min_len() -> int:
    return _env_int("WECHAT_MP_NEWS_SUMMARY_MIN", 230)


def ai_comment_target_chars() -> tuple[int, int]:
    lo = _env_int("WECHAT_MP_NEWS_AI_MIN", 120)
    hi = _env_int("WECHAT_MP_NEWS_AI_MAX", 220)
    if hi < lo:
        hi = lo + 40
    return lo, hi


def news_enriched_llm_enabled() -> bool:
    """要闻小标题/摘要/AI点评是否走 LLM。默认开（与 evening 写稿 LLM_BACKEND 解耦）。"""
    return _env_bool("WECHAT_MP_NEWS_AI_LLM", True)


def news_ai_llm_backend() -> str:
    """要闻 AI 点评固定使用公众号 Codex 写稿后端。"""
    return "codex"


def is_news_ai_llm_configured() -> bool:
    return is_wechat_mp_llm_configured()


def is_hot_stock_news_mode() -> bool:
    """热股 TopN × 快讯匹配（evening / weekend 批次由 wechat_mp_draft_batch 设置）。"""
    return _env_bool("WECHAT_MP_HOT_STOCK_NEWS", False) or _env_bool(
        "WECHAT_MP_WEEKEND_NEWS", False
    )


def is_weekend_news_batch() -> bool:
    """休市日单篇 news 批次（导语/标题用周末句式）。"""
    return os.getenv("WECHAT_MP_NEWS_BATCH", "").strip() == "weekend"


def is_weekend_news_mode() -> bool:
    """兼容旧名：仅表示休市日 news 批次，勿用于选题逻辑。"""
    return is_weekend_news_batch()


def news_pick_params() -> tuple[int, int, int, bool]:
    """返回 (limit, pool_limit, hours, prefer_stock)。"""
    if is_hot_stock_news_mode():
        from scripts.tools.wechat_mp_weekend_news import (
            hot_stock_news_hours,
            weekend_hot_stock_count,
            weekend_kuaixun_pool_limit,
        )

        return (
            weekend_hot_stock_count(),
            weekend_kuaixun_pool_limit(),
            hot_stock_news_hours(),
            True,
        )
    return (
        _env_int("WECHAT_MP_NEWS_TOP", 10),
        _env_int("WECHAT_MP_NEWS_POOL_LIMIT", 80),
        _env_int("WECHAT_MP_NEWS_HOURS", 36),
        False,
    )


def fetch_news_engagement(*, limit: int = 80) -> dict[str, dict[str, int]]:
    """东财快讯列表评论数（OpenCLI，失败则返回空 dict）。"""
    if _env_bool("WECHAT_MP_NEWS_SKIP_ENGAGEMENT", False):
        return {}
    try:
        from scripts.tools.fetch_eastmoney_quotes import fetch_kuaixun_engagement_opencli

        return fetch_kuaixun_engagement_opencli(limit=limit)
    except Exception:  # noqa: BLE001
        return {}


def load_top_news_items(*, limit: int | None = None) -> list[dict[str, Any]]:
    lim, pool_limit, hours, prefer_stock = news_pick_params()
    if limit is not None:
        lim = limit
    if is_hot_stock_news_mode():
        try:
            from scripts.tools.wechat_mp_weekend_news import load_weekend_hot_stock_news_items

            items = load_weekend_hot_stock_news_items(top_n=lim)
            if items:
                return items
        except Exception as exc:  # noqa: BLE001
            import sys

            print(f"⚠️ 周末热股快讯 OpenCLI 失败，回退库内快讯: {exc}", file=sys.stderr)
    engagement = fetch_news_engagement(limit=pool_limit)
    items = pick_top_news_by_attention(
        limit=lim,
        pool_limit=pool_limit,
        hours=hours,
        engagement=engagement,
        prefer_stock=prefer_stock,
    )
    if items:
        return items
    return pick_top_news_by_attention(
        limit=lim,
        pool_limit=pool_limit,
        hours=hours,
        engagement=None,
        prefer_stock=prefer_stock,
    )


def _clip_text(text: str, *, max_len: int) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return "（暂无摘要）"
    if len(cleaned) <= max_len:
        return cleaned
    cut = cleaned[: max_len - 1]
    if "，" in cut[-20:]:
        cut = cut.rsplit("，", 1)[0] + "…"
    else:
        cut = cut + "…"
    return cut


def _strip_template_news_title(title: str, *, stock: str = "") -> str:
    raw = (title or "").strip()
    if stock and raw.startswith(f"{stock}｜"):
        raw = raw.split("｜", 1)[1].strip()
    raw = re.sub(r"^周五人气关注[：:]\s*", "", raw)
    raw = re.sub(r"^周五人气关注", "", raw)
    return raw.strip()


def news_display_headline(item: dict[str, Any], *, max_len: int = 28) -> str:
    """列表小标题：优先快讯标题，周末合成稿走盘面规则。"""
    stock = str(item.get("matched_stock_name") or "").strip()
    if item.get("synthetic") and stock:
        from scripts.tools.wechat_mp_hot_stocks import HotStockRow
        from scripts.tools.wechat_mp_weekend_news import synthetic_display_title

        row = HotStockRow(
            rank=int(item.get("matched_stock_rank") or 0),
            code=str(item.get("matched_stock_code") or ""),
            name=stock,
            change_pct=float(item.get("matched_stock_change_pct") or 0.0),
        )
        return _clip_text(synthetic_display_title(row), max_len=max_len)

    raw = _strip_template_news_title(str(item.get("title") or ""), stock=stock)
    if not raw and stock:
        return stock
    headline = _clip_text(raw, max_len=max_len)
    if stock and stock not in headline and len(headline) <= 18:
        headline = _clip_text(f"{stock}：{headline}", max_len=max_len + 4)
    return headline


def _raw_item_blob(item: dict[str, Any]) -> str:
    title = (item.get("title") or "").strip()
    summary = (item.get("summary") or "").strip()
    if summary and summary != title:
        return f"{title}。{summary}" if not summary.startswith(title) else summary
    return title


def _ensure_min_length(
    text: str,
    *,
    min_len: int,
    max_len: int,
    pad_sentences: tuple[str, ...],
) -> str:
    out = _clip_text(text, max_len=max_len)
    idx = 0
    while len(out) < min_len and idx < len(pad_sentences):
        out = _clip_text(f"{out}{pad_sentences[idx]}", max_len=max_len)
        idx += 1
    return out


_SUMMARY_PAD = (
    "从交易层面看，市场往往先定价预期、再等待事实验证，短线波动不一定等于趋势反转。",
    "对 A 股而言，更需观察相关板块是否出现放量共振，以及是否与当日主线方向一致。",
    "若盘中仅为脉冲式上冲，通常说明资金仍在等待进一步信息确认，不宜过度外推。",
)


def _summary_pad_sentences(item: dict[str, Any], *, slot: int = 0) -> tuple[str, ...]:
    """垫句按条目/热股差异化，避免 10 条快讯摘要尾段雷同。"""
    if item.get("matched_stock_name"):
        name = str(item.get("matched_stock_name") or "").strip()
        rank = int(item.get("matched_stock_rank") or slot + 1)
        chg = float(item.get("matched_stock_change_pct") or 0.0)
        pads = (
            f"榜单第{rank}位{name}，收盘涨跌约{chg:+.1f}%，人气与基本面催化宜分开看。",
            "下一交易日重点盯竞价承接与首小时量比，别单凭排名推演趋势。",
            "若板块龙头走弱而该股仍高位换手，更像短线情绪而非板块共振。",
        )
    else:
        pads = _SUMMARY_PAD
    n = len(pads)
    start = slot % n
    return pads[start:] + pads[:start]


def _hot_stock_fallback_comment(item: dict[str, Any]) -> str:
    """热股/合成稿：按股名、榜位、涨跌幅写差异化 AI 点评。"""
    name = str(item.get("matched_stock_name") or "").strip() or "标的"
    code = str(item.get("matched_stock_code") or "").strip()
    rank = int(item.get("matched_stock_rank") or 0)
    chg = float(item.get("matched_stock_change_pct") or 0.0)
    ctx = None
    try:
        from scripts.tools.wechat_mp_weekend_news import build_news_time_context

        ctx = build_news_time_context()
        verify = ctx.verify_auction_phrase
    except Exception:  # noqa: BLE001
        verify = "下一交易日竞价"

    if chg >= 9.5:
        perf = "收盘涨停级，榜单热度偏高"
    elif chg >= 5:
        perf = f"收涨约{chg:+.1f}%，弹性不小"
    elif chg <= -5:
        perf = f"收跌约{chg:.1f}%，人气与走势背离需警惕"
    elif chg > 0:
        perf = f"小幅收涨约{chg:+.1f}%"
    elif chg < 0:
        perf = f"小幅回落约{chg:.1f}%"
    else:
        perf = "高位换手，方向待竞价确认"

    angle = _infer_news_angle(item)
    watch = str(angle.get("watch") or "龙头竞价与首小时成交量")
    variants = (
        f"{name}（{code}）人气第{rank}位，{perf}。{verify}看它能否高开不回补，首小时量比是否钉住人气。",
        f"榜内盯{name}：{perf}，别只盯排名。验证点看{watch}，{verify}强弱说了算。",
        f"人气第{rank}的{name}，{perf}。若{verify}低开放量，说明榜单热度在退潮；高开缩量则多看半小时。",
    )
    idx = sum(ord(c) for c in (code or name)) % len(variants)
    return variants[idx]


def _warn_duplicate_news_copy(enriched: list[tuple[str, str, str]]) -> None:
    """同批摘要/点评高度雷同时在 stderr 告警（推稿前人工可察）。"""
    import sys

    if len(enriched) < 2:
        return
    summaries = [s.strip() for _, s, _ in enriched if s.strip()]
    comments = [a.strip() for _, _, a in enriched if a.strip()]
    for label, texts in (("摘要", summaries), ("AI点评", comments)):
        if len(texts) < 2:
            continue
        dup = max(texts.count(t) for t in set(texts))
        if dup >= 3:
            print(
                f"⚠️ news 快讯{label}重复：{dup}/{len(texts)} 条完全相同，"
                "请检查 OpenCLI 快讯池或 WECHAT_MP_NEWS_AI_LLM",
                file=sys.stderr,
            )
            break
        tails = [t[-80:] for t in texts if len(t) >= 80]
        if len(tails) >= 3:
            tail_dup = max(tails.count(t) for t in set(tails))
            if tail_dup >= 3:
                print(
                    f"⚠️ news 快讯{label}尾段重复：{tail_dup} 条后 80 字相同",
                    file=sys.stderr,
                )
                break

# 读者正文禁止出现的流水线/后台术语（周末稿尤甚）
_NEWS_READER_META_BANNED = (
    "周末未匹配到该股专属 7×24 快讯",
    "周末未匹配到该股专属",
    "未匹配到该股专属",
    "未匹配到该股",
    "未匹配到",
    "专属 7×24",
    "专属快讯",
    "7×24 快讯",
    "本条按「人气股 + 休市舆情」占位",
    "人气股 + 休市舆情",
    "休市舆情」占位",
    "流水线",
    "占位：",
    "占位，",
    "非实时盘中排名",
    "榜单为休市前快照",
    "勿写「周末仍登榜",
)

# AI 点评套话 — LLM 与 fallback 均不得出现（后处理剔除）
_AI_COMMENT_BANNED = (
    "情绪定价",
    "结构分化",
    "主题脉冲",
    "梯度扩散",
    "二次定价",
    "向后看建议跟踪",
    "向后看宜跟踪",
    "结合成交额与梯队",
    "梯队完整性",
    "若与当前主线共振",
    "若仅为海外映射",
    "对 A 股而言",
    "市场往往先交易预期",
    "再等待数据或政策细节验证",
    "不宜过度外推",
    "短线资金往往会先做",
    "对指数层面更多影响结构而非方向",
    "仅供参考",
    "综上所述",
    "值得注意的是",
    "从交易层面看",
    "风险偏好",
    "映射交易",
)


def _sanitize_news_reader_meta(text: str, *, ctx: Any | None = None) -> str:
    """去掉「未匹配/占位/7×24」等后台话术，避免漏进读者正文。"""
    out = (text or "").strip()
    control_line_re = re.compile(r"^\[\[(?:fig|hl|cta):.*\]\]$")
    if any(control_line_re.match(line.strip()) for line in out.splitlines()):
        blocks: list[str] = []
        prose_lines: list[str] = []

        def flush_prose() -> None:
            prose = "\n".join(prose_lines).strip()
            prose_lines.clear()
            if prose:
                cleaned = _sanitize_news_reader_meta(prose, ctx=ctx)
                if cleaned:
                    blocks.append(cleaned)

        for line in out.splitlines():
            stripped = line.strip()
            if control_line_re.match(stripped):
                flush_prose()
                blocks.append(stripped)
            else:
                prose_lines.append(line)
        flush_prose()
        return "\n\n".join(blocks)
    for phrase in _NEWS_READER_META_BANNED:
        out = out.replace(phrase, "")
    out = re.sub(r"周末未匹配[^。；！？\n]*[。；]?", "", out)
    out = re.sub(r"未匹配到[^。；！？\n]*[。；]?", "", out)
    out = re.sub(r"本条按[^。；！？\n]*占位[：:]?", "", out)
    out = re.sub(r"专属\s*7×24[^。；！？\n]*", "", out)
    from scripts.tools.wechat_mp_public import sanitize_reader_data_gap

    out = sanitize_reader_data_gap(out)
    out = re.sub(r"[；;，,]{2,}", "，", out)
    out = re.sub(r"\s+", "", out)
    out = re.sub(r"^[，。；、]+|[，。；、]+$", "", out)
    out = out.strip()
    if ctx is not None:
        from scripts.tools.wechat_mp_weekend_news import fix_stale_auction_weekday

        out = fix_stale_auction_weekday(out, ctx)
    return out


def _sanitize_ai_comment(text: str) -> str:
    """去掉模板套话，合并重复标点。"""
    out = _sanitize_news_reader_meta(text)
    for phrase in _AI_COMMENT_BANNED:
        out = out.replace(phrase, "")
    out = re.sub(r"[；;，,]{2,}", "，", out)
    out = re.sub(r"\s+", "", out)
    out = re.sub(r"^[，。；、]+|[，。；、]+$", "", out)
    return out.strip()


def _infer_news_angle(item: dict[str, Any]) -> dict[str, str]:
    """从标题推断板块/验证点，供 prompt 提示与 fallback 差异化。"""
    title = str(item.get("title") or "")
    tag = sentiment_label(str(item.get("sentiment") or "neutral"))

    if any(kw in title for kw in ("黄金", "金饰", "金价", "贵金属")):
        return {
            "sectors": "黄金开采、珠宝零售（老凤祥/周大生）、赤峰黄金",
            "watch": "沪金主力、黄金股竞价、珠宝股毛利率预期",
            "stretch": "零售端降价和矿端利润是两回事，别混成一个故事。",
            "comments": (
                f"金饰终端降价往往先伤珠宝零售毛利，矿端要看金价本身怎么走。{tag}口径下，"
                f"盯老凤祥、周大生竞价，若低开放量，说明市场在算中报压力。",
                f"金价回落时赤峰黄金、山东黄金弹性更大。{tag}背景下，"
                f"看沪金主力是否企稳，黄金股才谈得上「利空出尽」。",
            ),
        }
    if any(kw in title for kw in ("伊朗", "中东", "霍尔木兹", "以军", "原油", "油价", "OPEC")):
        return {
            "sectors": "油服、炼化、航运（油运）、黄金",
            "watch": "翌日布伦特波动、油服龙头竞价强弱、航运指数",
            "stretch": "若油服龙头竞价走弱，多半是一日游情绪，别急着追。",
            "comments": (
                f"地缘推升油价预期，A股先动的是油服和油运，黄金往往同步。{tag}口径下，"
                f"盯中海油服、中曼石油这类能否带量，而不是泛泛看「能源板块」。"
                f"验证点：翌日 Brent 是否站稳、油服是否高开低走。",
                f"这类消息对指数权重不大，但会挤出部分资金去博弈油服。{tag}背景下，"
                f"中远海能、招商南油若放量，说明资金当真；若只有小票脉冲，持续性存疑。",
            ),
        }
    if any(
        kw in title
        for kw in ("半导体", "芯片", "存储", "AI", "华为", "英伟达", "费城半导体", "算力", "HBM")
    ):
        return {
            "sectors": "设备/材料/封测、算力链、科创50",
            "watch": "龙头（寒武纪/中芯国际等）能否带量、科创与主板是否背离",
            "stretch": "设备端往往比设计端先反应，别只看概念小票。",
            "comments": (
                f"半导体快讯通常先打设备和材料，设计端滞后。{tag}消息若属实，"
                f"看北方华创、中微公司能否放量，比扫一堆「芯片概念」更有信息量。",
                f"算力/AI 链和费城半导体指数联动时，科创50弹性最大。{tag}口径下，"
                f"盯寒武纪、海光信息是否引领，若龙头趴窝，跟风票多半一日游。",
            ),
        }
    if any(kw in title for kw in ("美联储", "职位", "非农", "CPI", "降息", "美债", "美元")):
        return {
            "sectors": "北向敏感的白电/消费、券商、黄金",
            "watch": "北向净流入、10Y 美债、美元指数",
            "stretch": "利率预期变时，券商往往比银行先动。",
            "comments": (
                f"海外利率叙事影响的是外资风险偏好，不是立刻改 A 股基本面。{tag}信号下，"
                f"先看北向是否回流、10Y 美债是否拐头；券商若没反应，说明市场在观望。",
                f"降息/非农类消息，黄金和利率敏感消费常抢先定价。{tag}背景下，"
                f"别被单条快讯带着调仓，等收盘看北向与美债是否同向验证。",
            ),
        }
    if any(kw in title for kw in ("央行", "降准", "降息", "MLF", "LPR", "流动性")):
        return {
            "sectors": "券商、地产链、高股息",
            "watch": "银行间利率、券商板块、地产政策配套",
            "stretch": "宽货币 alone 不够，要看有没有宽信用跟进。",
            "comments": (
                f"货币政策快讯，券商和地产链往往最先表态。{tag}口径下，"
                f"若只有降准传闻而无配套，脉冲后容易回落；盯券商能否持续放量。",
                f"流动性预期升温时，高股息有时会被抽血去搏弹性。{tag}消息下，"
                f"看地产链龙头（保利/万科系）是否跟涨，比看指数更有意义。",
            ),
        }
    if any(kw in title for kw in ("涨停", "连板", "龙头", "妖股", "情绪")):
        return {
            "sectors": "当日主线、连板梯队",
            "watch": "空间板高度、炸板率、昨日涨停表现",
            "stretch": "情绪票看梯队，不看单条新闻本身。",
            "comments": (
                f"情绪类快讯要对照当日连板梯队看，别孤立解读。{tag}口径下，"
                f"盯空间板是否拓展、炸板率是否抬升，这比新闻字面更重要。",
                f"龙头/连板消息往往滞后于盘面，{tag}背景下更该看「谁封住了、谁掉队」，"
                f"而不是追新闻里提到的名字。",
            ),
        }
    if any(
        kw in title
        for kw in ("市值", "红了", "绿了", "跑赢", "跑输", "涨跌家数", "全A", "权重股", "指数")
    ):
        return {
            "sectors": "上证50/沪深300权重、宽基指数、北向敏感蓝筹",
            "watch": "涨跌家数、权重与中小盘是否背离、成交额是否放大",
            "stretch": "权重拉升和普涨不是一回事，别看指数红就追中小票。",
            "comments": (
                f"指数型热搜要先拆「权重贡献」还是「普涨」。{tag}讨论下，"
                f"若涨家数未跟上指数，多半是少数权重股托底；盯全A涨跌比是否改善。",
                f"市值榜/权重股话题，资金往往在大盘蓝筹和题材之间切换。{tag}口径下，"
                f"看沪深300与中证1000是否同向，背离时别用指数颜色代替个股结构。",
            ),
        }
    if any(kw in title for kw in ("业绩", "预增", "预亏", "净利润", "营收", "年报", "季报")):
        return {
            "sectors": "公告涉及个股及同赛道对标",
            "watch": "是否超预期、同板块是否跟涨",
            "stretch": "业绩票看对标，不看板块指数。",
            "comments": (
                f"业绩快讯先读「超/不及预期」，再看同赛道对标动不动。{tag}公告下，"
                f"若只有个股涨、同行趴窝，多半是独立逻辑而非板块行情。",
                f"预增/预亏类消息，市场常提前定价；{tag}口径下，"
                f"开盘 15 分钟看是否高开低走，比收盘再看更有用。",
            ),
        }
    return {
        "sectors": "与标题主题最直接相关的细分方向",
        "watch": "相关龙头竞价与首小时成交量",
        "stretch": "单条快讯很少改趋势，先看龙头认不认。",
        "comments": (
            f"先把标题里的主体对应到具体细分，别泛化成「相关概念」。{tag}消息下，"
            f"找板块里谁最先涨停或放量，那才是真正的资金态度。",
            f"快讯再{tag}，也要看盘面是否买单：相关龙头竞价强弱、"
            f"首小时能否站稳均价，比复述新闻本身有价值。",
        ),
    }


def _pick_fallback_comment(item: dict[str, Any]) -> str:
    if item.get("matched_stock_name"):
        return _hot_stock_fallback_comment(item)
    angle = _infer_news_angle(item)
    comments = angle.get("comments") or ()
    if not comments:
        return ""
    title = str(item.get("title") or "")
    idx = sum(ord(c) for c in title) % len(comments)
    return str(comments[idx])


def _stretch_ai_comment(item: dict[str, Any], text: str) -> str:
    """字数不足时用本条线索补一句实质内容，不用通用垫句。"""
    lo, hi = ai_comment_target_chars()
    base = (text or "").strip()
    if len(base) >= lo:
        return base
    angle = _infer_news_angle(item)
    stretch = str(angle.get("stretch") or "")
    watch = str(angle.get("watch") or "")
    addon = stretch if stretch and stretch not in base else f"盯：{watch}。"
    if addon in base:
        return base
    sep = "。" if base and not base.endswith(("。", "！", "？")) else ""
    merged = _clip_text(f"{base}{sep}{addon}", max_len=hi + 10)
    return merged if len(merged) > len(base) else base


def _finalize_summary(
    text: str,
    item: dict[str, Any],
    *,
    ctx: Any | None = None,
    slot: int = 0,
) -> str:
    max_len = summary_max_len()
    min_len = summary_min_len()
    tag = sentiment_label(str(item.get("sentiment") or "neutral"))
    base = _sanitize_news_reader_meta(text, ctx=ctx)
    pads = _summary_pad_sentences(item, slot=slot)
    base = _ensure_min_length(
        base,
        min_len=min_len,
        max_len=max_len,
        pad_sentences=pads,
    )
    if len(base) >= min_len:
        return base
    if item.get("synthetic"):
        return _clip_text(base, max_len=max_len)
    title = (item.get("title") or "").strip()
    return _ensure_min_length(
        f"{title}。该消息归类为{tag}，",
        min_len=min_len,
        max_len=max_len,
        pad_sentences=pads,
    )


def _finalize_ai(text: str, item: dict[str, Any], *, ctx: Any | None = None) -> str:
    lo, hi = ai_comment_target_chars()
    out = _sanitize_ai_comment(text)
    if ctx is not None:
        from scripts.tools.wechat_mp_weekend_news import fix_stale_auction_weekday

        out = fix_stale_auction_weekday(out, ctx)
    out = _clip_text(out, max_len=hi + 10)
    if len(out) < lo:
        out = _stretch_ai_comment(item, out)
    if len(out) < max(60, lo // 2):
        out = _sanitize_ai_comment(_pick_fallback_comment(item))
        out = _stretch_ai_comment(item, out)
    return _clip_text(out, max_len=hi + 10)


def _fallback_summary(item: dict[str, Any], *, slot: int = 0) -> str:
    title = (item.get("title") or "").strip()
    extra = (item.get("summary") or "").strip()
    if item.get("synthetic") and extra:
        return _finalize_summary(extra, item, slot=slot)
    blob = _raw_item_blob(item)
    if extra and title and title in extra and len(extra) >= summary_min_len() - 40:
        return _finalize_summary(extra, item, slot=slot)
    tag = sentiment_label(str(item.get("sentiment") or "neutral"))
    padded = (
        f"{title}。{extra} " if extra and extra != title and not extra.startswith(title) else f"{title}。"
        f"该消息归类为{tag}，市场通常先交易预期、后验证事实。"
        f"若后续有更多细节披露，相关板块可能出现二次定价；"
        f"在官方信息未完全落地前，宜降低单条快讯对仓位的直接驱动。"
    )
    return _finalize_summary(
        padded if len(padded) >= len(blob) else blob,
        item,
        slot=slot,
    )


def _fallback_ai_comment(item: dict[str, Any], *, summary: str) -> str:
    return _pick_fallback_comment(item)


def _parse_enriched_blocks(text: str, *, expected: int) -> list[tuple[str, str, str]]:
    headlines: dict[int, str] = {}
    summaries: dict[int, str] = {}
    comments: dict[int, str] = {}
    current: int | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        title_m = re.match(r"^(\d+)\.\s*小标题[：:]\s*(.+)$", line)
        if title_m:
            current = int(title_m.group(1))
            headlines[current] = title_m.group(2).strip()
            continue
        title_only = re.match(r"^小标题[：:]\s*(.+)$", line)
        if title_only and current is not None:
            headlines[current] = title_only.group(1).strip()
            continue
        head = re.match(r"^(\d+)\.\s*摘要[：:]\s*(.*)$", line)
        if head:
            current = int(head.group(1))
            rest = head.group(2).strip()
            if rest:
                summaries[current] = rest
            continue
        summary_only = re.match(r"^摘要[：:]\s*(.+)$", line)
        if summary_only and current is not None:
            summaries[current] = summary_only.group(1).strip()
            continue
        ai_m = re.match(r"^AI点评[：:]\s*(.+)$", line)
        if ai_m and current is not None:
            comments[current] = ai_m.group(1).strip()
            continue
        if current is not None and current in summaries and current not in comments:
            summaries[current] = f"{summaries[current]}{line}"
    out: list[tuple[str, str, str]] = []
    for i in range(1, expected + 1):
        out.append((headlines.get(i, ""), summaries.get(i, ""), comments.get(i, "")))
    return out


def _finalize_headline(text: str, item: dict[str, Any], *, ctx: Any | None = None) -> str:
    headline = _sanitize_news_reader_meta((text or "").strip(), ctx=ctx)
    headline = re.sub(r"^周五人气关注[：:]\s*", "", headline)
    if len(headline) < 6 or "周五人气关注" in headline:
        headline = news_display_headline(item)
    return _clip_text(headline, max_len=30)


def generate_enriched_news_copy(
    items: list[dict[str, Any]],
) -> list[tuple[str, str, str]]:
    """为每条快讯生成小标题 + 扩写摘要 + AI 点评。返回 [(headline, summary, ai_comment), ...]。"""
    if not items:
        return []

    from scripts.tools.wechat_mp_weekend_news import build_news_time_context

    time_ctx = build_news_time_context()
    verify_example = (
        f"达实智能涨停占榜一，{time_ctx.verify_auction_phrase}怎么看"
    )

    fallbacks = [
        (
            news_display_headline(it),
            _fallback_summary(it, slot=idx - 1),
            _finalize_ai(_fallback_ai_comment(it, summary=""), it),
        )
        for idx, it in enumerate(items, start=1)
    ]
    if not news_enriched_llm_enabled() or not is_news_ai_llm_configured():
        return fallbacks

    smin = summary_min_len()
    smax = summary_max_len()
    lo, hi = ai_comment_target_chars()
    banned_sample = "、".join(_AI_COMMENT_BANNED[:8]) + "等"
    briefs = []
    for idx, it in enumerate(items, start=1):
        tag = sentiment_label(str(it.get("sentiment") or "neutral"))
        angle = _infer_news_angle(it)
        stock_line = ""
        if it.get("matched_stock_name"):
            anchor = it.get("hot_stock_anchor_label") or "上一交易日收盘"
            rank = it.get("matched_stock_rank") or "—"
            name = it.get("matched_stock_name")
            code = it.get("matched_stock_code")
            if it.get("synthetic"):
                stock_line = (
                    f"   人气榜第{rank}位：{name}（{code}）；{anchor}快照，暂无该股单独快讯标题。\n"
                    f"   {time_ctx.llm_date_rule}\n"
                    "   按「休市/盘面观察」写：资金面 + 下一交易日竞价/首小时验证；"
                    "禁止出现「未匹配/占位/7×24/专属快讯/流水线」等后台用语。\n"
                )
            else:
                stock_line = (
                    f"   对应人气榜第{rank}位 {name}（{code}，{anchor}）。\n"
                    "   摘要/点评须点名该股或同赛道验证点；"
                    "禁止写「未匹配/占位/7×24」等后台术语。\n"
                )
        briefs.append(
            f"{idx}. [{tag}] 标题：{it.get('title', '')}\n"
            f"{stock_line}"
            f"   素材：{_clip_text(_raw_item_blob(it), max_len=480)}\n"
            f"   联想（仅供展开，勿照抄）：{angle['sectors']}；验证：{angle['watch']}"
        )
    search_seo = ""
    if is_hot_stock_news_mode():
        search_seo = (
            "\n## 搜一搜（热股清单稿）\n"
            "- 摘要前 20 字尽量含热股名或 A股；勿一句塞 3 个热词\n"
            "- AI点评写清「该股/同赛道下一交易日盯什么」\n"
            "- 严禁向读者暴露采编后台：未匹配、占位、7×24、专属快讯、流水线、快照锚点等\n"
        )
    headline_rule = ""
    if is_hot_stock_news_mode():
        headline_rule = (
            "\n## 小标题（每条 — 读者列表项标题，最先写）\n"
            "- 8-22 字，概括本条事件或验证点；须含热股名\n"
            "- 有快讯素材：提炼快讯核心，勿照抄长标题\n"
            f"- 无快讯（休市/收盘观察）：写盘面+下一交易日验证，如「{verify_example}」\n"
            "- 严禁「周五人气关注」等模板句\n"
        )
    else:
        headline_rule = (
            "\n## 小标题（每条）\n"
            "- 8-22 字，概括快讯核心；可含主体公司/板块名\n"
        )

    prompt = f"""为下列 {len(items)} 条要闻各写「小标题」「扩写摘要」和「AI点评」。
{search_seo}{headline_rule}
{RESEARCHER_VOICE_RULE}

## 时间口径（全文遵守）
{time_ctx.llm_date_rule}

## 摘要（每条）
- 长度 {smin}-{smax} 字，3-4 句
- 写清：发生了什么、关键主体/数据/时间、与 A 股的可能关联
- 仅基于素材，勿编造未给出的数字或结论

## AI点评（每条 — 读者最看重，务必走心）
- 长度 {lo}-{hi} 字，2-4 句，密度优先，不必凑字数
- 像盘中给同事发微信：说清「这条会动谁、为什么、明天/下一交易日盯什么」
- **至少 1 句点宏观/政策或产业链传导背景**（素材有则写，无则写行业机制，勿编造）
- **至少 1 句明确主观判断**（可用「我们认为」「值得关注的是」），须可被下一交易日验证
- 可点名细分板块或产业链环节，可写具体验证动作（竞价、龙头、首小时成交量）
- 禁止买卖建议；禁止 emoji；禁止评论数/阅读量
- 每条写法必须有变化，禁止填空式「第1句板块、第2句机制、第3句验证」
- 严禁套话：{banned_sample}

## 输出格式（严格，每条三行；**每条单独占一组，禁止同一行写「1. … 2. …」**）
1. 小标题：……
   摘要：……
   AI点评：……

2. 小标题：……
   摘要：……
   AI点评：……

快讯素材：
{chr(10).join(briefs)}
{monetization_prompt_block("news")}"""

    try:
        raw = call_wechat_mp_llm(
            [
                {
                    "role": "system",
                    "content": (
                        "你是有实战经验的 A 股研究员，写给懂行的老读者。"
                        "AI点评要有具体判断和可验证的观察，拒绝空话和模板句。"
                        "禁止出现采编后台用语（未匹配、占位、7×24、专属快讯等）。"
                        "只输出编号「小标题 / 摘要 / AI点评」行，不要 markdown 或多余解释。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=6000,
        )
        parsed = _parse_enriched_blocks(raw.strip(), expected=len(items))
        out: list[tuple[str, str, str]] = []
        for i, (headline, summary, ai) in enumerate(parsed):
            item = items[i]
            headline = _finalize_headline(headline, item, ctx=time_ctx) if headline.strip() else fallbacks[i][0]
            summary = _finalize_summary(
                summary if len(summary) >= summary_min_len() - 40 else fallbacks[i][1],
                item,
                ctx=time_ctx,
                slot=i,
            )
            ai_raw = ai if len(_sanitize_ai_comment(ai)) >= max(60, lo // 2) else fallbacks[i][2]
            ai = _finalize_ai(ai_raw, item, ctx=time_ctx)
            out.append((headline, summary, ai))
        if len(out) == len(items) and all(h and s and a for h, s, a in out):
            _warn_duplicate_news_copy(out)
            return out
    except Exception:  # noqa: BLE001
        pass
    _warn_duplicate_news_copy(fallbacks)
    return fallbacks


def reflow_news_article_body(text: str) -> str:
    """humanize 会吃掉行首缩进，恢复「摘要 + AI点评」两行的排版。"""
    out: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s or s.startswith(">") or s.startswith("[[fig:") or s.startswith("本文为"):
            out.append(line)
            i += 1
            continue
        if re.match(r"^\d+\.", s):
            out.append(s)
            i += 1
            if i < len(lines):
                nxt = lines[i].strip()
                if nxt and not re.match(r"^\d+\.", nxt) and not nxt.startswith("AI点评"):
                    out.append(f"  {nxt}")
                    i += 1
            if i < len(lines) and lines[i].strip().startswith("AI点评"):
                out.append(f"  {lines[i].strip()}")
                i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def assemble_news_body(
    items: list[dict[str, Any]],
    enriched: list[tuple[str, str]],
    *,
    now: datetime,
) -> str:
    _, _, hours, prefer_stock = news_pick_params()
    if is_weekend_news_batch():
        from scripts.tools.wechat_mp_news_lede import build_weekend_hot_news_intro

        intro = build_weekend_hot_news_intro(items, now=now, hours=hours)
    elif is_hot_stock_news_mode():
        from scripts.tools.wechat_mp_news_lede import build_hot_stock_news_intro

        intro = build_hot_stock_news_intro(items, now=now, hours=hours)
    elif prefer_stock:
        intro = (
            f"以下为近 {hours} 小时内关注度较高的 {len(items)} 条快讯"
            "（按互动热度筛选，个股相关优先）。"
        )
    else:
        from scripts.tools.wechat_mp_news_lede import build_generic_news_intro

        intro = build_generic_news_intro(items, now=now, hours=hours)
    lines = [
        SECTION_LIST,
        intro,
        "",
    ]
    for idx, (it, block) in enumerate(zip(items, enriched), start=1):
        tag = sentiment_label(str(it.get("sentiment") or "neutral"))
        headline, summary, ai = block
        if is_hot_stock_news_mode():
            head = headline.strip() or news_display_headline(it)
        else:
            title = (it.get("title") or "").strip()
            stock = (it.get("matched_stock_name") or "").strip()
            head = (
                headline.strip()
                or (f"{stock}｜{title}" if stock and not title.startswith(stock) else title)
            )
        lines.append(f"{idx}. [{tag}] {head}")
        lines.append(f"  {summary}")
        lines.append(f"  AI点评：{ai.strip()}")
        if idx < len(items):
            lines.append("")
    return "\n".join(lines)


def generate_news_feature_body(*, now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    items = load_top_news_items()
    if not items:
        if is_hot_stock_news_mode():
            raise RuntimeError(
                "热股要闻生成失败：请确认 OpenCLI 可访问东财热股榜与 7×24 快讯"
            )
        raise RuntimeError("无可用快讯，请先运行 sync_macro_news")
    enriched = generate_enriched_news_copy(items)
    return assemble_news_body(items, enriched, now=now)
