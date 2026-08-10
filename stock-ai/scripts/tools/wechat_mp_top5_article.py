#!/usr/bin/env python3
"""公众号 Top5 稿：选股名单 + 东财快采 + 客观分析成稿（独立于八维度 SOP）。"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.deepseek_client import call_wechat_mp_llm, is_wechat_mp_llm_configured
from scripts.tools.selection_watchlist import SelectionPick, next_trading_day
from scripts.tools.wechat_mp_public import (
    PUBLIC_MP_WRITER_RULE,
    RESEARCHER_VOICE_RULE,
    PLATFORM_PROPERTY_RISK_RULE,
    check_public_compliance,
    finalize_public_body_text,
    sanitize_public_mp_text,
)
from scripts.tools.wechat_mp_monetization import monetization_prompt_block
from scripts.tools.wechat_mp_sop_fast import TOP5_SOP_PROFILE, WechatSopPack, collect_wechat_sop_packs

_SCORE_RE = re.compile(r"(?:评分|综合分|技术分)\s*[\d.]+")
_POINTS_RE = re.compile(r"[\d.]+\s*分")
_ACTION_RE = re.compile(
    r"(?:建议|结论|操作)[：:]\s*[^\n]+|"
    r"(?:观察买入|买入观察|观察为主|低吸试错|暂不关注|强势关注|小仓埋伏|继续观察|持有观望)"
)
_FIELD_OPINION_RE = re.compile(r"^(结论|博弈|操作建议)[：:]")
# 标题句式误入正文（LLM 常把「XX领衔N只！收盘信号出炉，明日盯啥？」写在「筛选名单」下）
_TOP5_TITLE_ECHO_RE = re.compile(
    r"^[\s>]*.{1,14}领衔\d+只[！!].*(?:收盘信号|明日盯|盯啥)"
)
_TOP5_TITLE_ECHO_LOOSE_RE = re.compile(
    r"^[\s>]*.{1,14}领衔\d+只[！!]"
)


def _truncate(text: str, limit: int = 3600) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text or "（无）"
    return text[:limit] + "\n…（下文已截断）"


def _trade_date_str(td: date) -> str:
    return td.isoformat()


def _pick_meta_line(p: SelectionPick) -> str:
    return f"策略标签 {p.label}；收盘 {p.close:.2f} 元（{p.change_pct:+.2f}%）"


def _roster_context(picks: list[SelectionPick], *, trade_date: date, watch_date: date) -> str:
    from scripts.tools.wechat_mp_prose import format_top5_list_prose

    return format_top5_list_prose(
        picks, trade_date=trade_date, watch_date=watch_date, for_public=True
    )


def _sop_reviews_context() -> str:
    try:
        from scripts.tools.selection_watchlist import load_sop_reviews

        reviews = load_sop_reviews()
    except Exception:  # noqa: BLE001
        return "（无库内 SOP 审查摘要）"
    if not reviews:
        return "（无库内 SOP 审查摘要）"
    lines: list[str] = []
    for r in reviews[:5]:
        code = str(r.get("code", "")).zfill(6)
        theme = str(r.get("theme") or r.get("sector") or "—").strip()
        lines.append(f"- {code}：库内审查主题 {theme}")
    return "\n".join(lines)


def _sop_blob(packs: list[WechatSopPack]) -> str:
    if not packs:
        return "（无标的）"
    chunks: list[str] = []
    for p in packs:
        chunks.append(
            f"### {p.rank}. {p.name}（{p.code}）\n"
            f"选股信号：{p.meta_line}\n"
            f"技术面：\n{_truncate(p.technical, 1200)}\n"
            f"东财快采：\n{_truncate(p.preliminary, 3200)}"
        )
    return "\n\n".join(chunks)


def _normalize_title_echo_line(line: str) -> str:
    s = re.sub(r"^[\s>]+", "", (line or "").strip())
    s = re.sub(r"[！!？?，,。.\s]", "", s)
    return s


def strip_top5_title_echo(text: str, *, title: str = "") -> str:
    """去掉正文中误贴的公众号标题句式（与 `_top5_title` 生成的标题同构）。"""
    if not text:
        return text
    title_norm = _normalize_title_echo_line(title) if title else ""
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            out.append(raw)
            continue
        if title_norm and _normalize_title_echo_line(line) == title_norm:
            continue
        if _TOP5_TITLE_ECHO_RE.match(line):
            continue
        if _TOP5_TITLE_ECHO_LOOSE_RE.match(line) and (
            "收盘信号" in line or "明日盯" in line or "盯啥" in line
        ):
            continue
        out.append(raw)
    merged = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", merged).strip()


def _first_nonempty_line(text: str, *, min_len: int = 8) -> str:
    for line in text.splitlines():
        s = line.strip()
        if len(s) >= min_len and not s.startswith(("#", "```", "---")):
            s = re.sub(r"^[\-*\d.]+\s*", "", s)
            if s:
                return s
    return ""


def sanitize_top5_analysis_text(text: str) -> str:
    """Top5 公开稿：去分数、去买卖/观察类操作建议，保留事实分析。"""
    cleaned = finalize_public_body_text(text or "")
    out: list[str] = []
    for raw in cleaned.splitlines():
        line = raw.strip()
        if not line:
            out.append("")
            continue
        if _FIELD_OPINION_RE.match(line):
            continue
        line = _SCORE_RE.sub("", line)
        line = _POINTS_RE.sub("", line)
        line = _ACTION_RE.sub("", line)
        line = re.sub(r"按总分重选", "多策略合并筛选", line)
        line = re.sub(r"按总分", "按多策略信号", line)
        line = re.sub(r"纳入次日观察池", "纳入次日数据跟踪", line)
        line = re.sub(r"观察标的", "筛选标的", line)
        line = re.sub(r"观察名单", "筛选名单", line)
        line = re.sub(r"\s{2,}", " ", line).strip(" ；;")
        if line:
            out.append(line)
    merged = "\n".join(out)
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    return merged.strip()


def _template_body(
    *,
    picks: list[SelectionPick],
    packs: list[WechatSopPack],
    td_s: str,
    watch_s: str,
    roster: str,
    sector_primary: str = "",
) -> str:
    lines = [
        "> 筛选名单",
        f"数据日 {td_s}，结构跟踪日 {watch_s}",
        "",
        roster,
        "",
        "> 个股拆解",
    ]
    pack_by_code = {p.code: p for p in packs}
    for i, pick in enumerate(picks, 1):
        p = pack_by_code.get(pick.code)
        lines.append(f"{i}. {pick.name}（{pick.code}）")
        logic = _pick_meta_line(pick)
        if sector_primary:
            logic += f"；与当日主线「{sector_primary}」关系须写明（同属/分化/独立）"
        lines.append(f"   逻辑归属：{logic}")
        if p and p.sop_ok:
            snippet = _first_nonempty_line(p.preliminary)
            lines.append(f"   量价结构：{snippet[:120] or '见东财快采摘要'}")
        else:
            lines.append("   量价结构：东财快采未获取，仅保留收盘涨跌与策略标签。")
        lines.append("   技术位置：需对照均线排列、前高压力与平台区间，核对结构是否延续。")
        lines.append("   待核实：次日重点看量能是否配合、板块是否仍为主线。")
        lines.append("")

    lines.extend(
        [
            "> 组合特征",
            "五只标的来自不同策略标签，彼此逻辑勿高度重复；下文按单票事实展开，不含操作建议。",
            "",
            "> 待验证事项",
            f"结构跟踪日（{watch_s}）可核对：① 主线板块是否延续；② 单票量能与收盘位置；③ 快采缺失项是否补齐。",
        ]
    )
    return sanitize_top5_analysis_text("\n".join(lines))


def generate_top5_trader_body(
    picks: list[SelectionPick],
    *,
    trade_date: date,
    pool_source: str = "",
) -> str:
    """生成 Top5 公众号正文（客观分析，非操作建议）。"""
    watch = next_trading_day(trade_date)
    td_s = _trade_date_str(trade_date)
    watch_s = f"{watch.month}月{watch.day}日"
    roster = _roster_context(picks, trade_date=trade_date, watch_date=watch)

    from scripts.tools.wechat_mp_sop_fast import sop_max

    limit = min(len(picks), sop_max(TOP5_SOP_PROFILE))
    items = [
        {
            "rank": i,
            "code": p.code,
            "name": p.name or p.code,
            "meta_line": _pick_meta_line(p),
        }
        for i, p in enumerate(picks[:limit], 1)
    ]
    packs = collect_wechat_sop_packs(TOP5_SOP_PROFILE, items, trade_date=td_s)
    sop_blob = _sop_blob(packs)
    reviews_ctx = _sop_reviews_context()
    align = ""
    sector_primary = ""
    try:
        from scripts.tools.wechat_mp_evening_align import (
            sector_alignment_prompt_block,
            sector_primary_label,
        )

        align = sector_alignment_prompt_block()
        sector_primary = sector_primary_label()
    except Exception:
        align = ""

    if not is_wechat_mp_llm_configured():
        return _template_body(
            picks=picks,
            packs=packs,
            td_s=td_s,
            watch_s=watch_s,
            roster=roster,
            sector_primary=sector_primary,
        )

    n = len(packs)
    if pool_source and "eastmoney_hot" in pool_source:
        pool_note = "东财 A 股人气榜（流量优先，搜一搜票名对齐）"
    else:
        pool_note = pool_source or "多策略合并筛选"
    prompt = f"""你是 A 股策略研究员，为微信公众号撰写「收盘综合选股 Top5」观察稿。
