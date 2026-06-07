"""投顾周五周复盘 — 生成、落库、看板读取。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from stock_ai.advisor_diagnosis import format_advisor_delivery_extended, format_diagnosis_briefing
from stock_ai.advisor_selection import (
    PRINCIPAL_CNY,
    build_advisor_dashboard_payload,
    parse_advisor_phase,
)

TZ = ZoneInfo("Asia/Shanghai")


def shanghai_today() -> date:
    return datetime.now(TZ).date()


def _position_ratio_pct(ratio: float | None) -> float | None:
    if ratio is None:
        return None
    r = float(ratio)
    return r * 100 if r <= 1.0 else r


def _week_range(end: date) -> tuple[date, date]:
    start = end - timedelta(days=6)
    return start, end


def _week_account_stats(end: date) -> dict[str, Any]:
    try:
        from scripts.tools.portfolio_db import load_portfolio_snapshot_series
    except ImportError:
        return {"note": "portfolio_db 不可用"}

    start, end_d = _week_range(end)
    series = load_portfolio_snapshot_series(
        date_from=start,
        date_to=end_d,
        snapshot_slot="eod",
    )
    if len(series) < 2:
        return {
            "note": "本周 eod 快照不足（需 portfolio_account_daily）",
            "snapshots": len(series),
        }
    first = series[0]
    last = series[-1]
    a0 = float(first.get("total_assets") or 0)
    a1 = float(last.get("total_assets") or 0)
    delta = round(a1 - a0, 2)
    pct = round(delta / a0 * 100, 2) if a0 > 0 else 0.0
    p0 = first.get("position_ratio")
    p1 = last.get("position_ratio")
    pr0 = _position_ratio_pct(float(p0) if p0 is not None else None)
    pr1 = _position_ratio_pct(float(p1) if p1 is not None else None)
    return {
        "week_start": str(first.get("snapshot_date")),
        "week_end": str(last.get("snapshot_date")),
        "assets_start": a0,
        "assets_end": a1,
        "assets_delta": delta,
        "assets_delta_pct": pct,
        "position_start_pct": pr0,
        "position_end_pct": pr1,
        "position_delta_pp": round(pr1 - pr0, 1) if pr0 is not None and pr1 is not None else None,
        "snapshots": len(series),
    }


def _format_must_do_checklist(tasks: list[dict[str, str]]) -> list[str]:
    lines = ["## 本周必做对照", ""]
    if not tasks:
        lines.append("- （投顾主策略未解析到本周必做，请检查 §十）")
        return lines
    for i, t in enumerate(tasks, 1):
        title = t.get("title") or "—"
        detail = t.get("detail") or ""
        lines.append(f"{i}. **{title}** — {detail}")
        lines.append("   - 执行：□ 已完成  □ 部分  □ 未做（下周继续）")
    lines.append("")
    lines.append(
        "> 对照方式：东方财富证券账户成交记录 + 持仓执行卡监控触发；"
        "Agent 对话可逐项核对。"
    )
    return lines


def _format_week_stats_block(stats: dict[str, Any]) -> list[str]:
    lines = ["## 本周账户变化（eod 快照）", ""]
    if stats.get("note"):
        lines.append(f"- {stats['note']}")
        return lines
    lines.extend(
        [
            f"- 区间 {stats.get('week_start')} → {stats.get('week_end')}（{stats.get('snapshots')} 个快照）",
            f"- 总资产 {stats.get('assets_start'):.0f} → {stats.get('assets_end'):.0f} 元"
            f"（{stats.get('assets_delta'):+.0f}，{stats.get('assets_delta_pct'):+.2f}%）",
            f"- 本金锚点 {PRINCIPAL_CNY} 元；距目标还差约 "
            f"{max(0, PRINCIPAL_CNY - float(stats.get('assets_end') or 0)):.0f} 元",
        ]
    )
    if stats.get("position_end_pct") is not None:
        dpp = stats.get("position_delta_pp")
        dpp_s = f"{dpp:+.1f}pp" if dpp is not None else "—"
        lines.append(
            f"- 仓位 {stats.get('position_start_pct')}% → {stats.get('position_end_pct')}%（{dpp_s}）"
        )
    return lines


def _maybe_ai_review(report_md: str, advisor: dict[str, Any]) -> str:
    try:
        from scripts.tools.deepseek_client import call_deepseek, is_llm_configured
    except ImportError:
        return ""
    if not is_llm_configured():
        return ""
    prompt = (
        "你是 6 万账户 A 股投顾，请基于以下周复盘素材，写 150～250 字「投后陪伴」小结：\n"
        "1) 本周做得好的 1 点 2) 最大风险 1 点 3) 下周 1 个最重要动作\n"
        "全中文，决策支持非投资建议，禁止绝对买卖指令。\n\n"
        f"{report_md[:6000]}"
    )
    try:
        return call_deepseek(
            [
                {"role": "system", "content": "简洁务实的中文投顾。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.4,
        ).strip()
    except Exception:
        return ""


def build_weekly_review_report(
    *,
    review_date: date | None = None,
    with_ai: bool = True,
) -> dict[str, Any]:
    """生成周五周复盘（Markdown + 结构化 JSON）。"""
    review_date = review_date or shanghai_today()
    phase = parse_advisor_phase()

    try:
        from scripts.tools.portfolio_db import load_account, load_latest_closes, load_positions
    except ImportError:
        acct = None
        positions = []
        closes = {}
    else:
        acct = load_account()
        positions = load_positions()
        closes = {}
        if positions:
            try:
                closes = load_latest_closes([p.code for p in positions])
            except Exception:
                closes = {}

    ratio = _position_ratio_pct(acct.position_ratio if acct else None)
    advisor = build_advisor_dashboard_payload(
        total_assets=acct.total_assets if acct else None,
        position_ratio_pct=ratio,
        holding_pnl=acct.holding_pnl if acct else None,
        available_cash=acct.available_cash if acct else None,
        positions=positions,
        closes=closes,
    )
    diagnosis = advisor.get("diagnosis") or {}
    week_stats = _week_account_stats(review_date)

    iso_year, iso_week, _ = review_date.isocalendar()
    title = f"{iso_year}年第{iso_week}周复盘 · {advisor.get('phase_label', '阶段0')}"

    body_parts: list[str] = [
        f"# {title}",
        "",
        f"**复盘日** {review_date.isoformat()} · **阶段** {phase}",
        "",
        "## 投顾交付摘要",
        "",
        format_advisor_delivery_extended(advisor),
        "",
        *_format_week_stats_block(week_stats),
        "",
    ]
    diag_text = format_diagnosis_briefing(diagnosis)
    if diag_text:
        body_parts.extend([diag_text, ""])
    body_parts.extend(_format_must_do_checklist(advisor.get("weekly_must_do") or []))
    body_parts.extend(["", "## 下周关注", ""])
    rb = (diagnosis.get("rebalance_priority") or []) if diagnosis else []
    if rb:
        body_parts.append("- 再平衡：" + " → ".join(rb))
    else:
        body_parts.append("- 维持阶段纪律；完成本周必做剩余项")
    if phase == 0:
        body_parts.append("- 阶段 1 门槛：仓位 ≤65% 且梅花风险解除")

    report_md = "\n".join(body_parts)
    ai_summary = _maybe_ai_review(report_md, advisor) if with_ai else ""
    if ai_summary:
        report_md += "\n\n## AI 投后陪伴\n\n" + ai_summary

    report_json = {
        "week_end_date": review_date.isoformat(),
        "phase": phase,
        "title": title,
        "health_score": diagnosis.get("health_score"),
        "week_stats": week_stats,
        "advisor_banner": advisor.get("banner"),
        "ai_summary": ai_summary or None,
    }

    return {
        "week_end_date": review_date.isoformat(),
        "phase": phase,
        "title": title,
        "health_score": diagnosis.get("health_score"),
        "report_md": report_md,
        "report_json": report_json,
        "ai_summary": ai_summary,
    }


def public_weekly_review_row(row: dict[str, Any]) -> dict[str, Any]:
    """看板展示：Markdown + 摘要，省略完整 JSON。"""
    js = row.get("report_json") or {}
    if isinstance(js, str):
        try:
            js = json.loads(js)
        except Exception:
            js = {}
    return {
        "week_end_date": row.get("week_end_date"),
        "phase": row.get("phase"),
        "title": row.get("title"),
        "health_score": row.get("health_score"),
        "report_md": row.get("report_md") or "",
        "week_stats": js.get("week_stats"),
        "ai_summary": js.get("ai_summary"),
        "created_at": row.get("created_at"),
    }


def load_latest_weekly_review_public() -> dict[str, Any] | None:
    try:
        from scripts.tools.portfolio_db import latest_advisor_weekly_review

        row = latest_advisor_weekly_review()
    except Exception:
        return None
    if not row:
        return None
    return public_weekly_review_row(row)


def save_weekly_review(report: dict[str, Any], *, review_date: date | None = None) -> None:
    from scripts.tools.portfolio_db import save_advisor_weekly_review

    d = review_date or date.fromisoformat(str(report["week_end_date"])[:10])
    save_advisor_weekly_review(
        week_end_date=d,
        phase=int(report.get("phase") or 0),
        title=str(report.get("title") or ""),
        health_score=report.get("health_score"),
        report_md=str(report.get("report_md") or ""),
        report_json=report.get("report_json") or {},
    )


def write_weekly_review_file(report: dict[str, Any], *, root: Any = None) -> str:
    from pathlib import Path

    base = Path(root) if root else Path(__file__).resolve().parents[1]
    out_dir = base / "output" / "advisor_weekly"
    out_dir.mkdir(parents=True, exist_ok=True)
    d = str(report["week_end_date"])[:10]
    path = out_dir / f"advisor_weekly_{d}.md"
    path.write_text(str(report.get("report_md") or ""), encoding="utf-8")
    return str(path)
