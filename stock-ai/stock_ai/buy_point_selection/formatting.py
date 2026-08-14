"""Text rendering with strict trade-qualification boundaries."""

from __future__ import annotations

from .service import BuyPointSelectionResult


def render_buy_point_report(value: BuyPointSelectionResult) -> str:
    lines = ["正式候选"]
    if not value.qualified:
        lines.append("无")
    for item in value.qualified:
        if item.plan is None:
            raise ValueError("qualified row is missing its price plan")
        lines.append(
            " ".join(
                (
                    item.code,
                    item.name,
                    item.setup.setup_type.value,
                    f"触发价 {item.plan.trigger_price:.2f}",
                    f"失效价 {item.plan.invalidation_price:.2f}",
                    f"2R目标 {item.plan.target_2r:.2f}",
                    f"最大股数 {item.plan.maximum_shares}",
                )
            )
        )

    lines.append("准备中观察")
    if not value.observe:
        lines.append("无")
    for item in value.observe:
        details = (*item.missing_fields, *item.reasons)
        suffix = ",".join(details) if details else "等待条件"
        lines.append(f"{item.code} {item.name} 无交易资格 {suffix}")

    lines.append("影子研究")
    if not value.shadow:
        lines.append("无")
    for item in value.shadow:
        reasons = ",".join(item.reasons) if item.reasons else "RESEARCH_ONLY"
        lines.append(f"{item.code} {item.name} {item.source} 无交易资格 {reasons}")

    lines.append("拒绝统计")
    if not value.rejection_counts:
        lines.append("无")
    for reason, count in value.rejection_counts.items():
        lines.append(f"{reason}: {count}")
    return "\n".join(lines)