读者要读懂每只票的结构与事实：研报体简练版（有框架、有验证点），不要粘贴东财网页原文。
{PUBLIC_MP_WRITER_RULE}
{RESEARCHER_VOICE_RULE}
{PLATFORM_PROPERTY_RISK_RULE}
{align}

## 数据日 / 结构跟踪日
{td_s} → {watch_s}

## 候选池说明
{pool_note}（名单共 {len(picks)} 只；每只仍走东财快采事实，禁止荐股式操作建议）

## 筛选名单（重选后的 Top{len(picks)}）
{roster}

## 库内 SOP 审查摘要（仅供参考，与快采冲突时以快采为准）
{reviews_ctx}

## 东财快采 + 技术面（前 {n} 只，事实来源）
{sop_blob}

## 输出结构（禁止 emoji、禁止 markdown 表格、禁止「研究员札记 |」；**小标题禁止「一、二、三」序号**，只用 `> 标题`）
> 筛选名单
（**首段 2～3 句结论先行**：须含名单只数 + 与当日行业主线的关系；再 1 短段写板块/风格分布；不写买卖判断）

> 个股拆解
（每只独立 4 行块，标题行「1. 股票名（000001）」）
逻辑归属：（策略标签、与当日行业主线的关系：同属/分化/独立；**禁止写评分、分数、排名分**）
量价结构：（从快采提炼换手、涨跌、资金事实，≤3 句，客观陈述）
技术位置：（均线、平台、压力/支撑等结构描述，不写「可买/可卖」）
待核实：（还缺哪些数据或结构条件才能确认，**禁止**给观察/买入/关注类意见）

