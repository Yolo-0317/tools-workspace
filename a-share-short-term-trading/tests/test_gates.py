from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from short_term_trading.gates import MarketInputs, PortfolioRiskInputs, evaluate_market, evaluate_portfolio_risk


def test_market_allow_then_intraday_downgrade() -> None:
    assert evaluate_market(MarketInputs(2, 55, 1.0, True)) == "ALLOW"
    assert evaluate_market(MarketInputs(2, 55, 1.0, True, intraday_breadth=35, strong_sector_count=1)) == "LIMITED"


def test_missing_market_data_freezes() -> None:
    assert evaluate_market(MarketInputs(3, 70, 1.1, False)) == "FREEZE"


def test_portfolio_risk_rejects_theme_overexposure() -> None:
    gate = evaluate_portfolio_risk(
        PortfolioRiskInputs(
            market_status="ALLOW",
            active_new_positions=0,
            current_exposure=10000,
            proposed_value=4000,
            same_theme_exposure=34000,
            proposed_theme_value=2000,
            maximum_shares_from_plan=300,
            entry_price=10,
        )
    )

    assert not gate.portfolio_approved
    assert "同主题" in gate.reason
