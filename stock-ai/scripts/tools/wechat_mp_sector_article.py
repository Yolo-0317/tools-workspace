#!/usr/bin/env python3
"""公众号「热点行业研究」稿：多源挖掘 1～2 个主题 + 研究员体例成稿。"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.deepseek_client import call_wechat_mp_llm, is_wechat_mp_llm_configured
from scripts.tools.wechat_mp_hot_theme import (
    HotThemeReport,
    ThemeScore,
    build_sector_context_blob,
    discover_sector_hot_themes,
    pick_focus_themes,
)
from scripts.tools.wechat_mp_public import PUBLIC_MP_WRITER_RULE, RESEARCHER_VOICE_RULE, PLATFORM_PROPERTY_RISK_RULE
from scripts.tools.wechat_mp_monetization import monetization_prompt_block

TZ = ZoneInfo("Asia/Shanghai")

SECTION_WHY = "> 为什么现在看"
SECTION_CHAIN = "> 产业链怎么拆"
SECTION_PRICE = "> 盘面里谁在用价格说话"
SECTION_LINK = "> 和指数情绪怎么联动"
SECTION_FORWARD = "> 向后看要验证什么"

from scripts.tools.wechat_mp_prose import SECTOR_SECTION_TITLES  # noqa: E402


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def resolve_sector_trade_date(
    report: HotThemeReport | None = None,
    *,
    fallback: date | None = None,
) -> date:
    """与选股/行业榜一致的数据日（非日历「今天」）。"""
    if report and report.trade_date:
        try:
            return date.fromisoformat(str(report.trade_date)[:10])
        except ValueError:
            pass
    try:
        from scripts.tools.selection_results import merge_selection_strategies_df

        td, _, _ = merge_selection_strategies_df()
        return td
    except Exception:
        return fallback or datetime.now(TZ).date()


def format_sector_trade_label(td: date, *, edition: str | None = "close") -> str:
    """如「6月3日收盘」——正文/摘要统一口径，避免「今日」歧义。"""
    from scripts.tools.wechat_mp_market_edition import normalize_market_edition

    ed = normalize_market_edition(edition)
    suffix = {"pre": "盘前", "midday": "午间", "close": "收盘"}.get(ed, "收盘")
    return f"{td.month}月{td.day}日{suffix}"


def _sector_date_rules_block(report: HotThemeReport) -> str:
    label = format_sector_trade_label(
        resolve_sector_trade_date(report), edition=report.edition
    )
    return (
        f"【数据日】{label}（{report.trade_date}）。"
        "正文彩色开篇、五节正文与结论先行段须写清该数据日；"
        "禁止用「今日」「当天」指代行情日（成稿日历日可能与数据日不同）。"
    )


def _collect_sample_stocks(theme_names: list[str]) -> list[str]:
    """行业领涨 + 人气同行业 + 龙头/选股观察（供「盘面」节写具体股名）。"""
    from scripts.tools.wechat_mp_sector_stocks import collect_sector_sample_lines

    return collect_sector_sample_lines(theme_names)


def _index_brief() -> list[str]:
    try:
        from scripts.tools.daily_briefing_report import fetch_market_indices

        return fetch_market_indices()[:6]
    except Exception:
        return ["（指数数据暂不可用）"]


def build_sector_research_context(
    *,
    themes: list[ThemeScore] | None = None,
    report: HotThemeReport | None = None,
    edition: str | None = "close",
) -> str:
    report = report or discover_sector_hot_themes(edition=edition)
    focus = themes or pick_focus_themes(report)
    names = [t.name for t in focus]
    stocks = _collect_sample_stocks(names)
    parts = [
        build_sector_context_blob(report),
        _sector_date_rules_block(report),
        "",
        "【本篇聚焦主题（按热度排序，写 1～2 个）】",
    ]
    for i, t in enumerate(focus, 1):
        parts.append(
            f"{i}. {t.name}（得分 {t.score:.1f}，来源：{', '.join(t.sources)}）"
        )
    hot_lines: list[str] = []
    try:
        from scripts.tools.wechat_mp_sector_stocks import (
            fetch_hot_stock_watch_rows,
            format_hot_stock_watch_line,
        )

        hot_rows = fetch_hot_stock_watch_rows()
        hot_lines = [format_hot_stock_watch_line(r) for r in hot_rows]
    except Exception:
        hot_lines = []

    parts.extend(
        [
            "",
            "【A股指数简况（正文须直接写沪指/深成指/涨跌家数，禁止写「根据你提供的」「根据上下文」）】",
            *_index_brief(),
            "",
            "【代表股观察样本（有则写，无则说明盘面缺样本）】",
            *(stocks or ["（暂无与主题直接对应的龙头/选股样本，仅写产业链逻辑）"]),
        ]
    )
    if hot_lines:
        from scripts.tools.wechat_mp_sector_stocks import sector_evening_dedup_enabled

        if sector_evening_dedup_enabled():
            parts.extend(
                [
                    "",
                    "【evening 同批分工】news 头条已写东财人气快讯；本篇禁止再罗列 Top10 全榜，"
                    "「盘面里谁在用价格说话」只写行业代表股（已避开头条人气前几名）。",
                ]
            )
        else:
            parts.extend(
                [
                    "",
                    "【当日人气观察 Top10（成稿将单独插入一节，其它节勿重复罗列全榜）】",
                    *hot_lines,
                ]
            )
    try:
        from scripts.tools.wechat_mp_market_edition import (
            build_market_news_context,
            normalize_market_edition,
        )

        ed = normalize_market_edition(edition)
        news_blob, _ = build_market_news_context(ed)
        parts.extend(["", news_blob])
    except Exception:
        pass
    return "\n".join(parts)


def sector_title_hook(themes: list[ThemeScore]) -> str:
    names = [t.name for t in themes if t.name]
    if len(names) >= 2:
        return f"{names[0]}+{names[1]}"
    if names:
        return names[0]
    return "主线"


def _sector_lead_stock_name(theme_names: list[str]) -> str | None:
    """领涨/代表股名（搜一搜长尾：用户常搜票名，标题前 15 字可带 1 只）。"""
    if not theme_names:
        return None
    try:
        from scripts.tools.wechat_mp_sector_stocks import collect_sector_sample_stocks

        stocks = collect_sector_sample_stocks(theme_names)
        if stocks:
            return (stocks[0].name or "").strip() or None
    except Exception:
        return None
    return None


def build_sector_title(
    themes: list[ThemeScore],
    *,
    now: datetime | None = None,
    hot_watch_rows: list | None = None,
) -> str:
    del now
    hook = sector_title_hook(themes)
    theme_names = [t.name for t in themes if t.name]
    if hot_watch_rows is None:
        try:
            from scripts.tools.wechat_mp_sector_stocks import fetch_hot_stock_watch_rows

            hot_watch_rows = fetch_hot_stock_watch_rows()
        except Exception:
            hot_watch_rows = []
    from scripts.tools.wechat_mp_sector_stocks import (
        news_hot_exclude_codes,
        pick_hot_stock_for_sector_title,
        sector_evening_dedup_enabled,
    )

    exclude = news_hot_exclude_codes() if sector_evening_dedup_enabled() else set()
    if sector_evening_dedup_enabled():
        lead = _sector_lead_stock_name(theme_names) or pick_hot_stock_for_sector_title(
            hot_watch_rows or [],
            exclude_codes=exclude,
        )
    else:
        hot_name = pick_hot_stock_for_sector_title(hot_watch_rows or [])
        lead = hot_name or _sector_lead_stock_name(theme_names)
    options: tuple[str, ...] = (
        f"A股行业｜{hook}：产业链怎么拆？",
        f"A股{hook}｜产业链结构观察",
        f"{hook}产业链怎么拆？量价对照",
    )
    from scripts.tools.wechat_mp_content import _pick_clickbait_title
    from scripts.tools.wechat_mp_seo import enrich_title_for_search

    if lead:
        board_lead = _sector_lead_stock_name(theme_names)
        verb = "领涨" if board_lead and lead == board_lead else "关联"
        from scripts.tools.wechat_mp_public import sanitize_public_title

        # 搜一搜：标题前段带 1 只热股名；用语偏信息观察，避免「领衔」被平台判为推荐
        raw = sanitize_public_title(
            f"A股{hook}｜{lead}{verb}观察：产业链怎么拆？",
            kind="sector",
        )
        return enrich_title_for_search(raw, "sector", clip_fn=lambda t, _m=32: t[:_m])

    raw = _pick_clickbait_title(list(options), kind="sector")
    return enrich_title_for_search(raw, "sector", clip_fn=lambda t, _m=32: t[:_m])


def build_sector_digest(
    themes: list[ThemeScore],
    *,
    trade_date: date | None = None,
    edition: str | None = "close",
) -> str:
    td = trade_date or datetime.now(TZ).date()
    hook = sector_title_hook(themes)
    day_label = format_sector_trade_label(td, edition=edition)
    base = (
        f"【{day_label} 行业观察】{hook}——"
        f"东财行业榜挖掘 {day_label} 热点，拆产业链与量价；个人观察，非荐股。"
    )
    from scripts.tools.wechat_mp_seo import enrich_digest

    return enrich_digest(base, "sector")


def _template_sector_body(
    *,
    context: str,
    themes: list[ThemeScore],
    trade_day_label: str,
) -> str:
    hook = sector_title_hook(themes)
    primary = themes[0].name if themes else "主线"
    lines = [
        (
            f"{trade_day_label}，资金与舆情共振偏向「{hook}」，"
            "我们认为宜先搞清产业链位置，再对照该日收盘量价。"
        ),
        "",
        SECTION_WHY,
        f"东财行业榜与快讯素材对「{primary}」有共振；这不是固定科技清单，而是 {trade_day_label} 的榜序结果。",
        "向后看，要验证的是景气是否继续反映在成交额与梯队上，而不是单条新闻的情绪脉冲。",
        "",
        SECTION_CHAIN,
        "上游、中游、下游分开写：谁受益、谁仅概念映射、谁滞后反应。",
        "缺具体公司数据时，只写环节逻辑，不编造订单或份额数字。",
        "",
        SECTION_PRICE,
        "优先用上下文里的代表股样本：写清涨跌、换手、是否带量，禁止操作建议。",
        "",
        SECTION_LINK,
        *_index_brief(),
        "对照涨跌家数：若指数与主题背离，写明是权重撑盘还是主线扩散。",
        "",
        SECTION_FORWARD,
        "我们认为，短线跟踪应落在可验证指标（价差、开工率、龙头竞价）而非口号。",
        "值得关注的是，若龙头断板而跟风仍涨，往往意味着博弈而非基本面驱动。",
        "向后看，留意次日同主题是否仍有 2 只以上带量标的，否则热度可能一日游。",
    ]
    _ = context
    return "\n".join(lines)


def generate_sector_research_body(
    *,
    now: datetime | None = None,
    edition: str | None = "close",
    max_themes: int | None = None,
) -> tuple[str, list[ThemeScore], HotThemeReport]:
    now = now or datetime.now(TZ)
    cap = max_themes if max_themes is not None else _env_int("WECHAT_MP_SECTOR_MAX_THEMES", 2)
    report = discover_sector_hot_themes(edition=edition)
    themes = pick_focus_themes(report, max_themes=cap, edition=edition)
    context = build_sector_research_context(themes=themes, report=report, edition=edition)
    trade_day_label = format_sector_trade_label(
        resolve_sector_trade_date(report), edition=report.edition
    )

    if not is_wechat_mp_llm_configured():
        return (
            _template_sector_body(
                context=context,
                themes=themes,
                trade_day_label=trade_day_label,
            ),
            themes,
            report,
        )

    names = "、".join(t.name for t in themes)
    dedup_note = ""
    try:
        from scripts.tools.wechat_mp_sector_stocks import (
            news_hot_exclude_codes,
            sector_evening_dedup_enabled,
        )

        if sector_evening_dedup_enabled():
            exc = news_hot_exclude_codes()
            exc_txt = "、".join(sorted(exc)) if exc else "（无）"
            dedup_note = (
                f"\n## evening 同批分工（必读）\n"
                f"- news 头条已覆盖东财人气快讯；禁止再写 Top10 全榜或快讯清单\n"
                f"- 代表股样本已避开头条人气前几名（代码 {exc_txt}）\n"
                f"- 本篇只写行业机制、产业链与行业代表股量价\n"
            )
    except Exception:
        pass
    prompt = f"""你是一位从业15年的A股行业研究员，为公众号撰写「热点行业研究」观察稿。
{dedup_note}{PUBLIC_MP_WRITER_RULE}
{RESEARCHER_VOICE_RULE}
{PLATFORM_PROPERTY_RISK_RULE}

