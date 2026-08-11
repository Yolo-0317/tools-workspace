"""DataFrame compatibility adapter for completed-bar short-term selection."""

from __future__ import annotations

from datetime import date
from typing import Mapping, Sequence

import pandas as pd

from .short_term_selection import SelectionBar, select_short_term_candidates


_TYPE_LABELS = {
    "BREAKOUT": "突破启动",
    "PULLBACK": "强趋势回踩",
}


def build_trade_candidates(
    rows: pd.DataFrame,
    *,
    analysis_date: date,
    bars_by_code: Mapping[str, Sequence[Mapping[str, object] | SelectionBar]],
    holding_codes: set[str] | None = None,
    st_codes: set[str] | None = None,
    limit: int = 5,
) -> pd.DataFrame:
    """Return a chat/report-compatible frame backed by real completed bars."""
    if rows.empty:
        return pd.DataFrame()
    records = rows.to_dict("records")
    result = select_short_term_candidates(
        analysis_date=analysis_date,
        rows=records,
        bars_by_code=bars_by_code,
        holding_codes=holding_codes or set(),
        st_codes=st_codes or set(),
        limit=limit,
    )
    originals = {
        str(row.get("代码", "")).split(".")[0].zfill(6): row
        for row in records
    }
    output: list[dict[str, object]] = []
    for candidate in result.candidates:
        data = dict(originals.get(candidate.code, {}))
        candidate_label = _TYPE_LABELS[candidate.candidate_type]
        data.update(
            {
                "代码": candidate.code,
                "策略标签": f"短线候选·{candidate_label}",
                "建议动作": "模拟跟踪，盘中五项确认后才可小仓",
                "交易候选分": candidate.setup_score,
                "候选类型": candidate_label,
                "盘中确认": False,
                "盘中确认项": "题材、板块、量价资金、筹码、盘口五项同时确认",
                "交易资格": "待盘中验证与组合风控；禁止自动买入",
                "试错仓建议": "由冻结计划与组合风控计算，不猜测账户资金",
                "失效规则": "跌破计划失效价、资金转弱或板块退潮即放弃",
                "最大持有期": "1–5 个交易日；无新增催化不超过 10 日",
                "风险过滤": "仅沪深主板；已过滤持仓、ST、停牌、上市不足60日、流动性不足和涨幅>7%",
                "入选理由": "；".join(candidate.reasons),
                "形态指标": candidate.metrics,
            }
        )
        output.append(data)
    return pd.DataFrame(output).reset_index(drop=True)
