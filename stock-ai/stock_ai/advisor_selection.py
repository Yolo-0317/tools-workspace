"""交易型选股门控：收盘候选池与次日盘中确认分离。"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[1] / "investment-agent"
ADVISOR_STRATEGY_PATH = AGENT_ROOT / "投顾主策略.md"

# 不再按历史个股永久封禁；公告、监管和流动性风险由当日候选审核排除。
EXCLUDE_CODES = frozenset()
BUY_ACTIONS = frozenset({"强势关注", "观察买入", "小仓埋伏"})
WATCH_ACTIONS = frozenset({"交易观察", "次日确认", "持有", "—", ""})
PRINCIPAL_CNY = 100_000


@lru_cache(maxsize=1)
def load_advisor_strategy_text() -> str:
    if not ADVISOR_STRATEGY_PATH.exists():
        return ""
    return ADVISOR_STRATEGY_PATH.read_text(encoding="utf-8")


def parse_advisor_phase(text: str | None = None) -> int:
    """读取明确的当前交易阶段；默认 0，避免无策略时产生交易信号。"""
    body = text if text is not None else load_advisor_strategy_text()
    match = re.search(r"当前交易阶段\s*[：:]\s*阶段\s*([0-2])", body)
    if match:
        return int(match.group(1))
    match = re.search(r"^###?\s*阶段\s*([0-2])\s*[（(]?当前", body, re.M)
    return int(match.group(1)) if match else 0


def phase_label(phase: int | None = None) -> str:
    p = parse_advisor_phase() if phase is None else phase
    return {
        0: "交易型系统·阶段0建档",
        1: "交易型系统·阶段1小仓验证",
        2: "交易型系统·阶段2规则扩容",
    }.get(p, f"交易型系统·阶段{p}")


def advisor_cap_action(
    action: str,
    code: str,
    *,
    phase: int | None = None,
    account_position_pct: float = 0.0,
) -> str:
    """将日线动作降级为候选状态，禁止收盘排名直接变成买入指令。"""
    _ = code
    p = parse_advisor_phase() if phase is None else phase
    act = (action or "").strip()
    if p == 0 and act in BUY_ACTIONS:
        return "交易观察"
    if p >= 1 and act in BUY_ACTIONS:
        return "次日确认"
    if account_position_pct > 75.0 and act in BUY_ACTIONS:
        return "交易观察"
    return act


def advisor_industry_score_bonus(industry: str | None, *, phase: int | None = None) -> float:
    """不再偏置能源等旧主题；题材强度由当日候选审核决定。"""
    _ = industry, phase
    return 0.0


def top5_eligible_actions(
    *,
    phase: int | None = None,
    account_position_pct: float = 0.0,
) -> frozenset[str] | None:
    """阶段 0 仅看观察项；阶段 1+ 保留候选以供盘中二次确认。"""
    p = parse_advisor_phase() if phase is None else phase
    if p == 0 or account_position_pct > 75.0:
        return WATCH_ACTIONS
    return None


def selection_watch_sync_enabled(*, phase: int | None = None) -> bool:
    return (parse_advisor_phase() if phase is None else phase) >= 1


def sop_review_enabled(*, phase: int | None = None) -> bool:
    _ = phase
    return os.getenv("DISABLE_SOP_TOP5", "0").strip().lower() not in ("1", "true", "yes", "on")


def ai_selection_review_enabled(*, phase: int | None = None) -> bool:
    return (parse_advisor_phase() if phase is None else phase) >= 1


def execution_card_probe_enabled(*, phase: int | None = None) -> bool:
    return (parse_advisor_phase() if phase is None else phase) >= 1


def advisor_signal_disclaimer(*, phase: int | None = None) -> str:
    p = parse_advisor_phase() if phase is None else phase
    if p == 0:
        return "\n\n【交易约束】当前仅建档与观察，禁止根据筛选结果新开仓。"
    return "\n\n【交易约束】收盘候选不是买入指令；次日须完成题材、板块、量价资金、筹码与盘口确认。"


def format_selection_banner(*, phase: int | None = None) -> str:
    p = parse_advisor_phase() if phase is None else phase
    if p == 0:
        return f"{phase_label(p)} | 选股=交易观察，先建档不新开"
    if p == 1:
        return f"{phase_label(p)} | 选股=次日候选池，盘中确认后才允许小仓试错"
    return f"{phase_label(p)} | 选股=次日候选池，仍受单笔风险与总暴露上限约束"


def _extract_section(body: str, heading_prefix: str) -> str:
    match = re.search(
        rf"^{re.escape(heading_prefix)}[^\n]*\n(.*?)(?=\n## |\n---\s*\n|\Z)",
        body,
        re.S | re.M,
    )
    return match.group(1).strip() if match else ""


def parse_weekly_must_do(text: str | None = None) -> list[dict[str, str]]:
    body = text if text is not None else load_advisor_strategy_text()
    section = _extract_section(body, "## 十、本周必做")
    tasks: list[dict[str, str]] = []
    for line in section.splitlines():
        match = re.match(r"^\d+\.\s+\*\*(.+?)\*\*[：:]?\s*(.+)$", line.strip())
        if match:
            tasks.append({"title": match.group(1).strip(), "detail": match.group(2).strip()})
    return tasks


def parse_weekly_forbidden(text: str | None = None) -> list[str]:
    body = text if text is not None else load_advisor_strategy_text()
    section = _extract_section(body, "## 【本周不做】")
    return [line.strip().lstrip("-").strip() for line in section.splitlines() if line.strip().startswith("-")][:8]


def position_tier(position_ratio_pct: float | None) -> str:
    if position_ratio_pct is None:
        return "unknown"
    if position_ratio_pct > 75.0:
        return "A"
    if position_ratio_pct > 50.0:
        return "B"
    return "C"


def build_advisor_dashboard_payload(
    *,
    total_assets: float | None = None,
    position_ratio_pct: float | None = None,
    holding_pnl: float | None = None,
    available_cash: float | None = None,
    include_diagnosis: bool = True,
    positions: list[Any] | None = None,
    closes: dict[str, float] | None = None,
) -> dict:
    phase = parse_advisor_phase()
    assets = float(total_assets or 0)
    tier = position_tier(position_ratio_pct)
    selection_mode = "watch_only" if phase == 0 else "next_day_confirmation"
    payload = {
        "principal_cny": float(PRINCIPAL_CNY),
        "phase": phase,
        "phase_label": phase_label(phase),
        "banner": format_selection_banner(phase=phase),
        "market_tier": "observe" if phase == 0 else "trade",
        "position_tier": tier,
        "total_assets": assets or None,
        "position_ratio_pct": position_ratio_pct,
        "holding_pnl": holding_pnl,
        "available_cash": available_cash,
        "gap_to_principal": 0.0,
        "progress_pct": 0.0,
        "need_return_pct": 0.0,
        "selection": {
            "mode": selection_mode,
            "mode_label": "仅观察" if phase == 0 else "次日盘中确认",
            "sop_top5_enabled": sop_review_enabled(phase=phase),
            "watch_sync_enabled": selection_watch_sync_enabled(phase=phase),
        },
        "weekly_must_do": parse_weekly_must_do(),
        "weekly_forbidden": parse_weekly_forbidden() or ["不补仓摊薄成本", "不追封板", "不把资格资产当交易资金"],
        "focus_codes": [],
    }
    if include_diagnosis:
        try:
            from stock_ai.advisor_diagnosis import build_account_diagnosis, format_advisor_delivery_extended

            payload["diagnosis"] = build_account_diagnosis(
                total_assets=total_assets,
                position_ratio_pct=position_ratio_pct,
                available_cash=available_cash,
                holding_pnl=holding_pnl,
                positions=positions,
                closes=closes,
                phase=phase,
            )
            payload["delivery_template"] = format_advisor_delivery_extended(payload)
        except Exception:
            pass
    return payload


def advisor_discipline_alerts(*, position_ratio_pct: float | None, phase: int | None = None) -> list[dict[str, str]]:
    p = parse_advisor_phase() if phase is None else phase
    alerts: list[dict[str, str]] = []
    if p == 0:
        alerts.append({"level": "warn", "title": "交易建档阶段", "message": "当前候选只做观察，尚未开放新交易仓。", "code": None})
    if position_ratio_pct is not None and position_ratio_pct > 75.0:
        alerts.append({"level": "danger", "title": "账户仓位过高", "message": f"账户仓位 {position_ratio_pct:.1f}% >75%，暂停新增风险。", "code": None})
    return alerts


def apply_advisor_to_results_row(row: dict, *, phase: int | None = None, account_position_pct: float = 0.0) -> dict:
    p = parse_advisor_phase() if phase is None else phase
    before = str(row.get("建议动作", "")).strip()
    row["建议动作"] = advisor_cap_action(before, str(row.get("代码", "")), phase=p, account_position_pct=account_position_pct)
    if before in BUY_ACTIONS:
        row["投顾备注"] = "收盘候选；次日须完成题材、板块、量价资金、筹码与盘口确认"
    return row


def reapply_advisor_to_rows(rows: list[dict], *, phase: int | None = None, account_position_pct: float = 0.0) -> None:
    for row in rows:
        apply_advisor_to_results_row(row, phase=phase, account_position_pct=account_position_pct)
