"""投顾模式选股过滤 — 与 investment-agent/投顾主策略.md 对齐。"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[1] / "investment-agent"
ADVISOR_STRATEGY_PATH = AGENT_ROOT / "投顾主策略.md"

# 永久禁止（任何阶段）
EXCLUDE_CODES = frozenset({"600873"})  # 梅花生物

BUY_ACTIONS = frozenset({"强势关注", "观察买入", "小仓埋伏"})
TOP5_INTEL_ACTIONS = frozenset({"继续观察", "持有", "—", ""})

# 阶段 0 情报池：优先展示与回本主路径相关的行业
PHASE_0_INDUSTRY_KEYWORDS = (
    "电力",
    "公用",
    "银行",
    "燃气",
    "水电",
    "核电",
    "储能",
    "新能源",
)


@lru_cache(maxsize=1)
def load_advisor_strategy_text() -> str:
    if not ADVISOR_STRATEGY_PATH.exists():
        return ""
    return ADVISOR_STRATEGY_PATH.read_text(encoding="utf-8")


def parse_advisor_phase(text: str | None = None) -> int:
    """从投顾主策略解析当前阶段；默认 0（止血降仓，最安全）。"""
    body = text if text is not None else load_advisor_strategy_text()
    if not body:
        return 0
    if re.search(r"阶段\s*0", body):
        return 0
    if re.search(r"阶段\s*2", body):
        return 2
    if re.search(r"阶段\s*1", body):
        return 1
    return 0


def phase_label(phase: int | None = None) -> str:
    p = parse_advisor_phase() if phase is None else phase
    return {
        0: "6万投顾·阶段0止血降仓",
        1: "6万投顾·阶段1稳态组合",
        2: "6万投顾·阶段2进攻试探",
    }.get(p, f"阶段{p}")


def advisor_cap_action(
    action: str,
    code: str,
    *,
    phase: int | None = None,
    account_position_pct: float = 0.0,
) -> str:
    """按投顾阶段压制「建议动作」。"""
    p = parse_advisor_phase() if phase is None else phase
    code6 = str(code).split(".")[0].zfill(6)
    if code6 in EXCLUDE_CODES:
        return "禁止"
    act = (action or "").strip()
    if p == 0:
        if act in BUY_ACTIONS:
            return "继续观察"
        return act
    if p == 1:
        if account_position_pct > 75.0 and act in BUY_ACTIONS:
            return "继续观察"
        if account_position_pct > 60.0 and act == "观察买入":
            return "小仓埋伏"
        return act
    # 阶段 2：仍受执行卡红线，不在此放宽追高
    return act


def advisor_industry_score_bonus(industry: str | None, *, phase: int | None = None) -> float:
    """阶段 0 Top5 排序加分（情报池偏公用/电力）。"""
    p = parse_advisor_phase() if phase is None else phase
    if p != 0:
        return 0.0
    ind = str(industry or "")
    for kw in PHASE_0_INDUSTRY_KEYWORDS:
        if kw in ind:
            return 8.0
    return 0.0


def top5_eligible_actions(
    *,
    phase: int | None = None,
    account_position_pct: float = 0.0,
) -> frozenset[str] | None:
    """
    pick_selection_top 的 eligible_actions。
    阶段 0 → 仅情报动作；None → 使用调用方默认（可执行买入类）。
    """
    p = parse_advisor_phase() if phase is None else phase
    if p == 0:
        return TOP5_INTEL_ACTIONS
    if p == 1 and account_position_pct > 75.0:
        return TOP5_INTEL_ACTIONS
    return None


def selection_watch_sync_enabled(*, phase: int | None = None) -> bool:
    """阶段 0 不向 alert_rules 写入选股池新开监控。"""
    return parse_advisor_phase() if phase is None else phase >= 1


def sop_review_enabled(*, phase: int | None = None) -> bool:
    """各阶段均跑 Top5 东财 SOP（供战报与公众号稿）；阶段 0 仍压买入动作、不写监控。"""
    _ = parse_advisor_phase() if phase is None else phase
    return True


def ai_selection_review_enabled(*, phase: int | None = None) -> bool:
    """阶段 0 跳过 Top5 DeepSeek 简评（避免推送「候选新开仓」）；SOP 照常。"""
    return parse_advisor_phase() if phase is None else phase >= 1


def execution_card_probe_enabled(*, phase: int | None = None) -> bool:
    """阶段 0 不展示/不提升执行卡试探买入（仅保留减仓提示）。"""
    return parse_advisor_phase() if phase is None else phase >= 1


def advisor_signal_disclaimer(*, phase: int | None = None) -> str:
    """MCP / 规则信号工具追加的投顾约束说明。"""
    p = parse_advisor_phase() if phase is None else phase
    if p == 0:
        return (
            "\n\n【投顾约束·阶段0】止血降仓周：本信号仅为技术参考，"
            "不得作为新开仓依据；Top5=情报池；实盘以投顾主策略+持仓执行卡为准。"
        )
    if p == 1:
        return (
            "\n\n【投顾约束·阶段1】小仓试探阶段：新开须符合目标组合与仓位≤75%；"
            "实盘以投顾主策略+持仓执行卡为准。"
        )
    return "\n\n【投顾约束】实盘操作须符合投顾主策略阶段与持仓执行卡红线。"


def format_selection_banner(*, phase: int | None = None) -> str:
    p = parse_advisor_phase() if phase is None else phase
    if p == 0:
        return (
            f"🏥 {phase_label(p)} | 选股=情报池（建议动作已压为「继续观察」）| "
            "勿当必买；本周以减仓止血为主"
        )
    if p == 1:
        return f"🏥 {phase_label(p)} | 选股=小仓试探+换仓 | 仓位须≤75%才可买"
    return f"🏥 {phase_label(p)} | 选股可进攻试探 | 仍禁追高、禁补梅花"


PRINCIPAL_CNY = 60_000


def _extract_section(body: str, heading_prefix: str) -> str:
    m = re.search(
        rf"^{re.escape(heading_prefix)}[^\n]*\n(.*?)(?=\n## |\n---\s*\n|\Z)",
        body,
        re.S | re.M,
    )
    return m.group(1).strip() if m else ""


def parse_weekly_must_do(text: str | None = None) -> list[dict[str, str]]:
    """解析投顾主策略「本周必做」列表。"""
    body = text if text is not None else load_advisor_strategy_text()
    section = _extract_section(body, "## 十、本周必做")
    if not section:
        section = _extract_section(body, "## 十、")
    tasks: list[dict[str, str]] = []
    for line in section.splitlines():
        line = line.strip()
        m = re.match(r"^\d+\.\s+\*\*(.+?)\*\*[：:]?\s*(.+)$", line)
        if m:
            tasks.append(
                {
                    "title": m.group(1).strip(),
                    "detail": m.group(2).strip(),
                }
            )
    return tasks


def parse_weekly_forbidden(text: str | None = None) -> list[str]:
    body = text if text is not None else load_advisor_strategy_text()
    section = _extract_section(body, "## 【本周不做】")
    if not section:
        # 阶段 0 禁止项在 §三
        section = _extract_section(body, "**阶段 0 禁止**")
    items: list[str] = []
    for line in section.splitlines():
        line = line.strip().lstrip("-").strip()
        if line.startswith("❌") or line.startswith("-"):
            items.append(line.lstrip("❌").strip())
        elif line and not line.startswith("|"):
            items.append(line)
    return [x for x in items if x][:8]


def position_tier(position_ratio_pct: float | None) -> str:
    if position_ratio_pct is None:
        return "unknown"
    if position_ratio_pct > 75.0:
        return "A"
    if position_ratio_pct > 60.0:
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
    """看板 / 战报用投顾摘要（JSON 可序列化）。"""
    phase = parse_advisor_phase()
    assets = float(total_assets or 0)
    principal = float(PRINCIPAL_CNY)
    gap = round(principal - assets, 2)
    progress_pct = round(assets / principal * 100, 2) if principal else 0.0
    need_return_pct = round(gap / assets * 100, 2) if assets > 0 and gap > 0 else 0.0
    tier = position_tier(position_ratio_pct)

    selection_mode = "intel_only" if phase == 0 else ("probe" if phase == 1 else "offense")

    payload = {
        "principal_cny": principal,
        "phase": phase,
        "phase_label": phase_label(phase),
        "banner": format_selection_banner(phase=phase),
        "market_tier": "defense" if tier == "A" or phase == 0 else ("probe" if tier == "B" else "offense"),
        "position_tier": tier,
        "total_assets": assets if assets else None,
        "position_ratio_pct": position_ratio_pct,
        "holding_pnl": holding_pnl,
        "available_cash": available_cash,
        "gap_to_principal": gap if gap > 0 else 0.0,
        "progress_pct": progress_pct,
        "need_return_pct": need_return_pct,
        "selection": {
            "mode": selection_mode,
            "mode_label": {
                "intel_only": "情报池（非必买）",
                "probe": "小仓试探",
                "offense": "进攻试探",
            }.get(selection_mode, selection_mode),
            "sop_top5_enabled": sop_review_enabled(phase=phase),
            "watch_sync_enabled": selection_watch_sync_enabled(phase=phase),
        },
        "weekly_must_do": parse_weekly_must_do(),
        "weekly_forbidden": parse_weekly_forbidden() or [
            "补梅花、A 档纯新开仓",
            "追 17:30 Top5",
            "单日涨幅>5% 追高",
            "龙头实盘",
        ],
        "focus_codes": [
            {"code": "600873", "name": "梅花生物", "priority": "P0"},
            {"code": "600098", "name": "广州发展", "priority": "P1"},
            {"code": "600995", "name": "南网储能", "priority": "P2"},
            {"code": "000543", "name": "皖能电力", "priority": "P5"},
        ],
    }
    if include_diagnosis:
        try:
            from stock_ai.advisor_diagnosis import build_account_diagnosis

            payload["diagnosis"] = build_account_diagnosis(
                total_assets=total_assets,
                position_ratio_pct=position_ratio_pct,
                available_cash=available_cash,
                holding_pnl=holding_pnl,
                positions=positions,
                closes=closes,
                phase=phase,
            )
            from stock_ai.advisor_diagnosis import format_advisor_delivery_extended

            payload["delivery_template"] = format_advisor_delivery_extended(payload)
        except Exception:
            pass
    return payload


def advisor_discipline_alerts(
    *,
    position_ratio_pct: float | None,
    phase: int | None = None,
) -> list[dict[str, str]]:
    """投顾层纪律提醒（并入看板 discipline）。"""
    p = parse_advisor_phase() if phase is None else phase
    alerts: list[dict[str, str]] = []
    if p == 0:
        alerts.append(
            {
                "level": "warn",
                "title": "投顾阶段0",
                "message": "止血降仓周：优先减梅花/广州/锁南网利；Top5 仅情报，勿当必买",
                "code": None,
            }
        )
    if position_ratio_pct is not None and position_ratio_pct > 75.0:
        alerts.append(
            {
                "level": "danger",
                "title": "A 防守档",
                "message": f"仓位 {position_ratio_pct:.1f}% >75%，禁止纯新开仓（投顾+执行卡）",
                "code": None,
            }
        )
    if position_ratio_pct is not None and p == 0 and position_ratio_pct > 65.0:
        alerts.append(
            {
                "level": "warn",
                "title": "降仓目标",
                "message": f"阶段0 目标仓位 ≤65%，当前 {position_ratio_pct:.1f}%",
                "code": None,
            }
        )
    return alerts


def apply_advisor_to_results_row(
    row: dict,
    *,
    phase: int | None = None,
    account_position_pct: float = 0.0,
) -> dict:
    """就地更新结果行：建议动作 + 投顾备注。"""
    p = parse_advisor_phase() if phase is None else phase
    code = str(row.get("代码", "")).split(".")[0].zfill(6)
    before = str(row.get("建议动作", "")).strip()
    after = advisor_cap_action(before, code, phase=p, account_position_pct=account_position_pct)
    row["建议动作"] = after
    notes: list[str] = []
    if code in EXCLUDE_CODES:
        notes.append("永久排除")
    elif p == 0 and before in BUY_ACTIONS and after == "继续观察":
        notes.append("阶段0禁买")
    elif p == 1 and before != after:
        notes.append("阶段1仓位过滤")
    if notes:
        row["投顾备注"] = "·".join(notes)
    return row


def reapply_advisor_to_rows(
    rows: list[dict],
    *,
    phase: int | None = None,
    account_position_pct: float = 0.0,
) -> None:
    """批量就地应用投顾 cap（执行卡 B 档等后置步骤后须再调用）。"""
    p = parse_advisor_phase() if phase is None else phase
    for row in rows:
        apply_advisor_to_results_row(
            row, phase=p, account_position_pct=account_position_pct
        )
