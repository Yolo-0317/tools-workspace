#!/usr/bin/env python3
"""个股 / 组合分析统一的决策上下文注入（操盘策略 + 持仓执行卡）。"""

from __future__ import annotations

from scripts.tools.holdings_context import load_full_decision_context

# 追加到所有 DeepSeek 个股分析 prompt 末尾
ANALYSIS_OUTPUT_RULES = """
## 分析输出纪律（必须遵守）
1. 所有操作建议必须严格符合上文「决策上下文」：仓位、止损、禁追高、禁满仓新开仓、单股≤30%、单笔风险≤2%、P0～P4 计划。
2. 若技术信号与红线冲突，必须**明确拒绝**并说明原因。
3. 新开仓 / 加仓须给出：**试探股数（100 整数倍）**、**止损价**、**预估账户风险占比**、**是否符合盈亏比≥2:1**。
4. 全中文，决策支持非投资建议；禁止绝对买卖指令。
"""


def get_decision_context_for_prompt(
    *,
    holdings_path=None,
    rules_path=None,
) -> str:
    """加载完整决策上下文文本块。"""
    _, combined = load_full_decision_context(holdings_path, rules_path)
    return combined.strip() or "（未加载决策上下文）"


def inject_decision_context(
    prompt: str,
    *,
    holdings_path=None,
    rules_path=None,
    include_output_rules: bool = True,
) -> str:
    """在任意分析 prompt 后注入决策上下文与输出纪律。"""
    ctx = get_decision_context_for_prompt(
        holdings_path=holdings_path,
        rules_path=rules_path,
    )
    parts = [
        prompt.rstrip(),
        "",
        "## 必须遵循的决策上下文（优先级：执行卡 P0～P4 > 通用策略）",
        ctx,
    ]
    if include_output_rules:
        parts.append(ANALYSIS_OUTPUT_RULES.strip())
    return "\n".join(parts)
