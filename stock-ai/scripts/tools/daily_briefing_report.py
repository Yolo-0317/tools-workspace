#!/usr/bin/env python3
"""生成每日战报（大盘 + 东财快讯 + 国际 + 持仓 + DeepSeek 解读）。"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.deepseek_client import call_deepseek
from scripts.tools.fetch_eastmoney_macro_news import MacroNewsItem, fetch_macro_news, format_report
from scripts.tools.holdings_context import load_full_decision_context
from scripts.tools.market_session import MarketSession, detect_market_session

ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = ROOT / "investment-agent"
HOLDINGS_SCRIPT = AGENT_ROOT / "scripts" / "query_holdings.py"
HOLDINGS_CARD_CANDIDATES = [
    AGENT_ROOT / "持仓执行卡.md",
    Path.home() / ".qclaw" / "workspace" / "持仓执行卡.md",
]

SLOT_TITLES = {
    "09:00": "盘中战报",
    "12:00": "午间战报",
    "15:00": "收盘战报",
    "17:30": "收盘甄选战报",
    "18:00": "收盘甄选战报",
    "20:00": "晚间战报",
}

SLOT_HINTS = {
    "09:00": "早盘阶段，侧重隔夜消息与开盘预期。",
    "12:00": "午间休市，侧重上午盘面与午后关注点。",
    "15:00": "A股收盘，侧重全天走势复盘与持仓表现。",
    "17:30": "收盘后阶段：必须结合「五、今日选股 Top5」给出次日观察要点；非持仓标的仅条件化关注，严禁追高与满仓新开仓。",
    "18:00": "收盘后阶段：必须结合「五、今日选股 Top5」给出次日观察要点；非持仓标的仅条件化关注，严禁追高与满仓新开仓。",
    "20:00": "晚间时段，侧重外盘动向与次日关注点。",
}

# 含 Top5 选股段的战报时段（17:30 与选股任务合并推送；18:00 保留供手动补发）
SELECTION_BRIEFING_SLOTS = frozenset({"17:30", "18:00"})

GEOPOLITICS_KEYWORDS = ("伊朗", "美伊", "特朗普", "霍尔木兹", "以军", "中东", "制裁", "停火")


def _http_get(url: str, *, encoding: str = "utf-8", timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return raw.decode(encoding, errors="replace")


def fetch_market_indices() -> list[str]:
    codes = "sh000001,sz399001,sz399006,sh000300,sh000688"
    names = {
        "sh000001": "上证指数",
        "sz399001": "深证成指",
        "sz399006": "创业板指",
        "sh000300": "沪深300",
        "sh000688": "科创50",
    }
    url = f"https://qt.gtimg.cn/q={codes}"
    try:
        content = _http_get(url, encoding="gbk")
    except Exception as exc:  # noqa: BLE001
        return [f"大盘数据获取失败: {exc}"]

    lines: list[str] = []
    for code, name in names.items():
        match = re.search(rf'v_{re.escape(code)}="([^"]*)"', content)
        if not match:
            lines.append(f"{name}: 获取失败")
            continue
        parts = match.group(1).split("~")
        if len(parts) > 32:
            lines.append(f"{name}: {parts[3]} ({parts[31]}, {parts[32]}%)")
        else:
            lines.append(f"{name}: 数据格式异常")
    return lines or ["大盘数据为空"]


def fetch_international_markets() -> list[str]:
    specs = [
        ("hf_CL,hf_OIL", {"hf_CL": "WTI原油", "hf_OIL": "布伦特原油"}),
        ("usDJI,usIXIC", {"usDJI": "道琼斯", "usIXIC": "纳斯达克"}),
    ]
    lines: list[str] = []
    for codes, labels in specs:
        url = f"https://qt.gtimg.cn/q={codes}"
        try:
            content = _http_get(url, encoding="gbk")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"国际市场获取失败: {exc}")
            continue
        for key, label in labels.items():
            match = re.search(rf'v_{re.escape(key)}="([^"]*)"', content)
            if not match:
                continue
            parts = match.group(1).split("~")
            if key.startswith("us") and len(parts) > 5:
                price = parts[3]
                change = pct = None
                if "USD" in parts:
                    idx = parts.index("USD")
                    if idx >= 4:
                        change, pct = parts[idx - 4], parts[idx - 3]
                if change and pct:
                    lines.append(f"{label}: {price} ({change}, {pct}%)")
                else:
                    lines.append(f"{label}: {price}")
            elif len(parts) > 2:
                lines.append(f"{label}: {parts[0]} ({parts[1]}%)")
    return lines or ["国际市场数据为空"]


def _pick_geopolitics(items: list[MacroNewsItem], limit: int = 5) -> list[MacroNewsItem]:
    picked: list[MacroNewsItem] = []
    for item in items:
        blob = f"{item.title} {item.summary}"
        if any(kw in blob for kw in GEOPOLITICS_KEYWORDS):
            picked.append(item)
        if len(picked) >= limit:
            break
    return picked


def _format_news_block(title: str, items: list[MacroNewsItem], *, limit: int) -> list[str]:
    lines = [title]
    if not items:
        lines.append("- 暂无相关快讯")
        return lines
    for idx, item in enumerate(items[:limit], start=1):
        time_part = f"{item.time} " if item.time else ""
        lines.append(f"{idx}. {time_part}{item.title}")
    return lines


def _resolve_holdings_card() -> Path | None:
    return next((p for p in HOLDINGS_CARD_CANDIDATES if p.exists()), None)


def fetch_holdings_lines() -> list[str]:
    card = _resolve_holdings_card()
    if card is None:
        return ["持仓执行卡未找到"]
    if not HOLDINGS_SCRIPT.exists():
        return ["持仓查询脚本未找到"]

    env = {"HOLDINGS_CARD": str(card)}
    try:
        proc = subprocess.run(
            [sys.executable, str(HOLDINGS_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=20,
            env={**dict(**__import__("os").environ), **env},
        )
    except Exception as exc:  # noqa: BLE001
        return [f"持仓查询失败: {exc}"]

    output = (proc.stdout or proc.stderr or "").strip()
    return output.splitlines() or ["持仓数据为空"]


def _build_selection_section() -> list[str]:
    from scripts.tools.selection_watchlist import (
        enrich_pick_names,
        format_briefing_section,
        load_ai_excerpt,
        load_sop_reviews,
        load_top_picks,
        next_trading_day,
        sync_watch_alerts,
    )

    try:
        sync_watch_alerts()
        trade_date, picks = load_top_picks()
        picks = enrich_pick_names(picks)
        watch_date = next_trading_day(trade_date)
        return format_briefing_section(
            picks,
            trade_date=trade_date,
            watch_date=watch_date,
            ai_excerpt=load_ai_excerpt(),
            sop_reviews=load_sop_reviews(),
        )
    except Exception as exc:  # noqa: BLE001
        return [
            "五、今日选股 Top5（收盘后）· 次日观察",
            "",
            f"- 暂无可用选股结果（{exc}）",
            "- 请确认 17:30 选股任务已运行",
        ]


def _build_raw_sections(
    *,
    session: MarketSession,
    geo_news: list[MacroNewsItem],
    domestic_news: list[MacroNewsItem],
    news_limit: int,
    slot: str = "",
) -> list[str]:
    holdings_lines = fetch_holdings_lines()
    if session.is_stale_a_share_quote:
        holdings_lines = [session.header_note(), *holdings_lines]

    holdings_title = "六、持仓个股（最新）"
    if session.is_stale_a_share_quote and session.quote_trade_date:
        holdings_title = f"六、持仓个股（{session.format_trade_date()} 收盘）"
    if slot not in SELECTION_BRIEFING_SLOTS:
        holdings_title = holdings_title.replace("六、", "五、", 1)
        tip_no = "六"
    else:
        tip_no = "七"

    sections = [
        session.market_section_title(),
        *fetch_market_indices(),
        "",
        *_format_news_block("二、国际地缘（东财7×24 实时）", geo_news, limit=5),
        "",
        *_format_news_block("三、国内财经要闻（东财7×24 实时）", domestic_news, limit=news_limit),
        "",
        "四、国际市场（最新）",
        *fetch_international_markets(),
        "",
    ]

    if slot in SELECTION_BRIEFING_SLOTS:
        sections.extend([*_build_selection_section(), ""])

    sections.extend(
        [
            holdings_title,
            *holdings_lines,
            "",
            f"{tip_no}、提示",
            session.header_note() + "。",
            "快讯为东财7×24实时；以上供决策参考，非投资建议。",
            "来源：https://kuaixun.eastmoney.com/",
        ]
    )
    return sections


def summarize_briefing_with_deepseek(
    *,
    slot: str,
    title: str,
    raw_report: str,
    holdings_context: str,
    session: MarketSession,
) -> str:
    hint = SLOT_HINTS.get(slot, "结合当前时段给出简明解读。")
    session_hint = session.ai_session_hint(slot)
    prompt = f"""以下是「{title}（{slot}）」的原始战报数据：

