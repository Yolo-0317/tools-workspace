from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine, text

from short_term_trading.market_capture import (
    AutomaticMarketStateProvider,
    build_closed_market_view,
    build_intraday_market_view,
    live_market_metrics,
    load_close_breadth_amount,
)
from short_term_trading.session import TradingSession


NOW = datetime(2026, 8, 11, 1, 55, tzinfo=timezone.utc)
TRADE_DATE = date(2026, 8, 10)


def rows(last_close: float) -> list[list[str]]:
    values = [10.0] * 19 + [last_close]
    return [
        [f"2026-07-{index + 1:02d}", "10", str(close), "11", "9", "1", "1", "", str((close - 10.0) * 10), "0", "1"]
        for index, close in enumerate(values)
    ]


def test_closed_market_uses_three_index_ma20_breadth_and_amount_ratio() -> None:
    state = build_closed_market_view(
        trading_date=TRADE_DATE,
        as_of=NOW,
        index_rows={
            "000001": rows(11.0),
            "399001": rows(11.0),
            "000688": rows(9.0),
        },
        breadth_pct=55.0,
        amount_ratio=1.0,
        evidence_refs=("fixture:close",),
    )

    assert state.status == "ALLOW"
    assert state.indexes_above_ma20 == 2
    assert state.breadth_pct == 55.0
    assert state.amount_ratio == 1.0
    assert state.index_change_pct == 3.3333


def test_incomplete_index_history_freezes_without_fake_market_metrics() -> None:
    state = build_closed_market_view(
        trading_date=TRADE_DATE,
        as_of=NOW,
        index_rows={"000001": rows(11.0)[:19], "399001": rows(11.0), "000688": rows(9.0)},
        breadth_pct=55.0,
        amount_ratio=1.0,
    )

    assert state.status == "FREEZE"
    assert state.indexes_above_ma20 is None
    assert "不足 20 根" in state.reasons[0]


def test_intraday_market_can_only_downgrade_the_close_state() -> None:
    baseline = build_closed_market_view(
        trading_date=TRADE_DATE,
        as_of=NOW,
        index_rows={"000001": rows(11.0), "399001": rows(11.0), "000688": rows(9.0)},
        breadth_pct=55.0,
        amount_ratio=1.0,
    )

    state = build_intraday_market_view(
        baseline,
        as_of=NOW,
        breadth_pct=35.0,
        strong_sector_count=1,
        data_fresh=True,
        evidence_refs=("fixture:live",),
    )

    assert state.status == "LIMITED"
    assert state.breadth_pct == 35.0
    assert state.strong_sector_count == 1
    assert state.amount_ratio == 1.0


def test_stale_intraday_market_freezes_and_explains_the_failure() -> None:
    baseline = build_closed_market_view(
        trading_date=TRADE_DATE,
        as_of=NOW,
        index_rows={"000001": rows(11.0), "399001": rows(11.0), "000688": rows(9.0)},
        breadth_pct=55.0,
        amount_ratio=1.0,
    )

    state = build_intraday_market_view(
        baseline,
        as_of=NOW,
        breadth_pct=70.0,
        strong_sector_count=8,
        data_fresh=False,
    )

    assert state.status == "FREEZE"
    assert "过期" in state.reasons[0]


def test_provider_captures_a_missing_close_state_then_downgrades_intraday() -> None:
    captured: list[date] = []
    refreshed: list[str] = []
    saved: list[str] = []

    def capture_close(trading_date: date, as_of: datetime):
        captured.append(trading_date)
        return build_closed_market_view(
            trading_date=trading_date,
            as_of=as_of,
            index_rows={"000001": rows(11.0), "399001": rows(11.0), "000688": rows(9.0)},
            breadth_pct=55.0,
            amount_ratio=1.0,
        )

    def capture_live(baseline, as_of):
        refreshed.append(baseline.status)
        return build_intraday_market_view(
            baseline,
            as_of=as_of,
            breadth_pct=35.0,
            strong_sector_count=1,
            data_fresh=True,
        )

    provider = AutomaticMarketStateProvider(
        load_close_state=lambda trading_date: None,
        capture_close_state=capture_close,
        capture_intraday_state=capture_live,
        save_state=lambda state: saved.append(state.status),
    )
    context = SimpleNamespace(
        diagnosis_trade_date=TRADE_DATE,
        now_utc=NOW,
        session=TradingSession.INTRADAY,
    )

    state = provider.get_state(context)

    assert captured == [TRADE_DATE]
    assert refreshed == ["ALLOW"]
    assert saved == ["ALLOW", "LIMITED"]
    assert state.status == "LIMITED"


def test_provider_uses_a_saved_close_state_without_intraday_refresh_after_close() -> None:
    baseline = build_closed_market_view(
        trading_date=TRADE_DATE,
        as_of=NOW,
        index_rows={"000001": rows(11.0), "399001": rows(11.0), "000688": rows(9.0)},
        breadth_pct=55.0,
        amount_ratio=1.0,
    )
    provider = AutomaticMarketStateProvider(
        load_close_state=lambda trading_date: baseline,
        capture_close_state=lambda trading_date, as_of: (_ for _ in ()).throw(AssertionError()),
        capture_intraday_state=lambda state, as_of: (_ for _ in ()).throw(AssertionError()),
        save_state=lambda state: (_ for _ in ()).throw(AssertionError()),
    )
    context = SimpleNamespace(
        diagnosis_trade_date=TRADE_DATE,
        now_utc=NOW,
        session=TradingSession.POST_MARKET,
    )

    assert provider.get_state(context) is baseline


def test_close_breadth_and_amount_ratio_use_completed_mysql_rows() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE stock_daily (trade_date DATE, pct_chg REAL, amount REAL)"))
        connection.execute(
            text("INSERT INTO stock_daily VALUES (:d, :p, :a)"),
            [
                {"d": "2026-08-07", "p": 1.0, "a": 100.0},
                {"d": "2026-08-07", "p": -1.0, "a": 100.0},
                {"d": "2026-08-10", "p": 2.0, "a": 100.0},
                {"d": "2026-08-10", "p": -1.0, "a": 100.0},
                {"d": "2026-08-10", "p": 0.0, "a": 100.0},
            ],
        )

    breadth, amount_ratio = load_close_breadth_amount(engine, TRADE_DATE)

    assert breadth == 33.3333
    assert amount_ratio == 1.5


def test_live_market_metrics_require_all_indices_and_count_distinct_strong_sectors() -> None:
    indices = {
        "000001": SimpleNamespace(change_pct=-0.2),
        "399001": SimpleNamespace(change_pct=0.1),
        "000688": SimpleNamespace(change_pct=-1.1),
    }
    breadth = {"total": {"up": 1176, "flat": 167, "down": 3940}}
    sectors = [
        {"sector": "白银", "sector_chg": 5.75},
        {"sector": "白银", "sector_chg": 5.75},
        {"sector": "机床工具", "sector_chg": 1.86},
        {"sector": "银行", "sector_chg": 0.2},
    ]

    metrics = live_market_metrics(indices, breadth, sectors)

    assert metrics == (-0.4, 22.2601, 2, True)
