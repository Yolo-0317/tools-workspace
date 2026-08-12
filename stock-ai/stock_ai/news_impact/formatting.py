from __future__ import annotations

from .models import NewsImpactResult


def _paths(prefix: str, paths) -> str:
    return f"{prefix}：强{paths.strong}% / 中{paths.neutral}% / 弱{paths.weak}%"


def _delta(value: int) -> str:
    return f"{value:+d}"


def format_stock_impact_card(result: NewsImpactResult) -> str:
    scopes = {impact.event.scope for impact in result.impacts}
    effective = "24小时" if "overseas" in scopes else ("3天" if "policy" in scopes else ("7天" if "a_share" in scopes else "无有效事件"))
    lines = [f"【消息面影响】{result.score:+g}，{result.direction}；有效期：{effective}"]
    shown = result.impacts[:3]
    relevance_labels = {"high": "高度", "medium": "中等", "low": "低度", "none": "无"}
    for impact in shown:
        lines.append(
            f"- {impact.event.title} → {','.join(impact.mapped_sectors) or result.stock.industry}"
            f" → {result.stock.name}{relevance_labels.get(impact.relevance, impact.relevance)}相关；来源：{impact.event.source_name}"
        )
    hidden = len(result.impacts) - len(shown)
    if hidden > 0:
        lines.append(f"- 另有{hidden}条相关消息已合并")
    if "overseas_company" in result.missing_scopes:
        lines.append("- 海外公司新闻覆盖不足，本次不做海外消息加分")
    p = result.probability
    lines.extend([
        _paths("基础概率", p.base),
        f"消息修正：强{_delta(p.delta.strong)} / 中{_delta(p.delta.neutral)} / 弱{_delta(p.delta.weak)}",
        _paths("最终概率", p.final),
    ])
    if result.veto.new_risk_forbidden:
        lines.append("重大利空门禁：禁止新增风险；已有持仓仍可保护性减仓或退出")
    if any(impact.event.confirmation_state in {"premarket", "intraday"} for impact in result.impacts):
        lines.append("失效条件：相关海外股票收盘明显回落，或A股对应板块竞价、开盘不跟")
    elif result.impacts:
        lines.append("失效条件：事件被撤回、后续披露反转，或A股对应板块不共振")
    else:
        lines.append("失效条件：暂无可计分事件；新事件需重新核验")
    if result.data_cutoff:
        lines.append(f"数据截止：{result.data_cutoff.isoformat(timespec='minutes')}")
    return "\n".join(lines)


def format_portfolio_impact_table(results: dict[str, NewsImpactResult]) -> str:
    lines = ["| 股票 | 消息分 | 方向 | 最相关事件 | 概率变化 |", "|---|---:|---|---|---|"]
    for result in results.values():
        title = result.impacts[0].event.title if result.impacts else "无高相关事件"
        delta = result.probability.delta
        lines.append(f"| {result.stock.name} | {result.score:+g} | {result.direction} | {title} | 强{delta.strong:+d} / 中{delta.neutral:+d} / 弱{delta.weak:+d} |")
    return "\n".join(lines)
