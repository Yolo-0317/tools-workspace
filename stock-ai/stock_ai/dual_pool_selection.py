"""Deterministic merger for technical candidates and mapped news events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Mapping, Sequence

from .news_impact import NewsEvent, ProbabilityPaths, StockContext, analyze_stock_news_impact
from .news_impact.events import FRESHNESS, deduplicate_events, filter_fresh_events
from .news_impact.mappings import infer_event_themes, iter_event_mapped_stocks


@dataclass(frozen=True)
class DualPoolResult:
    technical_rows: tuple[dict[str, object], ...]
    event_watch_rows: tuple[dict[str, object], ...]


def _code6(value: object) -> str:
    text = str(value or "").split(".")[0]
    return text.zfill(6) if text.isdigit() else text


def _number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _concepts(row: Mapping[str, object]) -> tuple[str, ...]:
    raw = row.get("所属概念", row.get("概念", row.get("概念板块", "")))
    if isinstance(raw, (tuple, list, set)):
        return tuple(str(value).strip() for value in raw if str(value).strip())
    return tuple(part.strip() for part in re.split(r"[,，、;；|]", str(raw or "")) if part.strip())


def _event_expiry(event: NewsEvent) -> datetime:
    return event.valid_until or event.published_at + FRESHNESS[event.scope]


def _themes(events: Sequence[NewsEvent]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            theme
            for event in events
            for theme, _rule in infer_event_themes(event)
        )
    )


def _impact_fields(result, *, coverage_status: str) -> dict[str, object]:
    impacts = result.impacts
    events = tuple(impact.event for impact in impacts)
    themes = _themes(events)
    expiry = min((_event_expiry(event) for event in events), default=None)
    scopes = {event.scope for event in events}
    invalidation = (
        "海外相关标的收盘转弱，或A股映射板块竞价与开盘不跟随"
        if "overseas" in scopes
        else "事件被官方修正、撤回，或映射板块量价不跟随"
    )
    return {
        "消息覆盖状态": coverage_status,
        "消息影响分": result.score,
        "消息方向": result.direction,
        "消息主题": ",".join(themes),
        "消息事件数": len(impacts),
        "消息摘要": "；".join(dict.fromkeys(event.title for event in events)),
        "消息传导": "；".join(dict.fromkeys(impact.transmission_type for impact in impacts)),
        "消息来源": "；".join(dict.fromkeys(event.source_name for event in events)),
        "消息截止时间": expiry.isoformat() if expiry is not None else "",
        "消息失效条件": invalidation if impacts else "",
        "消息否决原因": "；".join(result.veto.reasons),
    }


def _technical_sort_key(row: Mapping[str, object]) -> tuple[float, float, float, float, str]:
    return (
        -_number(row.get("总分")),
        -_number(row.get("技术原始分")),
        -_number(row.get("标签数")),
        -_number(row.get("成交额(万)")),
        _code6(row.get("代码")),
    )


def merge_dual_pool_rows(
    technical_rows: Sequence[Mapping[str, object]],
    events: Sequence[NewsEvent],
    *,
    now: datetime,
    coverage_status: str = "完整",
) -> DualPoolResult:
    fresh_events = tuple(deduplicate_events(filter_fresh_events(list(events), now=now)))
    technical_codes = {_code6(row.get("代码")) for row in technical_rows}
    enriched: list[dict[str, object]] = []

    for original in technical_rows:
        row = dict(original)
        technical_score = _number(row.get("总分"))
        stock = StockContext(
            code=_code6(row.get("代码")),
            name=str(row.get("名称", row.get("股票名称", row.get("代码", ""))) or ""),
            industry=str(row.get("所属行业", "") or ""),
            concepts=_concepts(row),
        )
        impact = analyze_stock_news_impact(
            stock,
            list(fresh_events),
            ProbabilityPaths(35, 45, 20),
            now=now,
            existing_holding=False,
        )
        adjustment = max(-6.0, min(6.0, impact.score * 0.5))
        row.update(_impact_fields(impact, coverage_status=coverage_status))
        row["技术原始分"] = technical_score
        row["双池总分"] = round(technical_score + adjustment, 3)
        row["总分"] = row["双池总分"]
        if impact.veto.new_risk_forbidden:
            row["候选池来源"] = "vetoed"
            row["建议动作"] = "禁止新交易"
        elif impact.impacts:
            row["候选池来源"] = "both"
            source = str(row.get("策略来源", "") or "")
            if "消息共振" not in source:
                row["策略来源"] = "+".join(part for part in (source, "消息共振") if part)
        else:
            row["候选池来源"] = "technical"
        enriched.append(row)

    watch_events: dict[str, list[NewsEvent]] = {}
    watch_meta: dict[str, object] = {}
    for event in fresh_events:
        for mapped in iter_event_mapped_stocks(event):
            if mapped.code in technical_codes:
                continue
            watch_events.setdefault(mapped.code, []).append(event)
            watch_meta.setdefault(mapped.code, mapped)

    watches: list[dict[str, object]] = []
    for code, mapped_events in watch_events.items():
        mapped = watch_meta[code]
        impact = analyze_stock_news_impact(
            StockContext(code, mapped.name, mapped.sectors[0] if mapped.sectors else "", mapped.sectors),
            mapped_events,
            ProbabilityPaths(35, 45, 20),
            now=now,
            existing_holding=False,
        )
        fields = _impact_fields(impact, coverage_status=coverage_status)
        watches.append(
            {
                "代码": code,
                "名称": mapped.name,
                "所属行业": mapped.sectors[0] if mapped.sectors else "",
                "策略标签": "重大消息事件池",
                "策略来源": "消息事件池",
                "建议动作": "消息观察，等待技术确认",
                "交易资格": "无技术信号，不进入可执行Top5",
                "候选池来源": "event_watch",
                "技术原始分": 0.0,
                "双池总分": 0.0,
                "总分": 0.0,
                **fields,
            }
        )

    return DualPoolResult(
        tuple(sorted(enriched, key=_technical_sort_key)),
        tuple(sorted(watches, key=lambda row: (-abs(_number(row.get("消息影响分"))), str(row["代码"])))),
    )
