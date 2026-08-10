from datetime import date, datetime, timezone

import pytest

from short_term_trading.contracts import ReleaseMode
from short_term_trading.diagnosis import TradePlanDraft
from short_term_trading.intraday import IntradayDecision
from short_term_trading.session import TradingSession, TradingSessionContext
from short_term_trading.session_diagnosis import (
    diagnose_for_session,
    render_session_diagnosis,
)


NOW = datetime(2026, 8, 10, 2, 0, tzinfo=timezone.utc)


def context_for(
    session: TradingSession,
    *,
    confirmed: bool = True,
) -> TradingSessionContext:
    local_hour = {
        TradingSession.PRE_MARKET: 9,
        TradingSession.INTRADAY: 10,
        TradingSession.MIDDAY_BREAK: 12,
        TradingSession.POST_MARKET: 16,
        TradingSession.NON_TRADING_DAY: 10,
    }[session]
    local = datetime(2026, 8, 10, local_hour, tzinfo=timezone.utc)
    return TradingSessionContext(
        session=session,
        now_utc=NOW,
        local_now=local,
        calendar_confirmed=confirmed,
        diagnosis_trade_date=date(2026, 8, 7) if session is TradingSession.NON_TRADING_DAY else date(2026, 8, 10),
        next_trade_date=date(2026, 8, 11),
        reason=(
            "SSE 交易日历无法确认，已安全降级为不可交易诊断"
            if not confirmed
            else "fixture session"
        ),
    )


def static_plan(status: str = "WAIT_ENTRY") -> TradePlanDraft:
    return TradePlanDraft(
        code="600000",
        status=status,
        reason="收盘计划结论",
        as_of=NOW.isoformat(),
        trigger_price=10.0,
        entry_ceiling=10.3,
        invalidation_price=9.8,
        first_reduce_price=10.4,
        pullback_low=9.9,
        pullback_high=10.1,
        maximum_shares=300,
        indicators={"ma5": 9.95},
        evidence_refs={"chip": "fixture:chip"},
    )


def intraday_decision(status: str = "BUY_ALLOWED") -> IntradayDecision:
    return IntradayDecision(
        code="600000",
        status=status,
        reason="盘中门禁结论",
        as_of=NOW.isoformat(),
        maximum_shares=200 if status == "BUY_ALLOWED" else 0,
        passed_gates=["price"],
        failed_gates=[],
        evidence_refs={"quote": "fixture:quote"},
    )


def test_pre_market_returns_a_non_actionable_wait_entry_plan() -> None:
    calls: list[str] = []

    def static_handler(code: str, context: TradingSessionContext) -> TradePlanDraft:
        calls.append("static")
        return static_plan()

    def intraday_handler(code: str, context: TradingSessionContext) -> IntradayDecision:
        calls.append("intraday")
        return intraday_decision()

    result = diagnose_for_session(
        "600000",
        context_for(TradingSession.PRE_MARKET),
        static_diagnose=static_handler,
        intraday_diagnose=intraday_handler,
    )

    assert calls == ["static"]
    assert result.signal == "WAIT_ENTRY"
    assert result.actionable is False
    assert "盘前" in result.session_label


def test_live_active_intraday_can_return_actionable_buy_allowed() -> None:
    result = diagnose_for_session(
        "600000",
        context_for(TradingSession.INTRADAY),
        static_diagnose=lambda code, context: static_plan(),
        intraday_diagnose=lambda code, context: intraday_decision(),
        release_mode=ReleaseMode.LIVE,
    )

    assert result.signal == "BUY_ALLOWED"
    assert result.computed_signal == "BUY_ALLOWED"
    assert result.actionable is True
    assert result.quote_as_of == NOW.isoformat()


def test_shadow_buy_has_one_no_trade_main_signal() -> None:
    result = diagnose_for_session(
        "600000",
        context_for(TradingSession.INTRADAY),
        static_diagnose=lambda code, context: static_plan(),
        intraday_diagnose=lambda code, context: intraday_decision(),
        release_mode=ReleaseMode.SHADOW,
    )

    assert result.signal == "NO_TRADE"
    assert result.computed_signal == "BUY_ALLOWED"
    assert result.actionable is False
    assert "影子规则命中" in result.reason


