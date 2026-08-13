from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from .features import extract_limit_up_features, normalize_bars
from .models import LimitUpBar, LimitUpContext, LimitUpResult
from .scoring import (
    allocate_limit_up_paths,
    classify_limit_up_identity,
    score_limit_up_setup,
)


def _missing_fields(context: LimitUpContext, base: tuple[str, ...]) -> tuple[str, ...]:
    missing = list(base)
    if not context.active_themes:
        missing.append("active_themes")
    if context.sector_change_pct is None:
        missing.append("sector_change_pct")
    if context.sector_limit_up_count is None:
        missing.append("sector_limit_up_count")
    if context.sector_leader_strength == "unknown":
        missing.append("sector_leader_strength")
    if context.main_net_inflow_ratio is None:
        missing.append("main_net_inflow_ratio")
    if context.consecutive_inflow_days is None:
        missing.append("consecutive_inflow_days")
    if context.auction_strength == "unknown":
        missing.append("auction_strength")
    if context.seal_quality == "unknown":
        missing.append("seal_quality")
    if context.reopen_count is None:
        missing.append("reopen_count")
    return tuple(dict.fromkeys(missing))


def analyze_limit_up_logic(
    code: str,
    name: str,
    bars: Sequence[LimitUpBar] | Sequence[Mapping[str, Any]],
    context: LimitUpContext | None = None,
    *,
    is_st: bool = False,
) -> LimitUpResult:
    context = context or LimitUpContext()
    normalized = normalize_bars(bars)
    features = extract_limit_up_features(code, normalized, is_st=is_st)
    identity = classify_limit_up_identity(features, context)
    score = score_limit_up_setup(features, context)
    paths = allocate_limit_up_paths(identity, score, context)

    drivers: list[str] = []
    if features.recent_limit_up_count:
        drivers.append(f"近20日出现{features.recent_limit_up_count}次涨停")
    if features.post_limit_retention:
        drivers.append("首板后连续承接，未破首板低点")
    if features.post_limit_shrink:
        drivers.append("首板后缩量整理，抛压阶段性收敛")
    verified_themes = tuple(set(context.concepts).intersection(context.active_themes))
    if verified_themes:
        drivers.append("活跃题材共振：" + "、".join(sorted(verified_themes)))
    if context.main_net_inflow_ratio is not None and context.main_net_inflow_ratio > 0:
        drivers.append(f"主力净流入占比{context.main_net_inflow_ratio:.1f}%")
    if not drivers:
        drivers.append("未形成可验证的封板驱动组合")

    prerequisites = [
        "至少一个已验证题材形成板块共振并保持领涨股强度",
        "个股放量突破关键前高后回踩不破",
        "竞价、真实成交与封单质量不出现冲突",
    ]
    suppressors: list[str] = []
    if context.material_risk:
        suppressors.extend(context.material_risk_reasons or ("存在重大风险门禁",))
    if features.post_limit_support_broken:
        suppressors.append("首板后关键支撑已经失守")
    if features.post_limit_volume_breakdown:
        suppressors.append("首板后出现放量破位")
    if features.upper_shadow_ratio is not None and features.upper_shadow_ratio > 0.35:
        suppressors.append("上影线偏长，冲高抛压明显")
    if not context.active_themes:
        suppressors.append("概念标签尚未得到实时板块共振验证")
    if context.auction_strength == "unknown" or context.seal_quality == "unknown":
        suppressors.append("收盘阶段缺少竞价和封单验证")

    cutoff = context.observed_at or features.latest_trade_date or datetime.now().astimezone()
    return LimitUpResult(
        code="".join(ch for ch in str(code) if ch.isdigit())[:6],
        name=name,
        identity=identity,
        gene=features.limit_up_gene,
        score=score,
        paths=paths,
        drivers=tuple(drivers),
        prerequisites=tuple(prerequisites),
        suppressors=tuple(suppressors),
        missing_fields=_missing_fields(context, features.missing_fields),
        data_cutoff=cutoff,
        new_risk_forbidden=context.material_risk,
        recent_limit_up_count=features.recent_limit_up_count,
        post_limit_support_broken=features.post_limit_support_broken,
        post_limit_shrink=features.post_limit_shrink,
        consolidation_high=(
            max(item.high for item in normalized[-9:-1])
            if len(normalized) >= 9
            else None
        ),
        distance_to_consolidation_high=(
            normalized[-1].close / max(item.high for item in normalized[-9:-1]) - 1
            if len(normalized) >= 9
            and max(item.high for item in normalized[-9:-1]) > 0
            else None
        ),
        last_limit_up_low=features.last_limit_up_low,
        latest_pct_chg=features.latest_pct_chg,
        days_since_last_limit_up=features.days_since_last_limit_up,
        return5=features.return5,
        distance_from_last_limit_close=features.distance_from_last_limit_close,
    )
