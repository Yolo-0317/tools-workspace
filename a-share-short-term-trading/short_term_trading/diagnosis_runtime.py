"""Runtime composition for one session-aware stock diagnosis."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Callable, Protocol

from .contracts import ReleaseMode
from .daily_sync import DailyBar, DailyBarRepository, bar_is_complete, normalize_code
from .diagnosis import RiskProfile, TradePlanDraft, build_eod_trade_plan
from .evidence import EvidenceRepository, is_chip_snapshot_for_trade_date
from .intraday import IntradayDecision, IntradayRiskGate, verify_intraday_plan
from .market_regime import MarketStateProvider, MarketStateView, freeze_market_state
from .session import TradingCalendar, TradingSession, classify_trading_session
from .session_diagnosis import SessionAwareDiagnosis, diagnose_for_session


class RuntimeEvidenceRepository(EvidenceRepository, Protocol):
    def get_latest_valid_snapshot(self, code: str, kind: str): ...

    def get_valid_snapshots_since(self, code: str, kind: str, since: datetime): ...


class StockAiTradingCalendar:
    """Strict adapter around the shared SSE calendar cache."""

    def status(self, value: date) -> bool | None:
        from stock_ai.trading_calendar import trading_day_status

        return trading_day_status(value)

    def latest_on_or_before(self, value: date) -> date | None:
        from stock_ai.trading_calendar import latest_confirmed_a_share_trade_date

        return latest_confirmed_a_share_trade_date(value)

    def next_on_or_after(self, value: date) -> date | None:
        from stock_ai.trading_calendar import next_confirmed_a_share_trade_date

        return next_confirmed_a_share_trade_date(value)


@dataclass
class DiagnosisRuntime:
    calendar: TradingCalendar
    daily_repository: DailyBarRepository
    evidence_repository: RuntimeEvidenceRepository
    risk_profile: RiskProfile
    frozen_plan: TradePlanDraft | None = None
    risk_gate: IntradayRiskGate | None = None
    intraday_refresh: Callable[[str], None] | None = None
    chip_refresh: Callable[[str], None] | None = None
    market_state_provider: MarketStateProvider | None = None


def _market_payload(state: MarketStateView, *, is_holding: bool) -> dict[str, object]:
    if state.status == "ALLOW":
        impact = "继续验证个股与组合门禁，不代表直接可以买入"
    elif state.status == "LIMITED":
        impact = "限制新增仓位；已有持仓的退出纪律不变"
    else:
        impact = "禁止加仓；已有持仓的退出纪律不变" if is_holding else "禁止新增风险"
    return {
        "status": state.status,
        "trading_date": state.trading_date.isoformat() if state.trading_date else None,
        "as_of": state.as_of.isoformat(),
        "expires_at": state.expires_at.isoformat(),
        "indexes_above_ma20": state.indexes_above_ma20,
        "breadth_pct": state.breadth_pct,
        "amount_ratio": state.amount_ratio,
        "strong_sector_count": state.strong_sector_count,
        "reasons": list(state.reasons),
        "evidence_refs": list(state.evidence_refs),
        "emotion_label": state.emotion_label,
        "index_change_pct": state.index_change_pct,
        "source": state.source,
        "impact": impact,
    }


def _safe_plan(code: str, now: datetime, reason: str) -> TradePlanDraft:
    return TradePlanDraft(
        code=code,
        status="NO_TRADE",
        reason=reason,
        as_of=now.isoformat(),
        trigger_price=None,
        entry_ceiling=None,
        invalidation_price=None,
        first_reduce_price=None,
        pullback_low=None,
        pullback_high=None,
        maximum_shares=0,
        indicators={},
        evidence_refs={},
    )


def _missing_intraday_decision(code: str, now: datetime, reason: str) -> IntradayDecision:
    return IntradayDecision(
        code=code,
        status="NO_TRADE",
        reason=reason,
        as_of=now.isoformat(),
        maximum_shares=0,
        passed_gates=[],
        failed_gates=["plan", "portfolio"],
        evidence_refs={},
    )


def build_runtime_diagnosis(
    code: str,
    runtime: DiagnosisRuntime,
    *,
    now: datetime,
    release_mode: ReleaseMode,
    is_holding: bool = False,
) -> SessionAwareDiagnosis:
    """Classify the clock, select the data path, and return one safe conclusion."""

    normalized = normalize_code(code)
    context = classify_trading_session(now, runtime.calendar)
    if not context.calendar_confirmed:
        return diagnose_for_session(
            normalized,
            context,
            static_diagnose=lambda selected, _: _safe_plan(
                selected, context.now_utc, "交易日历未确认，未访问行情或交易数据源"
            ),
            release_mode=release_mode,
            is_holding=is_holding,
        )

    market_state: MarketStateView | None = None
    if runtime.market_state_provider is not None:
        market_context = context
        if context.session in {TradingSession.INTRADAY, TradingSession.MIDDAY_BREAK}:
            completed_market_date = runtime.calendar.latest_on_or_before(
                context.local_now.date() - timedelta(days=1)
            )
            market_context = replace(
                context, diagnosis_trade_date=completed_market_date
            )
        try:
            market_state = runtime.market_state_provider.get_state(market_context)
        except Exception:  # noqa: BLE001
            market_state = freeze_market_state(
                trading_date=context.diagnosis_trade_date,
                as_of=context.now_utc,
                reason="自动大盘状态获取失败",
            )

    cached_bars: list[DailyBar] | None = None
    if context.session not in {TradingSession.INTRADAY, TradingSession.MIDDAY_BREAK}:
        retrieved_bars = runtime.daily_repository.get_recent_bars(normalized, 120)
        cutoff = context.diagnosis_trade_date or context.local_now.date()
        cached_bars = [
            item
            for item in retrieved_bars
            if item.trade_date <= cutoff and bar_is_complete(item)
        ]
        latest_date = max((item.trade_date for item in cached_bars), default=None)
        if latest_date is not None and latest_date != context.diagnosis_trade_date:
            context = replace(context, diagnosis_trade_date=latest_date)

    def static_diagnose(selected: str, _context) -> TradePlanDraft:
        if market_state is not None and market_state.status == "FREEZE" and not is_holding:
            return _safe_plan(selected, context.now_utc, "市场状态为 FREEZE，禁止新增风险")
        bars = cached_bars
        if bars is None:
            bars = runtime.daily_repository.get_recent_bars(selected, 120)
        chip = runtime.evidence_repository.get_latest_valid_snapshot(selected, "chip")
        expected_trade_date = context.diagnosis_trade_date
        if (
            expected_trade_date is not None
            and not is_chip_snapshot_for_trade_date(chip, expected_trade_date)
            and runtime.chip_refresh is not None
        ):
            try:
                runtime.chip_refresh(selected)
            except Exception:  # noqa: BLE001
                pass
            chip = runtime.evidence_repository.get_latest_valid_snapshot(selected, "chip")
        profile = runtime.risk_profile
        if market_state is not None and market_state.status == "LIMITED" and not is_holding:
            profile = replace(profile, ticket_limit=min(profile.ticket_limit, 2000.0))
        return build_eod_trade_plan(
            selected,
            bars,
            chip,
            profile=profile,
            now=context.now_utc,
            expected_trade_date=expected_trade_date,
        )

    def intraday_diagnose(selected: str, _context) -> IntradayDecision:
        if runtime.frozen_plan is None or runtime.risk_gate is None:
            return _missing_intraday_decision(
                selected, context.now_utc, "缺少冻结收盘计划或组合风控门禁"
            )
        if context.session is TradingSession.INTRADAY and runtime.intraday_refresh is not None:
            runtime.intraday_refresh(selected)
        repository = runtime.evidence_repository
        risk_gate = runtime.risk_gate
        if market_state is not None:
            risk_gate = IntradayRiskGate(
                market_state.status,
                risk_gate.portfolio_approved,
                risk_gate.maximum_shares,
                risk_gate.reason,
            )
        return verify_intraday_plan(
            runtime.frozen_plan,
            quote=repository.get_latest_valid_snapshot(selected, "quote"),
            fund_flow=repository.get_latest_valid_snapshot(selected, "fund_flow"),
            sector=repository.get_latest_valid_snapshot(selected, "sector"),
            chip=repository.get_latest_valid_snapshot(selected, "chip"),
            order_books=repository.get_valid_snapshots_since(
                selected, "order_book", context.now_utc - timedelta(minutes=5)
            ),
            risk_gate=risk_gate,
            now=context.now_utc,
            is_holding=is_holding,
        )

    result = diagnose_for_session(
        normalized,
        context,
        static_diagnose=static_diagnose,
        intraday_diagnose=intraday_diagnose,
        release_mode=release_mode,
        is_holding=is_holding,
    )
    if market_state is not None:
        result = replace(result, market=_market_payload(market_state, is_holding=is_holding))
    return result