def test_midday_break_downgrades_a_computed_buy_to_wait_entry() -> None:
    result = diagnose_for_session(
        "600000",
        context_for(TradingSession.MIDDAY_BREAK),
        static_diagnose=lambda code, context: static_plan(),
        intraday_diagnose=lambda code, context: intraday_decision(),
        release_mode=ReleaseMode.LIVE,
    )

    assert result.signal == "WAIT_ENTRY"
    assert result.computed_signal == "BUY_ALLOWED"
    assert result.actionable is False
    assert "13:00" in result.next_action


def test_post_market_suppresses_an_invalid_static_buy_signal() -> None:
    result = diagnose_for_session(
        "600000",
        context_for(TradingSession.POST_MARKET),
        static_diagnose=lambda code, context: static_plan("BUY_ALLOWED"),
        intraday_diagnose=None,
        release_mode=ReleaseMode.LIVE,
    )

    assert result.signal == "WAIT_ENTRY"
    assert result.computed_signal == "BUY_ALLOWED"
    assert result.actionable is False
    assert "收盘" in result.data_label


def test_non_trading_day_forces_new_entry_to_no_trade() -> None:
    result = diagnose_for_session(
        "600000",
        context_for(TradingSession.NON_TRADING_DAY),
        static_diagnose=lambda code, context: static_plan(),
        intraday_diagnose=None,
    )

    assert result.signal == "NO_TRADE"
    assert result.computed_signal == "WAIT_ENTRY"
    assert result.actionable is False
    assert result.data_label == "最近交易日收盘（2026-08-07）"


def test_unknown_calendar_reason_is_preserved_and_never_calls_intraday() -> None:
    calls: list[str] = []

    def intraday_handler(code: str, context: TradingSessionContext) -> IntradayDecision:
        calls.append("intraday")
        return intraday_decision()

    result = diagnose_for_session(
        "600000",
        context_for(TradingSession.NON_TRADING_DAY, confirmed=False),
        static_diagnose=lambda code, context: static_plan(),
        intraday_diagnose=intraday_handler,
    )

    assert calls == []
    assert result.signal == "NO_TRADE"
    assert "无法确认" in result.reason


def test_missing_intraday_handler_returns_a_safe_conclusion() -> None:
    result = diagnose_for_session(
        "600000",
        context_for(TradingSession.INTRADAY),
        static_diagnose=lambda code, context: static_plan(),
        intraday_diagnose=None,
    )

    assert result.signal == "NO_TRADE"
    assert result.computed_signal == "NO_TRADE"
    assert result.actionable is False
    assert "盘中诊断数据未就绪" in result.reason


def test_non_trading_renderer_uses_close_wording_and_one_main_conclusion() -> None:
    result = diagnose_for_session(
        "600000",
        context_for(TradingSession.NON_TRADING_DAY),
        static_diagnose=lambda code, context: static_plan(),
        intraday_diagnose=None,
    )

    rendered = render_session_diagnosis(result)

    assert "非交易日" in rendered
    assert "最近交易日收盘" in rendered
    assert "现价" not in rendered
    assert rendered.count("主结论：NO_TRADE") == 1


@pytest.mark.parametrize(
    "session",
    [
        TradingSession.PRE_MARKET,
        TradingSession.MIDDAY_BREAK,
        TradingSession.POST_MARKET,
        TradingSession.NON_TRADING_DAY,
    ],
)
def test_every_closed_session_is_non_actionable(session: TradingSession) -> None:
    result = diagnose_for_session(
        "600000",
        context_for(session),
        static_diagnose=lambda code, context: static_plan("BUY_ALLOWED"),
        intraday_diagnose=lambda code, context: intraday_decision(),
        release_mode=ReleaseMode.LIVE,
    )

    assert result.signal != "BUY_ALLOWED"
    assert result.actionable is False
