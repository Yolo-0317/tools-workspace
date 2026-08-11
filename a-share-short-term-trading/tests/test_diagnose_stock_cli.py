from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import importlib.util
from pathlib import Path

from short_term_trading.contracts import ReleaseMode
from short_term_trading.daily_sync import DailyBar
from short_term_trading.diagnosis import RiskProfile, TradePlanDraft
from short_term_trading.diagnosis_runtime import DiagnosisRuntime, build_runtime_diagnosis
from short_term_trading.evidence import EvidenceSnapshot
from short_term_trading.intraday import IntradayRiskGate
from short_term_trading.market_regime import MarketStateView
from short_term_trading.session import TradingSession


SHANGHAI_POST_MARKET = datetime.fromisoformat("2026-08-10T16:00:00+08:00")
SHANGHAI_INTRADAY = datetime.fromisoformat("2026-08-10T10:00:00+08:00")
SHANGHAI_MIDDAY = datetime.fromisoformat("2026-08-10T12:00:00+08:00")


class FakeCalendar:
    def __init__(self, status: bool | None = True) -> None:
        self._status = status

    def status(self, value: date) -> bool | None:
        return self._status

    def latest_on_or_before(self, value: date) -> date | None:
        return date(2026, 8, 7)

    def next_on_or_after(self, value: date) -> date | None:
        return date(2026, 8, 11)


class FakeDailyRepository:
    def __init__(self, bars: list[DailyBar]) -> None:
        self.bars = bars
        self.calls = 0

    def get_recent_bars(self, code: str, limit: int) -> list[DailyBar]:
        self.calls += 1
        return self.bars[-limit:]


class FakeEvidenceRepository:
    def __init__(self, latest: dict[str, EvidenceSnapshot] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.latest = latest or {}

    def get_latest_valid_snapshot(self, code: str, kind: str):
        self.calls.append((code, kind))
        return self.latest.get(kind)

    def get_valid_snapshots_since(self, code: str, kind: str, since: datetime):
        self.calls.append((code, kind))
        return []


def bar(trade_date: date) -> DailyBar:
    return DailyBar(
        ts_code="600000",
        exch_code="SH",
        trade_date=trade_date,
        open=10.0,
        high=10.3,
        low=9.8,
        close=10.1,
        pre_close=10.0,
        change_amount=0.1,
        pct_chg=1.0,
        vol=1000,
        amount=10000.0,
    )


def plan() -> TradePlanDraft:
    return TradePlanDraft(
        code="600000",
        status="WAIT_ENTRY",
        reason="fixture plan",
        as_of=SHANGHAI_INTRADAY.astimezone(timezone.utc).isoformat(),
        trigger_price=10.0,
        entry_ceiling=10.3,
        invalidation_price=9.8,
        first_reduce_price=10.4,
        pullback_low=9.9,
        pullback_high=10.1,
        maximum_shares=300,
        indicators={},
        evidence_refs={},
    )


def chip_snapshot(trade_date: date) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        snapshot_id=f"chip-{trade_date.isoformat()}",
        code="600000",
        kind="chip",
        as_of=datetime.combine(trade_date, datetime.min.time(), tzinfo=timezone.utc),
        source="eastmoney-opencli",
        parser_version="chip-cyq-v1",
        data={
            "source_trade_date": trade_date.isoformat(),
            "cost_90_low": 9.0,
            "cost_90_high": 10.0,
            "average_cost": 9.5,
            "profit_ratio": 70.0,
            "concentration": 5.0,
            "input_bar_count": 210,
            "method": "eastmoney-cyq-v1",
        },
        raw_evidence_ref=f"fixture:chip:{trade_date.isoformat()}",
    )


def thirty_bars_ending_on(end: date) -> list[DailyBar]:
    return [bar(end - timedelta(days=offset)) for offset in reversed(range(30))]


def runtime(
    *,
    now_bars: list[DailyBar] | None = None,
    calendar_status: bool | None = True,
    refresh=None,
    chip_refresh=None,
    frozen_plan: TradePlanDraft | None = None,
    evidence_repository: FakeEvidenceRepository | None = None,
) -> DiagnosisRuntime:
    return DiagnosisRuntime(
        calendar=FakeCalendar(calendar_status),
        daily_repository=FakeDailyRepository(now_bars or []),
        evidence_repository=evidence_repository or FakeEvidenceRepository(),
        risk_profile=RiskProfile(),
        frozen_plan=frozen_plan,
        risk_gate=IntradayRiskGate("FREEZE", False, 0),
        intraday_refresh=refresh,
        chip_refresh=chip_refresh,
    )


