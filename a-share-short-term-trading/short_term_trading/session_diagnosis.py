"""Session-aware routing and user-visible diagnosis policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

from .contracts import ReleaseMode
from .diagnosis import TradePlanDraft
from .intraday import IntradayDecision
from .session import TradingSession, TradingSessionContext


StaticDiagnosis = Callable[[str, TradingSessionContext], TradePlanDraft]
IntradayDiagnosis = Callable[[str, TradingSessionContext], IntradayDecision]


@dataclass(frozen=True)
class SessionAwareDiagnosis:
    code: str
    session: TradingSession
    session_label: str
    as_of: str
    diagnosis_trade_date: str | None
    quote_as_of: str | None
    data_label: str
    signal: str
    computed_signal: str
    actionable: bool
    reason: str
    next_action: str
    details: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        values = asdict(self)
        values["session"] = self.session.value
        return values


_SESSION_LABELS = {
    TradingSession.PRE_MARKET: "交易日盘前",
    TradingSession.INTRADAY: "交易日盘中",
    TradingSession.MIDDAY_BREAK: "交易日盘中（午间休市）",
    TradingSession.POST_MARKET: "交易日盘后",
    TradingSession.NON_TRADING_DAY: "非交易日",
}


def _data_label(context: TradingSessionContext, quote_as_of: str | None) -> str:
    trade_date = (
        context.diagnosis_trade_date.isoformat()
        if context.diagnosis_trade_date is not None
        else "日期不可确认"
    )
    if context.session in {TradingSession.PRE_MARKET, TradingSession.NON_TRADING_DAY}:
        return f"最近交易日收盘（{trade_date}）"
    if context.session is TradingSession.POST_MARKET:
        if (
            context.diagnosis_trade_date is not None
            and context.diagnosis_trade_date != context.local_now.date()
        ):
            return f"最近完整收盘（{trade_date}）"
        return f"当日收盘（{trade_date}）"
    if context.session is TradingSession.MIDDAY_BREAK:
        return f"上午最新行情（{quote_as_of or '时间不可确认'}）"
    return f"盘中行情（{quote_as_of or '时间不可确认'}）"


def _next_action(context: TradingSessionContext) -> str:
    if context.session is TradingSession.PRE_MARKET:
        return "09:30 开盘后重新采集实时证据并验证门禁"
    if context.session is TradingSession.MIDDAY_BREAK:
        return "13:00 恢复交易后重新采集实时证据"
    if context.session is TradingSession.POST_MARKET:
        return "下一交易日开盘后验证收盘计划"
    if context.session is TradingSession.NON_TRADING_DAY:
        if context.next_trade_date is None:
            return "交易日历恢复后再进行盘中验证"
        return f"{context.next_trade_date.isoformat()} 开盘后重新验证"
    return "证据超过五分钟或行情变化后重新验证"


def _reason(context: TradingSessionContext, decision_reason: str) -> str:
    return f"{context.reason}；{decision_reason}"


def _missing_intraday(context: TradingSessionContext, code: str) -> SessionAwareDiagnosis:
    return SessionAwareDiagnosis(
        code=code,
        session=context.session,
        session_label=_SESSION_LABELS[context.session],
        as_of=context.now_utc.isoformat(),
        diagnosis_trade_date=(
            context.diagnosis_trade_date.isoformat()
            if context.diagnosis_trade_date is not None
            else None
        ),
        quote_as_of=None,
        data_label=_data_label(context, None),
        signal="NO_TRADE",
        computed_signal="NO_TRADE",
        actionable=False,
        reason=_reason(context, "盘中诊断数据未就绪"),
        next_action=_next_action(context),
        details={},
    )


def diagnose_for_session(
    code: str,
    context: TradingSessionContext,
    *,
    static_diagnose: StaticDiagnosis,
    intraday_diagnose: IntradayDiagnosis | None = None,
    is_holding: bool = False,
    release_mode: ReleaseMode = ReleaseMode.SHADOW,
) -> SessionAwareDiagnosis:
    use_intraday = context.session in {
        TradingSession.INTRADAY,
        TradingSession.MIDDAY_BREAK,
    }
    if use_intraday:
        if intraday_diagnose is None:
            return _missing_intraday(context, code)
        decision = intraday_diagnose(code, context)
        computed_signal = decision.status
        signal = computed_signal
        actionable = False
        reason = _reason(context, decision.reason)
        if context.session is TradingSession.MIDDAY_BREAK:
            if computed_signal == "BUY_ALLOWED":
                signal = "WAIT_ENTRY"
                reason = _reason(context, "上午条件曾命中，但午间休市不可放行买入")
        elif computed_signal == "BUY_ALLOWED":
            if release_mode is ReleaseMode.LIVE:
                actionable = True
            else:
                signal = "NO_TRADE"
                reason = _reason(context, "影子规则命中，仅用于验证")
        return SessionAwareDiagnosis(
            code=decision.code,
            session=context.session,
            session_label=_SESSION_LABELS[context.session],
            as_of=context.now_utc.isoformat(),
            diagnosis_trade_date=(
                context.diagnosis_trade_date.isoformat()
                if context.diagnosis_trade_date is not None
                else None
            ),
            quote_as_of=decision.as_of,
            data_label=_data_label(context, decision.as_of),
            signal=signal,
            computed_signal=computed_signal,
            actionable=actionable,
            reason=reason,
            next_action=_next_action(context),
            details=decision.to_dict(),
        )

    plan = static_diagnose(code, context)
    computed_signal = plan.status
    signal = computed_signal
    if context.session is TradingSession.NON_TRADING_DAY and not is_holding:
        signal = "NO_TRADE"
    elif computed_signal == "BUY_ALLOWED":
        signal = "WAIT_ENTRY"
    return SessionAwareDiagnosis(
        code=plan.code,
        session=context.session,
        session_label=_SESSION_LABELS[context.session],
        as_of=context.now_utc.isoformat(),
        diagnosis_trade_date=(
            context.diagnosis_trade_date.isoformat()
            if context.diagnosis_trade_date is not None
            else None
        ),
        quote_as_of=None,
        data_label=_data_label(context, None),
        signal=signal,
        computed_signal=computed_signal,
        actionable=False,
        reason=_reason(context, plan.reason),
        next_action=_next_action(context),
        details=plan.to_dict(),
    )


def render_session_diagnosis(result: SessionAwareDiagnosis) -> str:
    return "\n".join(
        [
            f"当前状态：{result.session_label}",
            f"数据口径：{result.data_label}",
            f"主结论：{result.signal}（{'可执行' if result.actionable else '不可执行'}）",
            f"原因：{result.reason}",
            f"下一步：{result.next_action}",
        ]
    )
