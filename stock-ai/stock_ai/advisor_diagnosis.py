"""专业投顾能力 — 账户诊断、配置缺口、风险预算、投教（对齐中证协投顾六大职责）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stock_ai.advisor_selection import EXCLUDE_CODES, PRINCIPAL_CNY, parse_advisor_phase

# 电力/公用集群（与投顾主策略 §四 一致）
POWER_KEYWORDS = ("电力", "储能", "核电", "广核", "发展", "能源", "皖能", "宝新", "南网")

PHASE_POSITION_TARGET = {0: 40.0, 1: 50.0, 2: 60.0}
PHASE_CASH_TARGET_MIN = {0: 60.0, 1: 50.0, 2: 40.0}
MAX_SINGLE_PCT_PHASE = {0: 4.0, 1: 8.0, 2: 8.0}
MAX_SECTOR_CLUSTER_PCT = 35.0
RISK_BUDGET_PCT = 0.5  # 单笔计划亏损 ≤ 10 万实投预算的 0.5%


@dataclass
class PositionSnapshot:
    code: str
    name: str
    shares: int
    cost: float
    market_value: float
    weight_pct: float
    pnl: float | None = None


def _code6(code: str) -> str:
    return str(code).split(".")[0].zfill(6)


def _is_power_name(name: str) -> bool:
    n = str(name or "")
    return any(kw in n for kw in POWER_KEYWORDS)


def _health_label(score: int) -> str:
    if score >= 75:
        return "良好"
    if score >= 55:
        return "尚可"
    if score >= 35:
        return "需改善"
    return "高风险"


def _position_field(p: Any, key: str, default: Any = "") -> Any:
    if isinstance(p, dict):
        return p.get(key, default)
    return getattr(p, key, default)


def build_position_snapshots(
    positions: list[Any],
    *,
    total_assets: float,
    closes: dict[str, float] | None = None,
) -> list[PositionSnapshot]:
    """持仓 → 市值权重（closes 缺失时用成本价估算）。"""
    assets = max(float(total_assets or 0), 1.0)
    closes = closes or {}
    snaps: list[PositionSnapshot] = []
    for p in positions:
        code = _code6(str(_position_field(p, "code", "")))
        if len(code) != 6:
            continue
        name = str(_position_field(p, "name", code))
        shares = int(_position_field(p, "shares", 0) or 0)
        cost = float(_position_field(p, "cost", 0) or 0)
        price = closes.get(code, cost)
        mv = price * shares
        pnl = (price - cost) * shares if cost and shares else None
        snaps.append(
            PositionSnapshot(
                code=code,
                name=name,
                shares=shares,
                cost=cost,
                market_value=mv,
                weight_pct=round(mv / assets * 100, 2),
                pnl=round(pnl, 2) if pnl is not None else None,
            )
        )
    snaps.sort(key=lambda s: s.market_value, reverse=True)
    return snaps


def build_account_diagnosis(
    *,
    total_assets: float | None,
    position_ratio_pct: float | None,
    available_cash: float | None = None,
    holding_pnl: float | None = None,
    positions: list[Any] | None = None,
    closes: dict[str, float] | None = None,
    phase: int | None = None,
) -> dict[str, Any]:
    """
    专业账户诊断（需求分析 + 组合管理 + 风险管理）。
    参考：中证协投顾类能力素质模型 — 账户诊断、资产配置、风险合规、投资者教育。
    """
    p = parse_advisor_phase() if phase is None else phase
    assets = float(total_assets or 0)
    pos_pct = float(position_ratio_pct or 0)
    cash = float(available_cash or 0)
    cash_pct = round(cash / assets * 100, 2) if assets > 0 else 0.0

    target_pos = PHASE_POSITION_TARGET.get(p, 65.0)
    target_cash_min = PHASE_CASH_TARGET_MIN.get(p, 25.0)
    max_single = MAX_SINGLE_PCT_PHASE.get(p, 15.0)

    issues: list[dict[str, str]] = []
    score = 100

    if assets <= 0:
        return {
            "health_score": 0,
            "health_label": "无数据",
            "issues": [{"severity": "warn", "title": "账户未同步", "detail": "请运行 sync_portfolio_from_card"}],
            "concentration": {},
            "allocation_gap": {},
            "risk_budget": {},
            "education_tip": "先同步持仓，投顾才能做账户诊断。",
            "rebalance_priority": [],
        }

    snaps = build_position_snapshots(positions or [], total_assets=assets, closes=closes)
    max_snap = snaps[0] if snaps else None
    power_pct = round(
        sum(s.weight_pct for s in snaps if _is_power_name(s.name)),
        2,
    )

    if pos_pct > target_pos:
        gap = round(pos_pct - target_pos, 1)
        issues.append(
            {
                "severity": "high" if p == 0 else "warn",
                "title": "仓位超标",
                "detail": f"现 {pos_pct:.1f}% > 阶段{p}目标 {target_pos:.0f}%（需降 {gap:.1f}pp）",
            }
        )
        score -= min(30, int(gap * 1.5))

    if cash_pct < target_cash_min and p <= 1:
        issues.append(
            {
                "severity": "warn",
                "title": "现金缓冲不足",
                "detail": f"可用 {cash_pct:.1f}% < 目标 ≥{target_cash_min:.0f}%（机动弹药偏少）",
            }
        )
        score -= 10

    if max_snap and max_snap.weight_pct > max_single:
        issues.append(
            {
                "severity": "high" if max_snap.code in EXCLUDE_CODES else "warn",
                "title": "单票集中",
                "detail": f"{max_snap.name}({max_snap.code}) 占 {max_snap.weight_pct:.1f}% > 上限 {max_single:.0f}%",
            }
        )
        score -= min(25, int((max_snap.weight_pct - max_single) * 1.2))

    if power_pct > MAX_SECTOR_CLUSTER_PCT:
        issues.append(
            {
                "severity": "warn",
                "title": "电力集群过重",
                "detail": f"电力/公用相关合计约 {power_pct:.1f}% > {MAX_SECTOR_CLUSTER_PCT:.0f}%",
            }
        )
        score -= 12

    for code in EXCLUDE_CODES:
        snap = next((s for s in snaps if s.code == code), None)
        if snap and snap.shares > 0:
            issues.append(
                {
                    "severity": "high",
                    "title": "毒瘤敞口",
                    "detail": f"{snap.name} 仍持仓，投顾主策略要求退出",
                }
            )
            score -= 20

    if holding_pnl is not None and float(holding_pnl) < -assets * 0.03:
        issues.append(
            {
                "severity": "warn",
                "title": "浮亏拖累",
                "detail": f"持仓浮亏 {float(holding_pnl):+.0f} 元，优先处理深套票",
            }
        )
        score -= 8

    score = max(0, min(100, score))
    max_loss_cny = round(PRINCIPAL_CNY * RISK_BUDGET_PCT / 100, 0)
    worst = min(snaps, key=lambda s: s.pnl or 0) if snaps else None
    worst_loss = abs(worst.pnl) if worst and worst.pnl and worst.pnl < 0 else 0

    rebalance: list[str] = []
    if p == 0:
        rebalance = ["完成库存持仓交易建档", "不新开仓", "隔离资格资产与交易预算"]
    elif max_snap and max_snap.weight_pct > max_single:
        rebalance.append(f"降 {max_snap.name} 至 ≤{max_single:.0f}%")
    if pos_pct > target_pos:
        rebalance.append(f"总仓位降至 ≤{target_pos:.0f}%")

    education = _education_tip(p, issues, pos_pct, target_pos)

    return {
        "health_score": score,
        "health_label": _health_label(score),
        "issues": issues[:6],
        "concentration": {
            "holding_count": len(snaps),
            "max_single_code": max_snap.code if max_snap else None,
            "max_single_name": max_snap.name if max_snap else None,
            "max_single_pct": max_snap.weight_pct if max_snap else None,
            "power_sector_pct": power_pct,
            "top3": [
                {"code": s.code, "name": s.name, "weight_pct": s.weight_pct, "pnl": s.pnl}
                for s in snaps[:3]
            ],
        },
        "allocation_gap": {
            "phase": p,
            "current_position_pct": pos_pct,
            "target_position_pct": target_pos,
            "position_gap_pp": round(pos_pct - target_pos, 1) if pos_pct > target_pos else 0,
            "current_cash_pct": cash_pct,
            "target_cash_pct_min": target_cash_min,
        },
        "risk_budget": {
            "max_loss_per_trade_pct": RISK_BUDGET_PCT,
            "max_loss_per_trade_cny": max_loss_cny,
            "worst_holding_code": worst.code if worst else None,
            "worst_holding_loss_cny": worst_loss,
            "within_budget": worst_loss <= max_loss_cny if worst_loss else True,
        },
        "education_tip": education,
        "rebalance_priority": rebalance[:4],
    }


def _education_tip(phase: int, issues: list[dict], pos_pct: float, target_pos: float) -> str:
    if phase == 0:
        return "交易建档阶段的成功标准是写清每笔失效条件，不是预测下一只涨停。"
    if any(i["title"] == "单票集中" for i in issues):
        return "投教：单票权重过高时，一次误判就可能吃掉数周收益；分散是控风险，不是分散注意力。"
    return "交易提示必须含入场条件、失效条件和仓位上限；执行纪律比预测涨跌更重要。"


def format_diagnosis_briefing(diagnosis: dict[str, Any]) -> str:
    """战报 / 微信用短诊断段。"""
    if not diagnosis or diagnosis.get("health_label") == "无数据":
        return ""
    lines = [
        f"【账户诊断】健康度 {diagnosis.get('health_score')}/100（{diagnosis.get('health_label')}）",
    ]
    conc = diagnosis.get("concentration") or {}
    if conc.get("max_single_name"):
        lines.append(
            f"· 最大单票 {conc['max_single_name']} {conc.get('max_single_pct')}%"
            f" | 电力集群 {conc.get('power_sector_pct')}%"
        )
    gap = diagnosis.get("allocation_gap") or {}
    if gap.get("position_gap_pp", 0) > 0:
        lines.append(
            f"· 仓位缺口：现 {gap.get('current_position_pct')}% → 目标 ≤{gap.get('target_position_pct')}%"
        )
    rb = diagnosis.get("rebalance_priority") or []
    if rb:
        lines.append(f"· 再平衡优先：{' → '.join(rb)}")
    tip = diagnosis.get("education_tip")
    if tip:
        lines.append(tip)
    return "\n".join(lines)


def format_advisor_delivery_extended(advisor: dict[str, Any]) -> str:
    """Agent / 战报用扩展交付格式（原五段 + 诊断三要素）。"""
    diag = advisor.get("diagnosis") or {}
    lines = [
        "【市场一句话】（档位 + 主线 + 情绪）",
        (
            f"【交易资金】实投预算 ¥{advisor.get('principal_cny') or '—'}；"
            "资格资产与交易仓位分开核算"
        ),
    ]
    if diag:
        lines.append(
            f"【账户诊断】{diag.get('health_score')}/100 {diag.get('health_label')}"
            f" | 单票最大 {diag.get('concentration', {}).get('max_single_pct') or '—'}%"
        )
        gap = diag.get("allocation_gap") or {}
        if gap.get("position_gap_pp"):
            lines.append(
                f"【风险缺口】账户仓位需降 {gap['position_gap_pp']}pp"
                f"（目标 ≤{gap.get('target_position_pct')}%）"
            )
        rb = diag.get("rebalance_priority") or []
        if rb:
            lines.append(f"【再平衡】{' → '.join(rb)}")
    lines.extend(
        [
            "【本周必做 1～3 条】代码+股数+条件+理由",
            "【本周不做】",
            f"【风险预算】单笔计划亏损 ≤ 实投预算 {RISK_BUDGET_PCT}%（约 ¥{diag.get('risk_budget', {}).get('max_loss_per_trade_cny', '—')}）",
        ]
    )
    if diag.get("education_tip"):
        lines.append(diag["education_tip"])
    lines.append("【触发价附录】摘自持仓执行卡")
    return "\n".join(lines)


def load_diagnosis_from_db(*, skip_live_quotes: bool = False) -> dict[str, Any]:
    """从 MySQL 持仓 + 账户快照构建诊断（供看板 / 战报）。"""
    try:
        from scripts.tools.portfolio_db import load_account, load_latest_closes, load_positions
    except ImportError:
        return build_account_diagnosis(total_assets=None, position_ratio_pct=None)

    acct = load_account()
    positions = load_positions()
    if not acct:
        return build_account_diagnosis(total_assets=None, position_ratio_pct=None)

    ratio = acct.position_ratio
    pos_pct = None
    if ratio is not None:
        r = float(ratio)
        pos_pct = r * 100 if r <= 1.0 else r

    closes: dict[str, float] = {}
    if positions and not skip_live_quotes:
        codes = [p.code for p in positions]
        try:
            closes = load_latest_closes(codes)
        except Exception:
            closes = {}

    return build_account_diagnosis(
        total_assets=acct.total_assets,
        position_ratio_pct=pos_pct,
        available_cash=acct.available_cash,
        holding_pnl=acct.holding_pnl,
        positions=positions,
        closes=closes,
    )
