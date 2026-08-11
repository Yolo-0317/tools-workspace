#!/usr/bin/env python3
"""Manually run four-lane short-term selection and print an auditable report."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
import json
from io import StringIO
from pathlib import Path
import sys
from typing import Callable, Protocol


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
STOCK_AI_ROOT = WORKSPACE_ROOT / "stock-ai"
for path in (PROJECT_ROOT, STOCK_AI_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from short_term_trading.capture import capture_chip
from short_term_trading.daily_sync import DailyBar
from short_term_trading.diagnosis import RiskProfile
from short_term_trading.evidence import CaptureRecorder
from short_term_trading.market_capture import build_default_market_state_provider
from short_term_trading.repositories import EvidenceRepository, PlanningRepository
from short_term_trading.selection_service import (
    SelectionDependencies,
    SelectionReport,
    SelectionRequest,
    materialize_short_term_selection,
    render_selection_report,
)
from short_term_trading.session import TradingCalendar, TradingSession, classify_trading_session
from stock_ai.relative_strength import load_relative_strength_snapshot
from stock_ai.selection_validation import load_promoted_policy
from stock_ai.short_term_selection import SelectionPolicy, select_short_term_candidates


LANES = ("combined", "ma5", "five_factor", "bottom_breakout")
VALIDATION_ARTIFACT = STOCK_AI_ROOT / "config" / "short_term_selection_validation.json"


class CliInputError(RuntimeError):
    """Expected safe failure whose message may be printed to the user."""


def resolve_runtime_policy(
    engine: object,
    analysis_date: date,
    *,
    artifact_path: Path = VALIDATION_ARTIFACT,
) -> tuple[SelectionPolicy, dict[str, float] | None]:
    policy = load_promoted_policy(
        artifact_path,
        expected_data_end=analysis_date,
    )
    if not policy.strict:
        return policy, None
    snapshot = load_relative_strength_snapshot(engine, analysis_date)
    if snapshot.current_trade_date != analysis_date or not snapshot.is_usable:
        raise CliInputError(
            f"2.1 全市场相对强度覆盖率不足 95%（当前 {snapshot.coverage_ratio:.2%}），已停止选股"
        )
    return policy, dict(snapshot.percentiles)


class SelectionCliRuntime(Protocol):
    calendar: TradingCalendar

    def run_lanes(self, strategies: tuple[str, ...]) -> int: ...

    def latest_daily_trade_date(self) -> date | None: ...

    def execute(
        self, *, context: object, analysis_date: date, trading_date: date
    ) -> SelectionReport: ...


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="手动运行短线自动选股（不会自动下单）")
    parser.add_argument("--output", choices=("text", "json"), default="text")
    parser.add_argument("--at", help="带时区 ISO 时间，仅用于复现")
    parser.add_argument(
        "--skip-lanes",
        action="store_true",
        help="仅在人工重试/测试时复用已落库的四轨结果",
    )
    return parser


def _resolve_dates(now: datetime, calendar: TradingCalendar) -> tuple[object, date, date]:
    context = classify_trading_session(now, calendar)
    if not context.calendar_confirmed:
        raise CliInputError("交易日历无法确认，已停止选股")
    today = context.local_now.date()
    if context.session is TradingSession.NON_TRADING_DAY:
        analysis_date = calendar.latest_on_or_before(today)
        trading_date = calendar.next_on_or_after(today)
    elif context.session is TradingSession.POST_MARKET:
        analysis_date = today
        trading_date = calendar.next_on_or_after(today + timedelta(days=1))
    else:
        analysis_date = calendar.latest_on_or_before(today - timedelta(days=1))
        trading_date = today
    if analysis_date is None or trading_date is None:
        raise CliInputError("无法确定完整日线日期或下一交易日")
    return replace(
        context,
        diagnosis_trade_date=analysis_date,
        next_trade_date=trading_date,
    ), analysis_date, trading_date


def _bar(code: str, value: dict[str, object]) -> DailyBar:
    return DailyBar(
        ts_code=code,
        exch_code="SH" if code.startswith("6") else "SZ",
        trade_date=date.fromisoformat(str(value["trade_date"])[:10]),
        open=float(value["open"]),
        high=float(value["high"]),
        low=float(value["low"]),
        close=float(value["close"]),
        pre_close=None,
        change_amount=None,
        pct_chg=float(value.get("pct_chg") or 0),
        vol=int(value.get("vol") or 0),
        amount=float(value.get("amount") or 0),
    )


class DefaultRuntime:
    def __init__(self) -> None:
        from dotenv import load_dotenv
        from scripts.tools import portfolio_db
        from short_term_trading.diagnosis_runtime import StockAiTradingCalendar

        load_dotenv(STOCK_AI_ROOT / ".env", override=False)
        self.calendar = StockAiTradingCalendar()
        self._portfolio_db = portfolio_db
        self._engine = portfolio_db.get_engine()
        if self._engine is None:
            raise CliInputError("MySQL 配置不可用")
        self._evidence = EvidenceRepository(self._engine)
        self._planning = PlanningRepository(self._engine)

    def run_lanes(self, strategies: tuple[str, ...]) -> int:
        if strategies != LANES:
            raise CliInputError("短线选股必须运行完整四轨")
        from scripts.selection.run_parallel_selection import main as run_parallel

        return run_parallel()

    def latest_daily_trade_date(self) -> date | None:
        return self._portfolio_db.latest_stock_daily_trade_date(engine=self._engine)

    def execute(
        self, *, context: object, analysis_date: date, trading_date: date
    ) -> SelectionReport:
        from scripts.tools.portfolio_db import (
            load_account,
            load_holding_codes,
            load_industry_map,
            load_selection_daily_results,
            load_st_codes,
            load_stock_daily_bars,
            mysql_url,
        )
        from scripts.tools.selection_results import merge_selection_strategies_df

        policy, relative_strength_by_code = resolve_runtime_policy(
            self._engine,
            analysis_date,
        )

        for lane in LANES:
            lane_date, lane_rows = load_selection_daily_results(
                analysis_date, strategy=lane, engine=self._engine
            )
            if lane_date != analysis_date:
                raise CliInputError(f"{lane} 轨在分析日缺少结果，已停止部分评分")

        merged_date, frame, _ = merge_selection_strategies_df(
            trade_date=analysis_date,
            strategies=LANES,
        )
        if merged_date != analysis_date:
            raise CliInputError("四轨合并结果日期不一致")
        industries = load_industry_map(engine=self._engine)
        rows = frame.to_dict("records")
        bars_by_code: dict[str, list[dict[str, object]]] = {}
        daily_bars: dict[str, list[DailyBar]] = {}
        for row in rows:
            code = str(row.get("代码", "")).split(".")[0].zfill(6)
            row["所属行业"] = row.get("所属行业") or industries.get(code, "未知行业")
            raw_bars = load_stock_daily_bars(
                code, end_date=analysis_date, limit=120, engine=self._engine
            )
            bars_by_code[code] = raw_bars
            daily_bars[code] = [_bar(code, value) for value in raw_bars]

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            st_codes = load_st_codes(engine=self._engine)
        result = select_short_term_candidates(
            analysis_date=analysis_date,
            rows=rows,
            bars_by_code=bars_by_code,
            holding_codes=load_holding_codes(engine=self._engine),
            st_codes=st_codes,
            relative_strength_by_code=relative_strength_by_code,
            policy=policy,
        )
        account = load_account(engine=self._engine)
        approved = bool(
            account is not None
            and account.snapshot_date is not None
            and account.snapshot_date >= analysis_date
            and account.available_cash is not None
        )
        cash = float(account.available_cash) if approved and account.available_cash is not None else 4000.0
        risk_profile = RiskProfile(
            per_trade_loss_budget=min(500.0, cash * 0.01),
            ticket_limit=min(4000.0, cash),
            remaining_exposure=max(0.0, cash),
        )
        market_state = build_default_market_state_provider(mysql_url()).get_state(context)
        recorder = CaptureRecorder(self._evidence)
        dependencies = SelectionDependencies(
            evidence_repository=self._evidence,
            planning_repository=self._planning,
            load_daily_bars=lambda code, _: daily_bars.get(code, []),
            refresh_chip=lambda code, _: capture_chip(code, recorder),
        )
        return materialize_short_term_selection(
            result,
            dependencies,
            SelectionRequest(
                analysis_date=analysis_date,
                trading_date=trading_date,
                now=getattr(context, "now_utc"),
                market_state=market_state,
                risk_profile=risk_profile,
                portfolio_approved=approved,
                rule_version=policy.rule_version,
            ),
        )


def default_runtime(_: argparse.Namespace) -> SelectionCliRuntime:
    return DefaultRuntime()


def _report_dict(report: SelectionReport) -> dict[str, object]:
    payload = asdict(report)
    payload["analysis_date"] = report.analysis_date.isoformat()
    payload["trading_date"] = report.trading_date.isoformat()
    for item in payload["items"]:
        plan = item.get("plan")
        if plan is not None:
            item["plan"] = plan.model_dump(mode="json")
    return payload


def main(
    argv: list[str] | None = None,
    *,
    runtime_factory: Callable[[argparse.Namespace], SelectionCliRuntime] | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    now = datetime.now(timezone.utc)
    if args.at:
        try:
            now = datetime.fromisoformat(args.at)
        except ValueError:
            print("短线自动选股失败：--at 必须是合法 ISO 时间")
            return 2
        if now.tzinfo is None or now.utcoffset() is None:
            print("短线自动选股失败：--at 必须包含时区")
            return 2
    try:
        runtime = (runtime_factory or default_runtime)(args)
        if not args.skip_lanes and runtime.run_lanes(LANES) != 0:
            raise CliInputError("四轨选股执行失败")
        context, analysis_date, trading_date = _resolve_dates(now, runtime.calendar)
        latest = runtime.latest_daily_trade_date()
        if context.session is TradingSession.POST_MARKET and latest != analysis_date:
            raise CliInputError("当日日线尚未完整入库，未生成交易价位")
        if latest is None or latest < analysis_date:
            raise CliInputError("完整日线尚未入库，未生成交易价位")
        report = runtime.execute(
            context=context,
            analysis_date=analysis_date,
            trading_date=trading_date,
        )
    except CliInputError as exc:
        print(f"短线自动选股失败：{exc}")
        return 2
    except Exception:
        print("短线自动选股失败：数据或配置不可用，未生成交易价位")
        return 2

    if args.output == "json":
        print(json.dumps(_report_dict(report), ensure_ascii=False, indent=2))
    else:
        print(render_selection_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
