"""Deterministic market-regime and portfolio-risk gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from short_term_trading.intraday import IntradayRiskGate


MarketStatus = Literal["ALLOW", "LIMITED", "FREEZE"]


@dataclass(frozen=True)
class MarketInputs:
    indexes_above_ma20: int
    breadth: float
    amount_ratio: float
    data_fresh: bool
    intraday_breadth: float | None = None
    strong_sector_count: int | None = None


def evaluate_market(inputs: MarketInputs) -> MarketStatus:
    if not inputs.data_fresh:
        return "FREEZE"
    if inputs.indexes_above_ma20 <= 1 and inputs.breadth < 40:
        return "FREEZE"
    if inputs.amount_ratio < 0.75 and inputs.breadth < 45:
        return "FREEZE"
    status: MarketStatus = "ALLOW" if (
        inputs.indexes_above_ma20 >= 2 and inputs.breadth >= 50 and inputs.amount_ratio >= 0.90
    ) else "LIMITED"
    if status == "ALLOW" and inputs.intraday_breadth is not None and inputs.strong_sector_count is not None:
        if inputs.intraday_breadth < 40 and inputs.strong_sector_count < 2:
            return "LIMITED"
    return status


@dataclass(frozen=True)
class PortfolioRiskInputs:
    market_status: MarketStatus
    active_new_positions: int
    current_exposure: float
    proposed_value: float
    same_theme_exposure: float
    proposed_theme_value: float
    maximum_shares_from_plan: int
    entry_price: float
    total_exposure_limit: float = 40000.0
    same_theme_limit: float = 35000.0
    normal_new_position_limit: int = 2


def evaluate_portfolio_risk(inputs: PortfolioRiskInputs) -> IntradayRiskGate:
    if inputs.market_status == "FREEZE":
        return IntradayRiskGate("FREEZE", False, 0, "市场风险冻结")
    allowed_new_positions = 1 if inputs.market_status == "LIMITED" else inputs.normal_new_position_limit
    if inputs.active_new_positions >= allowed_new_positions:
        return IntradayRiskGate(inputs.market_status, False, 0, "新开仓名额已用完")
    if inputs.current_exposure + inputs.proposed_value > inputs.total_exposure_limit:
        return IntradayRiskGate(inputs.market_status, False, 0, "总暴露超限")
    if inputs.same_theme_exposure + inputs.proposed_theme_value > inputs.same_theme_limit:
        return IntradayRiskGate(inputs.market_status, False, 0, "同主题暴露超限")
    maximum_by_exposure = int(max(0, inputs.total_exposure_limit - inputs.current_exposure) // inputs.entry_price)
    maximum_shares = min(inputs.maximum_shares_from_plan, maximum_by_exposure)
    if maximum_shares <= 0:
        return IntradayRiskGate(inputs.market_status, False, 0, "剩余总暴露不足")
    return IntradayRiskGate(inputs.market_status, True, maximum_shares)
