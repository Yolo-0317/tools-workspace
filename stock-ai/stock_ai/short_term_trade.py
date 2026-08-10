"""收盘短线候选池：未经盘中验证的日线信号不得生成买入指令。"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _number(row: pd.Series, key: str) -> float:
    return float(pd.to_numeric(row.get(key, 0), errors="coerce") or 0)


def build_trade_candidates(rows: pd.DataFrame, *, holding_codes: set[str] | None = None, limit: int = 5) -> pd.DataFrame:
    """筛出最多 ``limit`` 只突破观察候选，不输出买入指令。"""
    holding_codes = holding_codes or set()
    candidates: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        code = str(row.get("代码", "")).split(".")[0].zfill(6)
        change = _number(row, "涨幅%")
        amount = _number(row, "成交额(万)")
        score = _number(row, "总分")
        labels = str(row.get("策略标签", ""))
        sources = str(row.get("策略来源", ""))
        if code in holding_codes or change < -2 or change > 7 or amount < 10_000:
            continue
        momentum = 10 if 0 <= change <= 5 else 4
        source_bonus = 8 if "," in sources else 0
        label_bonus = min(12, labels.count("+") * 4 + (4 if labels else 0))
        trade_score = round(score * 0.65 + momentum + source_bonus + label_bonus, 1)
        if "空中加油" in labels or "MA5" in sources:
            candidate_type = "强趋势回踩"
        elif "大底突破" in labels:
            candidate_type = "突破启动"
        else:
            candidate_type = "题材分歧转强待验证"
        if candidate_type != "突破启动":
            continue
        data = row.to_dict()
        data.update(
            {
                "代码": code,
                "策略标签": f"短线候选·{candidate_type}",
                "建议动作": "模拟跟踪，盘中五项确认后才可小仓",
                "交易候选分": trade_score,
                "候选类型": candidate_type,
                "盘中确认": False,
                "盘中确认项": "题材、板块、量价资金、筹码、盘口五项同时确认",
                "交易资格": "待人工盘中确认；禁止自动买入",
                "试错仓建议": "实投预算 2%–4%；单笔计划最大亏损 500 元",
                "失效规则": "跌破回踩低点或筹码支撑、资金转弱、板块退潮即放弃",
                "最大持有期": "1–5 个交易日；无新增催化不超过 10 日",
                "风险过滤": "已排除持仓、强趋势回踩与题材日线信号、单日跌幅<-2%、涨幅>7%、成交额<1亿元",
            }
        )
        candidates.append(data)
    return pd.DataFrame(candidates).sort_values("交易候选分", ascending=False).head(limit).reset_index(drop=True) if candidates else pd.DataFrame()
