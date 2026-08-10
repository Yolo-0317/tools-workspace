#!/usr/bin/env python3
"""牛马也智能 · 增长模型：大行情判定、周焦点、发表清单。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
FOCUS_PATH = ROOT / "data" / "wechat_mp_growth_focus.json"
TZ = ZoneInfo("Asia/Shanghai")

FOCUS_LABELS = {
    "news_title": "news 标题（热股名前置）",
    "news_lede": "news 头条开篇/完读",
    "tv_trial": "影视试跑（HBO/Netflix 日更 1 篇）",
    "distribution": "控群转发头条（每周 2 次）",
    "market_addon": "大行情同批 market",
    "sector_theme": "sector 主线选题",
    "stock_ai_cta": "引 stock-ai 工具",
}


@dataclass(frozen=True)
class MarketDayEvaluation:
    score: int
    signals: tuple[str, ...]
    recommend_market: bool
    command: str


@dataclass(frozen=True)
class GrowthFocus:
    week_focus: str
    week_started: str
    evening_mode: str
    distribution_enabled: bool
    distribution_times_per_week: int
    distribution_weekdays: tuple[int, ...]
    market_addon_enabled: bool
    market_min_signals: int
    read_target: int
    income_target_yuan: float
    stock_ai_cta_enabled: bool
    stock_ai_cta_kinds: tuple[str, ...]
    stock_ai_hub_base: str
    stock_ai_news_read_source: bool

    @property
    def focus_label(self) -> str:
        return FOCUS_LABELS.get(self.week_focus, self.week_focus)

    @property
    def evening_kinds(self) -> tuple[str, ...]:
        if self.evening_mode == "news_only":
            return ("news",)
        if self.evening_mode in {"hotspot_only", "hotspot"}:
            return ("hotspot",)
        return ("news", "hotspot")


def _default_focus_raw() -> dict[str, Any]:
    return {
        "version": 2,
        "week_focus": "news_title",
        "week_started": datetime.now(TZ).date().isoformat(),
        "evening_mode": "duo",
        "evening_mode_note": "duo=news+hotspot（默认）；news_only=交易日只推1篇news",
        "distribution": {"enabled": True, "times_per_week": 2, "weekdays": [1, 4]},
        "market_addon": {"enabled": True, "min_signals": 2},
        "stock_ai_cta": {"enabled": False, "kinds": ["news", "hotspot"]},
        "kpi": {"read_target": 85, "income_target_yuan": 1.0},
    }


def load_growth_focus(*, path: Path | None = None) -> GrowthFocus:
    p = path or FOCUS_PATH
    raw: dict[str, Any]
    if p.is_file():
        raw = json.loads(p.read_text(encoding="utf-8"))
    else:
        raw = _default_focus_raw()
    dist = raw.get("distribution") or {}
    mkt = raw.get("market_addon") or {}
    kpi = raw.get("kpi") or {}
    cta = raw.get("stock_ai_cta") or {}
    weekdays_raw = dist.get("weekdays") or [1, 4]
    weekdays = tuple(int(x) for x in weekdays_raw)
    kinds_raw = cta.get("kinds") or ["news", "dragons"]
    return GrowthFocus(
        week_focus=str(raw.get("week_focus") or "news_title"),
        week_started=str(raw.get("week_started") or datetime.now(TZ).date().isoformat()),
        evening_mode=str(raw.get("evening_mode") or "trilogy"),
        distribution_enabled=bool(dist.get("enabled", True)),
        distribution_times_per_week=int(dist.get("times_per_week") or 2),
        distribution_weekdays=weekdays,
        market_addon_enabled=bool(mkt.get("enabled", True)),
        market_min_signals=int(mkt.get("min_signals") or 2),
        read_target=int(kpi.get("read_target") or 85),
        income_target_yuan=float(kpi.get("income_target_yuan") or 1.0),
        stock_ai_cta_enabled=bool(cta.get("enabled", False)),
        stock_ai_cta_kinds=tuple(str(k) for k in kinds_raw),
        stock_ai_hub_base=str(cta.get("hub_base") or "https://hub.yoloworld.site:8883"),
        stock_ai_news_read_source=bool(cta.get("news_read_source", True)),
    )


def is_distribution_day(*, when: datetime | None = None) -> bool:
    focus = load_growth_focus()
    if not focus.distribution_enabled:
        return False
    dt = when or datetime.now(TZ)
    return dt.weekday() in focus.distribution_weekdays


def distribution_day_label(*, when: datetime | None = None) -> str:
    dt = when or datetime.now(TZ)
    names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return names[dt.weekday()]


def send_publish_reminder(*, force: bool = False) -> bool:
    """周二/周五 19:25 或 force：微信提醒群发+转群。"""
    if not force and not is_distribution_day():
        return False
    try:
        from scripts.tools.wechat_acp_push_text import send_wechat_acp_text
    except Exception:
        return False
    focus = load_growth_focus()
    mkt = evaluate_market_day()
    lines = [
        "【牛马也智能 · 发表提醒】",
        f"今天是{distribution_day_label()}（转群日之一）" if is_distribution_day() else "发表提醒",
        "",
        "1️⃣ mp 草稿箱 → 1 次群发（news→dragons→sector，或 +market）",
        "2️⃣ 群发后：把【头条 news】转到 2-3 个相关群（本周目标 "
        f"{focus.distribution_times_per_week} 次）",
    ]
    if mkt.recommend_market:
        lines.append(f"3️⃣ 大行情：先跑 market 再同批发 · {mkt.command}")
    if focus.stock_ai_cta_enabled:
        lines.append(f"4️⃣ 稿内已带看板链接 · {focus.stock_ai_hub_base}")
    try:
        send_wechat_acp_text("\n".join(lines))
        return True
    except Exception:
        return False


def evaluate_market_day(*, bundle: dict[str, Any] | None = None) -> MarketDayEvaluation:
    """大行情日：≥ min_signals 条信号 → 建议同批加 market(close)。"""
    focus = load_growth_focus()
    if bundle is None:
        try:
            from scripts.tools.portfolio_db import load_emotion_cycle_checklist

            bundle = load_emotion_cycle_checklist(checklist_slot="eod") or load_emotion_cycle_checklist()
        except Exception:
            bundle = None

    signals: list[str] = []
    if not bundle:
        return MarketDayEvaluation(
            score=0,
            signals=tuple(),
            recommend_market=False,
            command="uv run python -m scripts.tools.wechat_mp_draft --kind market --edition close",
        )

    hdr = bundle.get("header") or {}
    phase = str(hdr.get("phase") or "")
    limit_up = int(hdr.get("limit_up_count") or 0)
    limit_down = int(hdr.get("limit_down_count") or 0)
    max_board = int(hdr.get("max_board_height") or 0)
    theme_count = int(hdr.get("theme_count") or 0)
    explode = hdr.get("explode_rate_pct")
    main_theme = str(hdr.get("main_theme") or "").strip()

    if limit_up >= 45 or limit_down >= 25:
        signals.append(f"涨跌停极端（涨停{limit_up}/跌停{limit_down}）")
    if max_board >= 4:
        signals.append(f"连板高度 {max_board} 板")
    if phase in {"高潮", "退潮", "冰点"}:
        signals.append(f"情绪阶段·{phase}")
    if theme_count and theme_count <= 2 and main_theme:
        signals.append(f"主线清晰·{main_theme}")
    if explode is not None:
        try:
            if float(explode) >= 35:
                signals.append(f"炸板率 {float(explode):.0f}%")
        except (TypeError, ValueError):
            pass

    score = len(signals)
    min_sig = focus.market_min_signals if focus.market_addon_enabled else 99
    recommend = focus.market_addon_enabled and score >= min_sig
    cmd = "uv run python -m scripts.tools.wechat_mp_draft --kind market --edition close"
    return MarketDayEvaluation(
        score=score,
        signals=tuple(signals),
        recommend_market=recommend,
        command=cmd,
    )


def growth_theme_line_for_news() -> str | None:
    """供 news 开篇注入当日主线（growth 模型）。"""
    if os.getenv("WECHAT_MP_GROWTH_THEME_LEDE", "1").strip().lower() in ("0", "false", "no"):
        return None
    try:
        from scripts.tools.portfolio_db import load_emotion_cycle_checklist

        bundle = load_emotion_cycle_checklist(checklist_slot="eod") or load_emotion_cycle_checklist()
    except Exception:
        return None
    if not bundle:
        return None
    hdr = bundle.get("header") or {}
    theme = str(hdr.get("main_theme") or "").strip()
    phase = str(hdr.get("phase") or "").strip()
    if not theme and not phase:
        return None
    parts = []
    if phase:
        parts.append(f"情绪{phase}")
    if theme:
        parts.append(f"主线看{theme}")
    if not parts:
        return None
    return "今日盘面：" + "，".join(parts) + "；下面按热股人气序逐条对照快讯（非荐股）。"


def format_growth_notify_block(
    *,
    batch: str = "evening",
    news_title: str = "",
    news_intro: str = "",
) -> str:
    """18:20 推送后附增长清单（微信/飞书）。"""
    if batch not in {
        "evening",
        "weekend",
        "tv_trial",
        "hotspot_early",
        "hotspot_morning",
        "hotspot_afternoon",
        "hotspot_evening",
    }:
        return ""

    focus = load_growth_focus()
    mkt = evaluate_market_day()
    lines = [
        "",
        "—— 增长模型 ——",
        f"本周只改一类：{focus.focus_label}（自 {focus.week_started}）",
        f"KPI：日读 ≥{focus.read_target} · 概览入账 ≥¥{focus.income_target_yuan:.1f}",
    ]

    if focus.distribution_enabled:
        wd = focus.distribution_weekdays
        if len(wd) >= 7:
            wd_cn = "每日"
        else:
            wd_cn = "、".join(
                ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][d] for d in wd
            )
        lines.append(
            f"主动作：{'每日' if len(wd) >= 7 else f'每周 {focus.distribution_times_per_week} 次'}控群转发【头条 news】（{wd_cn}）"
        )
        if is_distribution_day():
            lines.append("📣 今日转群：群发后把【头条 news】转到 2-3 个群")

    title = (news_title or "").strip()
    intro = (news_intro or "").strip()
    if title or intro:
        try:
            from scripts.tools.wechat_mp_news_lede import format_group_share_copy

            share = format_group_share_copy(title=title, intro=intro)
            if share:
                lines.append("")
                lines.append("📣 转群文案（复制一句 + 附链接）：")
                lines.append(share)
        except Exception:
            pass

    if focus.stock_ai_cta_enabled:
        lines.append(
            f"stock-ai：稿末已附看板链接 · {focus.stock_ai_hub_base}（kinds={','.join(focus.stock_ai_cta_kinds)}）"
        )

    mode = focus.evening_mode
    if batch == "evening" and mode == "news_only":
        lines.append("批次模式：news_only（仅 1 篇 news，测阅读上限）")

    if batch == "evening":
        if mkt.recommend_market:
            lines.append("⚡ 大行情日：建议同批加 market(close)，仍 1 次通知")
            for sig in mkt.signals[:4]:
                lines.append(f"  · {sig}")
            lines.append(f"  命令：{mkt.command}")
        elif focus.market_addon_enabled and mkt.signals:
            lines.append(f"盘面信号 {mkt.score} 条（未达 {focus.market_min_signals}，可不加 market）")
            for sig in mkt.signals[:3]:
                lines.append(f"  · {sig}")
        else:
            lines.append("今日非大行情：evening 两篇同批即可（news + hotspot）")

    lines.append("流量主入账看概览「昨日 +X」，勿信明细行滞后")
    return "\n".join(lines)


def format_growth_check_report(*, batch: str | None = None) -> str:
    """终端/CLI 完整增长检查。"""
    focus = load_growth_focus()
    mkt = evaluate_market_day()
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    lines = [
        f"牛马也智能 · 增长检查 · {now}",
        "",
        f"本周焦点：{focus.focus_label}（{focus.week_started} 起）",
        f"KPI：阅读 ≥{focus.read_target} · 概览入账 ≥¥{focus.income_target_yuan:.1f}/日",
        "",
        "【大行情 · market】",
    ]
    if mkt.signals:
        for sig in mkt.signals:
            lines.append(f"  · {sig}")
    else:
        lines.append("  · （无 eod 数据或无信号）")
    if mkt.recommend_market:
        lines.append(f"  → 建议：{mkt.command}")
        lines.append("  → 与 evening 同一次群发，勿第二次通知")
    else:
        lines.append(f"  → 暂不强制 market（需 ≥{focus.market_min_signals} 条信号）")

    lines.extend(
        [
            "",
            "【主动分发】",
            f"  每周 {focus.distribution_times_per_week} 次 · 只转头条 news"
            if focus.distribution_enabled
            else "  已关闭（growth_focus.distribution.enabled=false）",
            "",
            "【傍晚草稿】",
            "  uv run python -m scripts.tools.wechat_mp_draft_batch --batch evening",
            "",
            "【复盘】",
            "  用户提供 mp token → analytics-sop 抓昨日阅读 + 概览入账",
        ]
    )
    if batch:
        lines.append(f"  当前批次：{batch}")
    return "\n".join(lines)
