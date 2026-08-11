from __future__ import annotations

from datetime import date, datetime, timezone

from short_term_trading.market_regime import (
    MarketStateView,
    apply_intraday_downgrade,
    freeze_market_state,
)


NOW = datetime(2026, 8, 11, 2, 0, tzinfo=timezone.utc)


def test_fresh_allow_remains_allow_when_intraday_breadth_is_not_weak() -> None:
    assert apply_intraday_downgrade("ALLOW", 52.0, 3, True) == "ALLOW"


def test_allow_downgrades_when_breadth_and_sector_strength_are_both_weak() -> None:
    assert apply_intraday_downgrade("ALLOW", 39.9, 1, True) == "LIMITED"


def test_stale_intraday_data_freezes_any_previous_status() -> None:
    assert apply_intraday_downgrade("ALLOW", 70.0, 8, False) == "FREEZE"


def test_intraday_state_never_upgrades_a_restricted_close_state() -> None:
    assert apply_intraday_downgrade("LIMITED", 80.0, 8, True) == "LIMITED"
    assert apply_intraday_downgrade("FREEZE", 80.0, 8, True) == "FREEZE"


def test_freeze_view_preserves_auditable_reason_without_fake_metrics() -> None:
    state = freeze_market_state(
        trading_date=date(2026, 8, 10),
        as_of=NOW,
        reason="三指数 MA20 数据缺失",
    )

    assert isinstance(state, MarketStateView)
    assert state.status == "FREEZE"
    assert state.reasons == ("三指数 MA20 数据缺失",)
    assert state.indexes_above_ma20 is None
    assert state.breadth_pct is None
    assert state.amount_ratio is None
    assert state.strong_sector_count is None
    assert state.expires_at == NOW