{raw_report}

## 行情时效（必须严格遵守）
{session_hint}

## 持仓与操作纪律（必须遵守）
{holdings_context}

时段提示：{hint}

请输出微信战报用的「AI 综合解读」，要求：
1. 以「【AI 综合解读】」开头，全中文，2-3 段，总字数 ≤600 字
2. 第 1 段：若 A 股休市或非交易时段，首句必须点明「上一交易日（具体日期）收盘」或「今日休市」；再写大盘/地缘/原油/美股
3. 第 2 段：国内财经要闻精华（3-5 条合并叙述，快讯可称「最新」）
4. 第 3 段：结合持仓与纪律给出条件化关注点（禁止绝对买卖指令；严禁补仓梅花生物；严禁满仓新开仓；严禁追高等红线必须遵守）
5. 若战报含「今日选股 Top5」，须单独用 1-2 句概括次日重点观察标的（区分已持仓与观察池）
6. 禁止 markdown 表格，禁止英文；禁止把上一交易日收盘行情说成「今日盘中/今日收盘」"""

    content = call_deepseek(
        [
            {"role": "system", "content": "你是 A 股投资助手，输出简洁务实，全中文。"},
            {"role": "user", "content": prompt},
        ],
        max_tokens=900,
    )
    if not content.startswith("【AI 综合解读】"):
        content = f"【AI 综合解读】\n{content}"
    return content


def build_daily_briefing(slot: str, *, news_limit: int = 8, with_ai: bool = True) -> str:
    slot = slot if slot in SLOT_TITLES else datetime.now().strftime("%H:%M")
    now = datetime.now()

    try:
        index_content = _http_get("https://qt.gtimg.cn/q=sh000001", encoding="gbk")
    except Exception:  # noqa: BLE001
        index_content = ""
    session = detect_market_session(index_quote_content=index_content)
    title = session.slot_title(slot)

    all_news = fetch_macro_news(limit=max(news_limit * 2, 16), include_home=True)
    geo_news = _pick_geopolitics(all_news, limit=5)
    domestic_news = all_news[:news_limit]

    raw_sections = _build_raw_sections(
        session=session,
        geo_news=geo_news,
        domestic_news=domestic_news,
        news_limit=news_limit,
        slot=slot,
    )
    raw_report = "\n".join(raw_sections)

    header = [
        f"【{title} | {slot}】",
        f"生成时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
        session.header_note(),
    ]

    ai_block = ""
    if with_ai:
        if os.getenv("DEEPSEEK_API_KEY"):
            try:
                card = _resolve_holdings_card()
                _, holdings_context = load_full_decision_context(
                    holdings_path=card,
                )
                ai_block = summarize_briefing_with_deepseek(
                    slot=slot,
                    title=title,
                    raw_report=raw_report,
                    holdings_context=holdings_context,
                    session=session,
                )
            except Exception as exc:  # noqa: BLE001
                ai_block = f"【AI 综合解读】\n（生成失败：{exc}）"
        else:
            ai_block = "【AI 综合解读】\n（跳过：未配置 DEEPSEEK_API_KEY）"

    parts = [*header, ""]
    if ai_block:
        parts.extend([ai_block, "", "---", ""])
    parts.extend(raw_sections)
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成每日战报文本")
    parser.add_argument("--slot", default=datetime.now().strftime("%H:%M"), help="战报时段，如 09:00")
    parser.add_argument("--limit", type=int, default=8, help="国内财经条数")
    parser.add_argument("--output", type=Path, default=None, help="输出文件")
    parser.add_argument(
        "--macro-only",
        action="store_true",
        help="仅输出东财宏观快讯（兼容旧用法）",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="跳过 DeepSeek AI 综合解读",
    )
    args = parser.parse_args()

    try:
        if args.macro_only:
            items = fetch_macro_news(limit=args.limit, include_home=True)
            content = format_report(items)
        else:
            content = build_daily_briefing(
                args.slot,
                news_limit=args.limit,
                with_ai=not args.no_ai,
            )
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 战报生成失败: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content + "\n", encoding="utf-8")
        print(f"已写入: {args.output}", file=sys.stderr)
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
