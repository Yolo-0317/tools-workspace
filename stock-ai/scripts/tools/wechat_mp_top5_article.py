#!/usr/bin/env python3
"""公众号 Top5 稿：选股名单 + 东财快采 + 交易员视角成稿（独立于八维度 SOP）。"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.deepseek_client import call_deepseek, is_llm_configured
from scripts.tools.selection_watchlist import SelectionPick, next_trading_day
from scripts.tools.wechat_mp_public import PUBLIC_MP_WRITER_RULE
from scripts.tools.wechat_mp_sop_fast import TOP5_SOP_PROFILE, WechatSopPack, collect_wechat_sop_packs


def _truncate(text: str, limit: int = 3600) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text or "（无）"
    return text[:limit] + "\n…（下文已截断）"


def _trade_date_str(td: date) -> str:
    return td.isoformat()


def _pick_meta_line(p: SelectionPick) -> str:
    return (
        f"标签 {p.label}；评分 {p.score:.0f}；收盘 {p.close:.2f} 元（{p.change_pct:+.2f}%）；"
        f"建议 {p.action}"
    )


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
        decision = r.get("decision") or "—"
        watch = "关注" if r.get("watch") else "暂不关注"
        lines.append(f"- {code}：{watch}，决策 {decision}")
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


def _first_nonempty_line(text: str, *, min_len: int = 8) -> str:
    for line in text.splitlines():
        s = line.strip()
        if len(s) >= min_len and not s.startswith(("#", "```", "---")):
            s = re.sub(r"^[\-*\d.]+\s*", "", s)
            if s:
                return s
    return ""


def _template_body(
    *,
    picks: list[SelectionPick],
    packs: list[WechatSopPack],
    td_s: str,
    watch_s: str,
    roster: str,
) -> str:
    lines = [
        "一、观察名单",
        f"数据日 {td_s}，次日跟踪 {watch_s}",
        "",
        roster,
        "",
        "二、个股拆解",
    ]
    pack_by_code = {p.code: p for p in packs}
    for i, pick in enumerate(picks, 1):
        p = pack_by_code.get(pick.code)
        lines.append(f"{i}. {pick.name}（{pick.code}）")
        lines.append(f"   地位：{_pick_meta_line(pick)}")
        if p and p.sop_ok:
            snippet = _first_nonempty_line(p.preliminary)
            lines.append(f"   量价资金：{snippet[:100] or '见东财快采'}")
        else:
            lines.append("   量价资金：东财快采未获取，仅依选股信号跟踪。")
        lines.append(
            "   博弈：收盘选股偏右侧；次日涨幅超 5% 不追，等回踩或放量确认。"
        )
        lines.append("   结论：观察为主；待配置 DEEPSEEK 后输出完整交易员稿。")
        lines.append("")

    lines.extend(
        [
            "三、组合与纪律",
            "五只标的分散观察，控制单票仓位；彼此逻辑勿高度重复，避免同题材过度集中。",
            "",
            "四、次日跟踪",
            f"下一交易日（{watch_s}）按监控池纪律跟踪；回落约 3% 附近再评估承接。",
        ]
    )
    return "\n".join(lines)


def generate_top5_trader_body(
    picks: list[SelectionPick],
    *,
    trade_date: date,
    pool_source: str = "",
) -> str:
    """生成 Top5 公众号正文（交易员视角）。"""
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

    if not is_llm_configured():
        return _template_body(
            picks=picks,
            packs=packs,
            td_s=td_s,
            watch_s=watch_s,
            roster=roster,
        )

    n = len(packs)
    pool_note = pool_source or "多策略合并按总分重选"
    prompt = f"""你是有 10 年经验的 A 股短线交易员，为微信公众号撰写「收盘选股 Top5」观察稿。
读者要复盘与次日计划，不要研报腔，不要粘贴东财网页原文。
{PUBLIC_MP_WRITER_RULE}

## 数据日 / 次日
{td_s} → 次日 {watch_s}

## 候选池说明
{pool_note}（综合 / 五因子 / MA5 / 观察池等合并去重后，按总分取前 {len(picks)}，非单一 combined 表前 5 行）

## 观察名单（重选后的 Top{len(picks)}）
{roster}

## 库内 SOP 审查摘要（仅供参考，与快采冲突时以快采为准）
{reviews_ctx}

## 东财快采 + 技术面（前 {n} 只，事实来源）
{sop_blob}

## 输出结构（禁止 emoji、禁止 markdown 表格、禁止「研究员札记 |」）
一、观察名单
（2～3 段：今日筛出逻辑、整体风格、与次日跟踪关系；可点名 1～2 只最强信号）

二、个股拆解
（每只独立 4 行块，标题行「1. 股票名（000001）」）
地位：（策略标签、评分、在观察池中的相对强度）
量价资金：（从快采提炼，≤3 句，写判断不写原文）
博弈：（次日追高/回踩/放量条件，是否触发 5% 不追红线）
结论：（观察 / 低吸试错 / 暂不关注，一句）

三、组合与纪律
（五只如何搭配、仓位与分散、优先级排序）

四、次日跟踪
（次日重点盯哪 1～2 只、回落与量能条件）

## 硬性要求
1. 必须覆盖名单中的 {n} 只（每只都有拆解）；数据缺失写「数据未获取」仍要给推演
2. 禁止投资建议；用「观察」「条件满足再看」
3. 全文 900～1500 字，只使用上文数据"""

    try:
        content = call_deepseek(
            [
                {
                    "role": "system",
                    "content": (
                        "你是短线交易员，文风干脆、有纪律感。"
                        "从东财快采提炼结论，绝不粘贴网页。"
                        "面向公开读者，禁止作者持仓与第一人称仓位。"
                        "直接从「一、观察名单」开始。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
            max_tokens=3600,
            timeout=(10, 240),
        )
        return content.strip()
    except Exception as exc:  # noqa: BLE001
        base = _template_body(
            picks=picks,
            packs=packs,
            td_s=td_s,
            watch_s=watch_s,
            roster=roster,
        )
        return f"{base}\n\n（交易员成稿失败：{exc}，以上为模板正文）"