def test_unknown_calendar_returns_safe_result_without_touching_data_sources() -> None:
    refresh_calls: list[str] = []
    subject = runtime(calendar_status=None, refresh=refresh_calls.append)

    result = build_runtime_diagnosis(
        "600000", subject, now=SHANGHAI_INTRADAY, release_mode=ReleaseMode.LIVE
    )

    assert result.session is TradingSession.NON_TRADING_DAY
    assert result.signal == "NO_TRADE"
    assert "无法确认" in result.reason
    assert subject.daily_repository.calls == 0
    assert subject.evidence_repository.calls == []
    assert refresh_calls == []


def test_active_intraday_refreshes_once_before_reading_evidence() -> None:
    refresh_calls: list[str] = []
    subject = runtime(refresh=refresh_calls.append, frozen_plan=plan())

    result = build_runtime_diagnosis(
        "600000", subject, now=SHANGHAI_INTRADAY, release_mode=ReleaseMode.SHADOW
    )

    assert refresh_calls == ["600000"]
    assert result.session is TradingSession.INTRADAY
    assert result.signal == "NO_TRADE"
    assert ("600000", "quote") in subject.evidence_repository.calls


def test_midday_break_uses_persisted_evidence_without_refresh() -> None:
    refresh_calls: list[str] = []
    subject = runtime(refresh=refresh_calls.append, frozen_plan=plan())

    result = build_runtime_diagnosis(
        "600000", subject, now=SHANGHAI_MIDDAY, release_mode=ReleaseMode.LIVE
    )

    assert result.session is TradingSession.MIDDAY_BREAK
    assert refresh_calls == []


def test_intraday_and_midday_never_refresh_the_close_chip_snapshot() -> None:
    chip_refresh_calls: list[str] = []
    for now in (SHANGHAI_INTRADAY, SHANGHAI_MIDDAY):
        subject = runtime(
            chip_refresh=chip_refresh_calls.append,
            frozen_plan=plan(),
        )
        build_runtime_diagnosis(
            "600000", subject, now=now, release_mode=ReleaseMode.LIVE
        )

    assert chip_refresh_calls == []


def test_missing_frozen_plan_never_starts_external_refresh() -> None:
    refresh_calls: list[str] = []
    subject = runtime(refresh=refresh_calls.append, frozen_plan=None)

    result = build_runtime_diagnosis(
        "600000", subject, now=SHANGHAI_INTRADAY, release_mode=ReleaseMode.LIVE
    )

    assert result.signal == "NO_TRADE"
    assert "缺少冻结收盘计划" in result.reason
    assert refresh_calls == []
    assert subject.evidence_repository.calls == []


def test_runtime_attaches_the_automatic_market_state_to_the_diagnosis() -> None:
    calls: list[TradingSession] = []

    class Provider:
        def get_state(self, context):
            calls.append(context.session)
            return MarketStateView(
                status="LIMITED",
                trading_date=date(2026, 8, 10),
                as_of=SHANGHAI_INTRADAY.astimezone(timezone.utc),
                expires_at=(SHANGHAI_INTRADAY + timedelta(minutes=15)).astimezone(timezone.utc),
                indexes_above_ma20=1,
                breadth_pct=43.0,
                amount_ratio=0.86,
                strong_sector_count=1,
                reasons=("市场广度偏弱",),
                evidence_refs=("fixture:market",),
            )

    subject = DiagnosisRuntime(
        calendar=FakeCalendar(True),
        daily_repository=FakeDailyRepository([]),
        evidence_repository=FakeEvidenceRepository(),
        risk_profile=RiskProfile(),
        frozen_plan=None,
        risk_gate=IntradayRiskGate("ALLOW", True, 200),
        market_state_provider=Provider(),
    )

    result = build_runtime_diagnosis(
        "600000", subject, now=SHANGHAI_INTRADAY, release_mode=ReleaseMode.SHADOW
    )

    assert calls == [TradingSession.INTRADAY]
    assert result.market is not None
    assert result.market["status"] == "LIMITED"
    assert result.market["breadth_pct"] == 43.0


def test_post_market_falls_back_to_latest_complete_bar_date() -> None:
    subject = runtime(now_bars=[bar(date(2026, 8, 7))])

    result = build_runtime_diagnosis(
        "600000", subject, now=SHANGHAI_POST_MARKET, release_mode=ReleaseMode.SHADOW
    )

    assert result.session is TradingSession.POST_MARKET
    assert result.diagnosis_trade_date == "2026-08-07"
    assert result.data_label == "最近完整收盘（2026-08-07）"
    assert result.signal != "BUY_ALLOWED"