> 组合特征
（五只在行业/逻辑上的分布与异同，客观描述，不写仓位与优先级）

> 待验证事项
（结构跟踪日应核对的数据点：板块、量能、缺口等，**禁止**写成交易计划）

## 硬性要求
1. 必须覆盖名单中的 {n} 只（每只都有拆解）；数据缺失写「数据未获取」仍要列结构框架
2. **禁止**投资建议、买卖暗示、观察买入、低吸、建仓、结论性操作建议
3. **禁止**出现评分、分数、X 分、按总分等量化排名表述
4. 全文 **750～1200 字**（控制篇幅利于搜一搜完读），只使用上文数据
5. **移动端排版**：普通叙述每段 ≤3 行（约 120 字内）；`1. 2. 3.` 序号列表**每项单独一行**，禁止同一行写多个序号；逻辑归属/量价结构/技术位置/待核实各占一行
6. **标题由系统单独生成**；正文禁止出现「XX领衔N只！收盘信号出炉，明日盯啥？」或与之同构的问句
7. 「筛选名单」开篇只写数据日、只数、行业主线事实，勿写标题党钩子
{monetization_prompt_block("top5")}"""

    try:
        content = call_wechat_mp_llm(
            [
                {
                    "role": "system",
                    "content": (
                        "你是 A 股策略研究员，文风冷静、重事实与结构链条。"
                        "从东财快采提炼可核对的信息，绝不粘贴网页。"
                        "面向公开读者，禁止作者持仓与第一人称仓位。"
                        "禁止分数与任何买卖/观察类操作建议。"
                        "小标题用 `> 标题`，禁止「一、二、三」序号。"
                        "直接从「> 筛选名单」开始。"
                        "禁止把公众号标题句式写进正文首段。"
                        "每段宜短；序号列表每项单独一行。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
            max_tokens=3600,
            timeout=(10, 240),
        )
        return sanitize_top5_analysis_text(
            strip_top5_title_echo(content.strip()),
        )
    except Exception as exc:  # noqa: BLE001
        base = _template_body(
            picks=picks,
            packs=packs,
            td_s=td_s,
            watch_s=watch_s,
            roster=roster,
            sector_primary=sector_primary,
        )
        return f"{base}\n\n（分析成稿失败：{exc}，以上为模板正文）"
