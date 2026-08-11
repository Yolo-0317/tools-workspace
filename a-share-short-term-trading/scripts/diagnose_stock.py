#!/usr/bin/env python3
"""Automatically classify the market session and diagnose one A-share symbol."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "stock-ai"))

from short_term_trading.capture import capture_chip, capture_quote_and_fund
from short_term_trading.contracts import ReleaseMode
from short_term_trading.daily_sync import SqlAlchemyDailyBarRepository, normalize_code
from short_term_trading.diagnosis import RiskProfile, TradePlanDraft
from short_term_trading.diagnosis_runtime import (
    DiagnosisRuntime,
    StockAiTradingCalendar,
    build_runtime_diagnosis,
)
from short_term_trading.evidence import CaptureRecorder, SqlAlchemyEvidenceRepository
from short_term_trading.intraday import IntradayRiskGate
from short_term_trading.market_capture import build_default_market_state_provider
from short_term_trading.repositories import PlanningRepository, create_mysql_engine
from short_term_trading.session import TradingSession
from short_term_trading.session_diagnosis import SessionAwareDiagnosis, render_session_diagnosis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="自动识别交易时段并诊断一只 A 股")
    parser.add_argument("--code", required=True)
    parser.add_argument("--output", choices=("text", "json"), default="text")
    parser.add_argument("--plan-json", help="上一交易日冻结计划 JSON")
    parser.add_argument("--maximum-shares", type=int, default=0)
    parser.add_argument("--portfolio-approved", action="store_true")
    parser.add_argument("--is-holding", action="store_true")
    parser.add_argument("--release-mode", choices=("SHADOW", "LIVE"), default="SHADOW")
    parser.add_argument("--no-intraday-refresh", action="store_true")
    parser.add_argument("--no-chip-refresh", action="store_true")
    parser.add_argument("--at", help="仅用于复现的带时区 ISO 时间；不指定时使用当前时间")
    parser.add_argument("--risk-budget", type=float, default=500.0)
    parser.add_argument("--ticket-limit", type=float, default=4000.0)
    parser.add_argument("--remaining-exposure", type=float, default=4000.0)
    return parser


def _load_plan(path: str | None) -> TradePlanDraft | None:
    if path is None:
        return None
    with open(path, encoding="utf-8") as file:
        return TradePlanDraft(**json.load(file))


def default_runtime(args: argparse.Namespace) -> DiagnosisRuntime:
    try:
        from dotenv import load_dotenv

        load_dotenv(WORKSPACE_ROOT / "stock-ai" / ".env", override=False)
    except ImportError:
        pass
    mysql_url = os.getenv("MYSQL_URL")
    if not mysql_url:
        raise RuntimeError("MYSQL_URL 未配置")
    daily_repository = SqlAlchemyDailyBarRepository(mysql_url)
    evidence_repository = SqlAlchemyEvidenceRepository(mysql_url)
    recorder = CaptureRecorder(evidence_repository)
    refresh = None
    if not args.no_intraday_refresh:
        refresh = lambda code: capture_quote_and_fund(code, recorder)
    chip_refresh = None
    if not args.no_chip_refresh:
        chip_refresh = lambda code: capture_chip(code, recorder)
    return DiagnosisRuntime(
        calendar=StockAiTradingCalendar(),
        daily_repository=daily_repository,
        evidence_repository=evidence_repository,
        risk_profile=RiskProfile(args.risk_budget, args.ticket_limit, args.remaining_exposure),
        frozen_plan=_load_plan(args.plan_json),
        risk_gate=IntradayRiskGate(
            "FREEZE",
            args.portfolio_approved,
            args.maximum_shares,
            "命令参数未明确放行组合风险" if not args.portfolio_approved else "",
        ),
        intraday_refresh=refresh,
        chip_refresh=chip_refresh,
        market_state_provider=build_default_market_state_provider(mysql_url),
        plan_repository=PlanningRepository(create_mysql_engine(mysql_url)),
    )


def _unavailable(code: str, now: datetime, reason: str) -> SessionAwareDiagnosis:
    return SessionAwareDiagnosis(
        code=normalize_code(code),
        session=TradingSession.NON_TRADING_DAY,
        session_label="诊断运行环境不可用",
        as_of=now.astimezone(timezone.utc).isoformat(),
        diagnosis_trade_date=None,
        quote_as_of=None,
        data_label="数据源不可用",
        signal="NO_TRADE",
        computed_signal="NO_TRADE",
        actionable=False,
        reason=reason,
        next_action="恢复数据库配置后重新诊断",
        details={},
    )


def main(
    argv: list[str] | None = None,
    *,
    runtime_factory: Callable[[argparse.Namespace], DiagnosisRuntime] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    if args.at:
        try:
            now = datetime.fromisoformat(args.at)
        except ValueError:
            parser.error("--at 必须是合法 ISO 时间")
        if now.tzinfo is None or now.utcoffset() is None:
            parser.error("--at 必须包含时区")
    try:
        runtime = (runtime_factory or default_runtime)(args)
        result = build_runtime_diagnosis(
            args.code,
            runtime,
            now=now,
            release_mode=ReleaseMode(args.release_mode),
            is_holding=args.is_holding,
        )
    except (OSError, RuntimeError):
        result = _unavailable(args.code, now, "诊断数据源不可用，未生成交易许可")
    if args.output == "json":
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_session_diagnosis(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