def test_post_market_ignores_an_incomplete_today_bar() -> None:
    incomplete_today = bar(date(2026, 8, 10))
    incomplete_today = DailyBar(
        **{
            **incomplete_today.__dict__,
            "high": 9.0,
        }
    )
    subject = runtime(now_bars=[bar(date(2026, 8, 7)), incomplete_today])

    result = build_runtime_diagnosis(
        "600000", subject, now=SHANGHAI_POST_MARKET, release_mode=ReleaseMode.SHADOW
    )

    assert result.diagnosis_trade_date == "2026-08-07"
    assert result.data_label == "最近完整收盘（2026-08-07）"


def test_post_market_refreshes_a_missing_chip_once_and_rereads_it() -> None:
    repository = FakeEvidenceRepository()
    refresh_calls: list[str] = []

    def refresh(code: str) -> None:
        refresh_calls.append(code)
        repository.latest["chip"] = chip_snapshot(date(2026, 8, 10))

    subject = runtime(
        now_bars=thirty_bars_ending_on(date(2026, 8, 10)),
        chip_refresh=refresh,
        evidence_repository=repository,
    )

    result = build_runtime_diagnosis(
        "600000", subject, now=SHANGHAI_POST_MARKET, release_mode=ReleaseMode.SHADOW
    )

    assert refresh_calls == ["600000"]
    assert repository.calls.count(("600000", "chip")) == 2
    assert "缺少最近收盘筹码快照" not in result.reason


def test_post_market_reuses_a_current_chip_without_refresh() -> None:
    repository = FakeEvidenceRepository(
        {"chip": chip_snapshot(date(2026, 8, 10))}
    )
    refresh_calls: list[str] = []
    subject = runtime(
        now_bars=thirty_bars_ending_on(date(2026, 8, 10)),
        chip_refresh=refresh_calls.append,
        evidence_repository=repository,
    )

    build_runtime_diagnosis(
        "600000", subject, now=SHANGHAI_POST_MARKET, release_mode=ReleaseMode.SHADOW
    )

    assert refresh_calls == []
    assert repository.calls.count(("600000", "chip")) == 1


def test_failed_chip_refresh_stays_a_safe_no_trade() -> None:
    subject = runtime(
        now_bars=thirty_bars_ending_on(date(2026, 8, 10)),
        chip_refresh=lambda code: (_ for _ in ()).throw(RuntimeError("detached")),
    )

    result = build_runtime_diagnosis(
        "600000", subject, now=SHANGHAI_POST_MARKET, release_mode=ReleaseMode.LIVE
    )

    assert result.signal == "NO_TRADE"
    assert "筹码" in result.reason


def test_cli_auto_detects_session_and_emits_json(capsys) -> None:
    script = Path(__file__).parents[1] / "scripts" / "diagnose_stock.py"
    spec = importlib.util.spec_from_file_location("diagnose_stock", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    subject = runtime(calendar_status=False)

    exit_code = module.main(
        ["--code", "600000", "--output", "json", "--at", "2026-08-09T10:00:00+08:00"],
        runtime_factory=lambda args: subject,
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"session": "NON_TRADING_DAY"' in output
    assert '"signal": "NO_TRADE"' in output


def test_cli_has_no_manual_session_override() -> None:
    script = Path(__file__).parents[1] / "scripts" / "diagnose_stock.py"
    spec = importlib.util.spec_from_file_location("diagnose_stock_invalid", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    option_strings = {
        option
        for action in module.build_parser()._actions
        for option in action.option_strings
    }
    assert "--session" not in option_strings
    assert "--market-status" not in option_strings
    assert "--no-chip-refresh" in option_strings


def test_cli_masks_runtime_configuration_errors(capsys) -> None:
    script = Path(__file__).parents[1] / "scripts" / "diagnose_stock.py"
    spec = importlib.util.spec_from_file_location("diagnose_stock_masked", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    exit_code = module.main(
        ["--code", "600000", "--output", "json", "--at", "2026-08-09T10:00:00+08:00"],
        runtime_factory=lambda args: (_ for _ in ()).throw(
            RuntimeError("mysql://root:secret@example.invalid/stock_data")
        ),
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"signal": "NO_TRADE"' in output
    assert "secret" not in output
