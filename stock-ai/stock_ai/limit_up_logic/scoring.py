from __future__ import annotations

from .models import (
    LimitUpContext,
    LimitUpFeatures,
    LimitUpIdentity,
    LimitUpPaths,
    LimitUpScoreBreakdown,
)


def classify_limit_up_identity(
    features: LimitUpFeatures,
    context: LimitUpContext,
) -> LimitUpIdentity:
    if not features.data_sufficient:
        return "DATA_INSUFFICIENT"
    if context.material_risk:
        return "RISK_VETOED"
    if features.post_limit_support_broken or features.post_limit_volume_breakdown:
        return "RELAY_FAILED"
    recent_board = (
        features.days_since_last_limit_up is not None
        and features.days_since_last_limit_up <= 10
    )
    holding_price = (
        features.distance_from_last_limit_close is not None
        and features.distance_from_last_limit_close >= -0.03
    )
    no_large_upper_shadow = (
        features.upper_shadow_ratio is None or features.upper_shadow_ratio <= 0.45
    )
    if (
        recent_board
        and features.post_limit_holding_days >= 2
        and features.post_limit_retention
        and holding_price
        and no_large_upper_shadow
    ):
        return "SECOND_WAVE_CANDIDATE"
    if recent_board and not features.post_limit_support_broken:
        return "POST_LIMIT_HOLDING"
    if (
        not features.recent_limit_up_indices
        and features.amount_ratio5 is not None
        and features.amount_ratio5 >= 1.2
        and features.close_location is not None
        and features.close_location >= 0.70
        and features.distance_from_prior_high20 is not None
        and features.distance_from_prior_high20 >= -0.02
    ):
        return "FIRST_BOARD_SETUP"
    return "NORMAL_TREND"


def score_limit_up_setup(
    features: LimitUpFeatures,
    context: LimitUpContext,
) -> LimitUpScoreBreakdown:
    gene = {"STRONG": 30, "MEDIUM": 20, "WEAK": 5, "UNKNOWN": 0}[features.limit_up_gene]

    price_volume = 0
    if features.ma5 is not None and features.ma10 is not None and features.ma5 > features.ma10:
        price_volume += 5
    if (
        features.ma20 is not None
        and features.ma10 is not None
        and features.ma5 is not None
        and features.ma5 > features.ma10 > features.ma20
    ):
        price_volume += 5
    if features.post_limit_retention:
        price_volume += 8
    if features.post_limit_shrink:
        price_volume += 4
    if features.close_location is not None and features.close_location >= 0.65:
        price_volume += 4
    if (
        features.distance_from_last_limit_close is not None
        and -0.03 <= features.distance_from_last_limit_close <= 0.15
    ):
        price_volume += 4
    price_volume = min(30, price_volume)

    theme_sector = 0
    verified_themes = set(context.concepts).intersection(context.active_themes)
    if verified_themes:
        theme_sector += 10
        if len(verified_themes) >= 2:
            theme_sector += 3
    if context.sector_change_pct is not None and context.sector_change_pct >= 1.5:
        theme_sector += 4
    if context.sector_limit_up_count is not None and context.sector_limit_up_count >= 3:
        theme_sector += 4
    if context.sector_leader_strength == "strong":
        theme_sector += 7
    elif context.sector_leader_strength == "neutral":
        theme_sector += 3
    theme_sector = min(25, theme_sector)

    fund_flow = 0
    if context.main_net_inflow_ratio is not None:
        if context.main_net_inflow_ratio >= 5:
            fund_flow += 8
        elif context.main_net_inflow_ratio > 0:
            fund_flow += 5
        elif context.main_net_inflow_ratio <= -5:
            fund_flow -= 5
    if context.consecutive_inflow_days is not None:
        if context.consecutive_inflow_days >= 5:
            fund_flow += 7
        elif context.consecutive_inflow_days >= 2:
            fund_flow += 4
    fund_flow = max(0, min(15, fund_flow))

    return LimitUpScoreBreakdown(gene, price_volume, theme_sector, fund_flow)


def allocate_limit_up_paths(
    identity: LimitUpIdentity,
    score: LimitUpScoreBreakdown,
    context: LimitUpContext,
) -> LimitUpPaths:
    if identity == "DATA_INSUFFICIENT":
        return LimitUpPaths(0, 0, 100)
    if identity == "RISK_VETOED":
        return LimitUpPaths(0, 15, 85)
    if identity == "RELAY_FAILED":
        return LimitUpPaths(5, 20, 75)
    if identity == "SECOND_WAVE_CANDIDATE":
        acceleration = 35 + (5 if score.total >= 65 else 0) + (5 if score.total >= 80 else 0)
        continuation = 40 if acceleration <= 40 else 35
    elif identity == "POST_LIMIT_HOLDING":
        acceleration, continuation = (25, 50)
    elif identity == "FIRST_BOARD_SETUP":
        acceleration, continuation = (20, 55)
    else:
        acceleration, continuation = (10, 60)

    missing_intraday = (
        context.auction_strength == "unknown" or context.seal_quality == "unknown"
    )
    acceleration = min(acceleration, 45 if missing_intraday else 55)
    failure = 100 - acceleration - continuation
    if failure < 15:
        continuation -= 15 - failure
        failure = 15
    return LimitUpPaths(int(acceleration), int(continuation), int(failure))

