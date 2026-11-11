from __future__ import annotations

from pathlib import Path

from .models import RotationBucket, RotationRunResult, RotationState

_BUCKET_LABELS = {
    RotationBucket.STRONG: "当前最强",
    RotationBucket.STRENGTHENING: "正在增强",
    RotationBucket.PULLBACK: "回踩观察",
}


def _reason_text(values: tuple[str, ...]) -> str:
    return "、".join(values) if values else "无额外原因"


def render_rotation_report(
    result: RotationRunResult,
    previous: RotationRunResult | None,
) -> str:
    lines = [
        "# 强势板块轮动检测",
        "",
        "## 数据时间与完整性",
        "",
        f"- 交易日：{result.trade_date.isoformat()}",
        f"- 观测时间：{result.observed_at.isoformat()}",
        f"- 版本：{result.edition} / {result.policy_version}",
        f"- 数据提示：{_reason_text(result.warnings)}",
        "",
        "## 六方向摘要",
        "",
        "| 分组 | 方向 | 状态 | 核心得分 | 先看原因 |",
        "|---|---|---|---:|---|",
    ]
    for chain in result.chains:
        state = chain.state.value if chain.state else "未达状态门槛"
        reasons = _reason_text(chain.state_reasons + chain.score.reasons)
        lines.append(
            f"| {_BUCKET_LABELS[chain.bucket]} | {chain.chain_name} | {state} | "
            f"{chain.score.total} | {reasons} |"
        )
    if len(result.chains) < 6:
        lines.extend(("", f"本次仅有{len(result.chains)}个方向通过门槛，不使用弱板块补位。"))

    lines.extend(("", "## 状态变化", ""))
    previous_states = {value.chain_code: value.state for value in previous.chains} if previous else {}
    transitions = []
    for chain in result.chains:
        old = previous_states.get(chain.chain_code)
        if old != chain.state:
            old_text = old.value if old else "新进入"
            new_text = chain.state.value if chain.state else "未达门槛"
            transitions.append(f"- {chain.chain_name}：{old_text} -> {new_text}")
    lines.extend(transitions or ["- 本次没有可比较的状态变化。"])

    held = [value for value in result.candidates if value.held]
    lines.extend(("", "## 持仓交集", ""))
    lines.extend(
        [f"- {value.name}（{value.code}）：{value.role.value}" for value in held]
        or ["- 当前候选与持仓没有交集。"]
    )

    for chain in result.chains:
        observations = [value for value in result.candidates if value.chain_code == chain.chain_code][:10]
        lines.extend(("", f"## {chain.chain_name}：最多10只观察股", ""))
        lines.extend((
            "| 排名 | 代码 | 名称 | 角色 | 是否正式候选 | 原因 |",
            "|---:|---|---|---|---|---|",
        ))
        for candidate in observations:
            eligibility = "是" if candidate.formal_eligible else "否"
            reason = _reason_text(candidate.reasons + candidate.rejection_reasons)
            lines.append(
                f"| {candidate.pool_rank} | {candidate.code} | {candidate.name} | "
                f"{candidate.role.value} | {eligibility} | {reason} |"
            )
        if not observations:
            lines.append("| - | - | 暂无合格观察股 | - | 否 | 数据不足 |")

    lines.extend(("", "## 正式条件计划", ""))
    formal = [value for value in result.candidates if value.formal_eligible]
    for candidate in formal:
        lines.append(f"### {candidate.name}（{candidate.code}）")
        lines.append("")
        lines.append(f"- 角色：{candidate.role.value}")
        lines.append(f"- 依据：{_reason_text(candidate.reasons)}")
        if candidate.levels is None:
            lines.append("- 降级为观察：价格结构数据不足")
        else:
            lines.extend((
                f"- 观察价：{candidate.levels.watch_price}",
                f"- 触发价：{candidate.levels.trigger_price}",
                f"- 禁追价：{candidate.levels.no_chase_price}",
                f"- 失效位：{candidate.levels.invalidation_price}",
            ))
        lines.append("")
    if not formal:
        lines.append("暂无达到正式条件的候选。")

    blocked = [value for value in result.candidates if value.rejection_reasons]
    lines.extend(("", "## 禁止追高与降级观察", ""))
    lines.extend(
        [f"- {value.name}（{value.code}）：{_reason_text(value.rejection_reasons)}" for value in blocked]
        or ["- 本次没有触发禁止追高条件的观察股。"]
    )

    fading = [value for value in result.chains if value.state is RotationState.FADING]
    lines.extend(("", "## 退潮方向", ""))
    lines.extend(
        [f"- {value.chain_name}：{_reason_text(value.state_reasons)}" for value in fading]
        or ["- 本次没有进入退潮状态的核心方向。"]
    )
    lines.extend((
        "",
        "## 使用限制",
        "",
        "- 本报告用于人工复盘和条件观察，不构成收益承诺。",
        "- 所有价格均为条件价，达到禁追价后禁止追高。",
        "- 本模块为非自动交易工具，不创建订单、监控规则或自动下单。",
        f"- 阈值版本：{result.policy_version}",
        "",
    ))
    return "\n".join(lines)


def write_rotation_report(
    result: RotationRunResult,
    output_path: Path | None = None,
    previous: RotationRunResult | None = None,
) -> Path:
    target = output_path or Path("output") / (
        f"sector_rotation_{result.observed_at.strftime('%Y%m%d_%H%M')}.md"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_rotation_report(result, previous), encoding="utf-8")
    return target.resolve()