{context}

## 写作要求
0. **结论先行**：在 `{SECTION_WHY}` 之前，先写 2～3 句（50～90字），开篇第一句须含「{trade_day_label}」，点明该日聚焦行业（{names}）+ 一句机制判断；然后再写五节标题。禁止用「今日」指代数据日。
1. 全文五节，节标题必须逐字使用（不要用「一、二、三」）：
   {SECTION_WHY}
   {SECTION_CHAIN}
   {SECTION_PRICE}
   {SECTION_LINK}
   {SECTION_FORWARD}
2. 必须覆盖上下文中的 **1～2 个聚焦主题**；若有两个，篇幅约 55% / 45%，勿写成互无关的两篇。
3. 「为什么现在看」160～220字：催化（快讯/政策/景气）+ 为何是 {trade_day_label} 的主线；**至少 1 句承接宏观或产业政策背景**（只写公开信息），再写资金/行业榜映射
4. 「产业链怎么拆」280～380字：上游/中游/下游或设备-材料-应用；只观察，无买入建议
5. 「盘面里谁在用价格说话」240～320字：**必须**写出上下文「代表股观察样本」里至少 **2 只**（有则尽量写满样本数，最多 4 只）；每只 **公司名+6位代码各出现 1 次**，写涨跌/换手/是否带量等事实，**禁止**操作建议与「可买可卖」。无样本才写板块梯队现象
5a. evening 同批：news 已写人气快讯，本节**勿复述**头条热股清单，只写**行业链**代表股量价
5b. 代表股是行业/人气/龙头 **观察样本**，不是第二篇 top5，勿写成五只名单式拆解
6. 「和指数情绪怎么联动」180～240字：指数、涨跌家数、情绪周期相位（若有）
7. 「向后看要验证什么」160～220字：2～3 个可跟踪指标；「我们认为」「值得关注的是」「向后看」各起一段
8. 禁止 emoji、禁止 markdown 加粗、禁止编号快讯清单
8a. 禁止「流水线/链路/赋能/综上所述/值得注意的是」及「首先/其次/最后/综上」机械连接
8b. **移动端排版**：普通叙述每段约 120 字内；`1. 2. 3.` 列表每项单独一行
9. 只使用上下文事实；勿编造订单额、精确份额
10. 禁止正文内免责声明（文末统一追加）
11. **禁止元叙述**：勿写「根据你提供的」「根据上下文/上文」「你提供的指数」等；指数与涨跌家数须直接陈述（如「沪指收于…，上涨家数…」）
{monetization_prompt_block("sector")}"""

    try:
        content = call_wechat_mp_llm(
            [
                {
                    "role": "system",
                    "content": (
                        "你是A股行业研究员，输出连贯行业观察，不是新闻汇总或荐股清单。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=_env_int("WECHAT_MP_SECTOR_MAX_TOKENS", 3600),
        )
        return content.strip(), themes, report
    except Exception as exc:  # noqa: BLE001
        body = _template_sector_body(
            context=context,
            themes=themes,
            trade_day_label=trade_day_label,
        )
        return f"{body}\n\n（行业稿生成失败：{exc}，以上为模板正文）", themes, report
