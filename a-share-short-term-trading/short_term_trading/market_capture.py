"""Pure market-state composition plus runtime data adapters."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Callable
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .gates import MarketInputs, evaluate_market
from .market_regime import MarketStateView, apply_intraday_downgrade, freeze_market_state
from .session import TradingSession


def load_close_breadth_amount(engine: Engine, trading_date: date) -> tuple[float, float]:
    with engine.connect() as connection:
        previous = connection.execute(
            text("SELECT MAX(trade_date) FROM stock_daily WHERE trade_date < :trading_date"),
            {"trading_date": trading_date},
        ).scalar()
        current = connection.execute(
            text(
                "SELECT COUNT(pct_chg) AS valid_count, "
                "SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) AS up_count, "
                "SUM(amount) AS total_amount FROM stock_daily "
                "WHERE trade_date = :trading_date"
            ),
            {"trading_date": trading_date},
        ).mappings().first()
        previous_amount = connection.execute(
            text("SELECT SUM(amount) FROM stock_daily WHERE trade_date = :trading_date"),
            {"trading_date": previous},
        ).scalar()
    if previous is None or current is None:
        raise ValueError("全市场收盘数据缺失")
    valid_count = int(current["valid_count"] or 0)
    total_amount = float(current["total_amount"] or 0)
    previous_total = float(previous_amount or 0)
    if valid_count <= 0 or total_amount <= 0 or previous_total <= 0:
        raise ValueError("全市场广度或成交额无效")
    breadth = 100 * int(current["up_count"] or 0) / valid_count
    return round(breadth, 4), round(total_amount / previous_total, 4)


def live_market_metrics(
    indices: dict[str, object],
    breadth: dict[str, object] | None,
    sectors: list[dict[str, object]],
) -> tuple[float | None, float | None, int | None, bool]:
    required = {"000001", "399001", "000688"}
    if not required.issubset(indices) or not breadth:
        return None, None, None, False
    total = breadth.get("total")
    if not isinstance(total, dict):
        return None, None, None, False
    up = int(total.get("up") or 0)
    flat = int(total.get("flat") or 0)
    down = int(total.get("down") or 0)
    count = up + flat + down
    if count <= 0:
        return None, None, None, False
    try:
        index_change = sum(float(getattr(indices[code], "change_pct")) for code in required) / 3
    except (AttributeError, TypeError, ValueError):
        return None, None, None, False
    strong = {
        str(row.get("sector") or "").strip()
        for row in sectors
        if float(row.get("sector_chg") or 0) >= 1.0
    }
    strong.discard("")
    return round(index_change, 4), round(100 * up / count, 4), len(strong), True


def restore_market_state_view(saved: object, evidence: object | None) -> MarketStateView:
    payload = getattr(evidence, "payload", {}) if evidence is not None else {}
    indexes_above = payload.get("indexes_above_ma20")
    return MarketStateView(
        status=getattr(saved, "status").value,
        trading_date=getattr(saved, "trading_date"),
        as_of=getattr(saved, "as_of"),
        expires_at=getattr(saved, "as_of") + timedelta(days=1),
        indexes_above_ma20=int(indexes_above) if indexes_above is not None else None,
        breadth_pct=round(float(getattr(saved, "breadth_ratio")) * 100, 4),
        amount_ratio=float(getattr(saved, "turnover_ratio")),
        strong_sector_count=int(getattr(saved, "strong_sector_count")),
        reasons=tuple(getattr(saved, "reasons")),
        evidence_refs=tuple(getattr(saved, "evidence_refs")),
        index_change_pct=float(getattr(saved, "index_change_pct")),
        source=str(getattr(saved, "source")),
    )


class AutomaticMarketStateProvider:
    def __init__(
        self,
        *,
        load_close_state: Callable[[date], MarketStateView | None],
        capture_close_state: Callable[[date, datetime], MarketStateView],
        capture_intraday_state: Callable[[MarketStateView, datetime], MarketStateView],
        save_state: Callable[[MarketStateView], None],
    ) -> None:
        self._load_close_state = load_close_state
        self._capture_close_state = capture_close_state
        self._capture_intraday_state = capture_intraday_state
        self._save_state = save_state

    def get_state(self, context: object) -> MarketStateView:
        trading_date = getattr(context, "diagnosis_trade_date", None)
        now = getattr(context, "now_utc")
        if trading_date is None:
            return freeze_market_state(
                trading_date=None,
                as_of=now,
                reason="大盘状态交易日不可确认",
            )
        baseline = self._load_close_state(trading_date)
        if baseline is None:
            baseline = self._capture_close_state(trading_date, now)
            if baseline.status != "FREEZE":
                self._save_state(baseline)
        if getattr(context, "session") is not TradingSession.INTRADAY:
            return baseline
        intraday = self._capture_intraday_state(baseline, now)
        if intraday.status != "FREEZE":
            self._save_state(intraday)
        return intraday


def _completed_rows(rows: list[list[str]], trading_date: date) -> list[list[str]]:
    return [row for row in rows if date.fromisoformat(str(row[0])) <= trading_date]


def _above_ma20(rows: list[list[str]]) -> bool:
    if len(rows) < 20:
        raise ValueError("指数日线不足 20 根")
    closes = [float(row[2]) for row in rows[-20:]]
    if any(value <= 0 for value in closes):
        raise ValueError("指数日线收盘价无效")
    return closes[-1] > sum(closes) / 20


def build_closed_market_view(
    *,
    trading_date: date,
    as_of: datetime,
    index_rows: dict[str, list[list[str]]],
    breadth_pct: float,
    amount_ratio: float,
    evidence_refs: tuple[str, ...] = (),
) -> MarketStateView:
    required = ("000001", "399001", "000688")
    try:
        completed = {
            code: _completed_rows(index_rows.get(code, []), trading_date)
            for code in required
        }
        above = sum(_above_ma20(completed[code]) for code in required)
        index_change_pct = sum(float(completed[code][-1][8]) for code in required) / 3
        if not 0 <= breadth_pct <= 100:
            raise ValueError("全市场广度无效")
        if amount_ratio < 0:
            raise ValueError("成交额比无效")
    except (TypeError, ValueError) as exc:
        return freeze_market_state(
            trading_date=trading_date,
            as_of=as_of,
            reason=str(exc),
        )
    status = evaluate_market(MarketInputs(above, breadth_pct, amount_ratio, True))
    return MarketStateView(
        status=status,
        trading_date=trading_date,
        as_of=as_of,
        expires_at=as_of + timedelta(minutes=15),
        indexes_above_ma20=above,
        breadth_pct=round(breadth_pct, 4),
        amount_ratio=round(amount_ratio, 4),
        strong_sector_count=0,
        reasons=(f"收盘市场状态 {status}",),
        evidence_refs=evidence_refs,
        index_change_pct=round(index_change_pct, 4),
    )


def build_intraday_market_view(
    baseline: MarketStateView,
    *,
    as_of: datetime,
    breadth_pct: float,
    strong_sector_count: int,
    data_fresh: bool,
    evidence_refs: tuple[str, ...] = (),
    index_change_pct: float | None = None,
) -> MarketStateView:
    if not data_fresh:
        return freeze_market_state(
            trading_date=baseline.trading_date,
            as_of=as_of,
            reason="盘中市场证据缺失或过期",
        )
    status = apply_intraday_downgrade(
        baseline.status,
        breadth_pct,
        strong_sector_count,
        True,
    )
    reason = (
        "盘中广度与强势板块同时偏弱，市场状态降级"
        if status != baseline.status
        else f"盘中市场状态维持 {status}"
    )
    return MarketStateView(
        status=status,
        trading_date=baseline.trading_date,
        as_of=as_of,
        expires_at=as_of + timedelta(minutes=15),
        indexes_above_ma20=baseline.indexes_above_ma20,
        breadth_pct=round(breadth_pct, 4),
        amount_ratio=baseline.amount_ratio,
        strong_sector_count=strong_sector_count,
        reasons=(reason,),
        evidence_refs=baseline.evidence_refs + evidence_refs,
        emotion_label=baseline.emotion_label,
        index_change_pct=index_change_pct if index_change_pct is not None else baseline.index_change_pct,
        source="market-intraday",
    )


def build_default_market_state_provider(mysql_url: str) -> AutomaticMarketStateProvider:
    from .contracts import EvidenceSnapshotV1, MarketStateV1
    from .repositories import EvidenceRepository, PlanningRepository, create_mysql_engine

    engine = create_mysql_engine(mysql_url)
    evidence_repository = EvidenceRepository(engine)
    planning_repository = PlanningRepository(engine)

    def record_evidence(state: MarketStateView, raw_reference: str) -> MarketStateView:
        if state.status == "FREEZE":
            return state
        evidence_id = str(uuid4())
        payload = {
            "status": state.status,
            "trading_date": state.trading_date.isoformat() if state.trading_date else None,
            "indexes_above_ma20": state.indexes_above_ma20,
            "index_change_pct": state.index_change_pct,
            "breadth_pct": state.breadth_pct,
            "amount_ratio": state.amount_ratio,
            "strong_sector_count": state.strong_sector_count,
            "reasons": list(state.reasons),
        }
        evidence_repository.save_snapshot(
            EvidenceSnapshotV1(
                evidence_id=evidence_id,
                as_of=state.as_of,
                source=state.source,
                data_status="VALID",
                kind="MARKET",
                code=None,
                payload=payload,
                parser_version="market-regime-v1",
                raw_reference=raw_reference,
                expires_at=state.expires_at,
                freshness_seconds=max(0, int((state.expires_at - state.as_of).total_seconds())),
                quality_flags=[],
            )
        )
        return replace(state, evidence_refs=state.evidence_refs + (evidence_id,))

    def load_close_state(trading_date: date) -> MarketStateView | None:
        saved = planning_repository.get_latest_market_state(
            trading_date, source="market-close"
        )
        if saved is None:
            return None
        evidence = (
            evidence_repository.get_snapshot(saved.evidence_refs[0])
            if saved.evidence_refs
            else None
        )
        return restore_market_state_view(saved, evidence)

    def capture_close_state(trading_date: date, as_of: datetime) -> MarketStateView:
        try:
            from scripts.tools.fetch_eastmoney_quotes import fetch_index_kline_rows_opencli

            index_rows = fetch_index_kline_rows_opencli(
                ["000001", "399001", "000688"], limit=30
            )
            breadth_pct, amount_ratio = load_close_breadth_amount(engine, trading_date)
            state = build_closed_market_view(
                trading_date=trading_date,
                as_of=as_of,
                index_rows=index_rows,
                breadth_pct=breadth_pct,
                amount_ratio=amount_ratio,
            )
            return record_evidence(
                state,
                f"eastmoney-opencli:index-kline:{trading_date.isoformat()}",
            )
        except Exception as exc:  # noqa: BLE001
            return freeze_market_state(
                trading_date=trading_date,
                as_of=as_of,
                reason=f"收盘大盘状态采集失败：{type(exc).__name__}",
            )

    def capture_intraday_state(baseline: MarketStateView, as_of: datetime) -> MarketStateView:
        try:
            from scripts.tools.fetch_eastmoney_quotes import (
                fetch_domestic_market_opencli,
                fetch_hot_industry_board_rows_opencli,
            )

            indices, breadth = fetch_domestic_market_opencli(
                ["000001", "399001", "000688"], include_breadth=True
            )
            sectors = fetch_hot_industry_board_rows_opencli(top_n=20)
            index_change, breadth_pct, strong_count, fresh = live_market_metrics(
                indices, breadth, sectors
            )
            if breadth_pct is None or strong_count is None:
                fresh = False
                breadth_pct = 0.0
                strong_count = 0
            state = build_intraday_market_view(
                baseline,
                as_of=as_of,
                breadth_pct=breadth_pct,
                strong_sector_count=strong_count,
                data_fresh=fresh,
                index_change_pct=index_change,
            )
            return record_evidence(
                state,
                f"eastmoney-opencli:domestic-market:{as_of.isoformat()}",
            )
        except Exception as exc:  # noqa: BLE001
            return freeze_market_state(
                trading_date=baseline.trading_date,
                as_of=as_of,
                reason=f"盘中大盘状态采集失败：{type(exc).__name__}",
            )

    def save_state(state: MarketStateView) -> None:
        if (
            state.trading_date is None
            or state.index_change_pct is None
            or state.breadth_pct is None
            or state.amount_ratio is None
            or state.strong_sector_count is None
        ):
            return
        planning_repository.save_market_state(
            MarketStateV1(
                state_id=str(uuid4()),
                as_of=state.as_of,
                source=state.source,
                data_status="VALID",
                trading_date=state.trading_date,
                index_change_pct=Decimal(str(state.index_change_pct)),
                breadth_ratio=Decimal(str(state.breadth_pct / 100)),
                turnover_ratio=Decimal(str(state.amount_ratio)),
                strong_sector_count=state.strong_sector_count,
                status=state.status,
                reasons=list(state.reasons),
                evidence_refs=list(state.evidence_refs),
            )
        )

    return AutomaticMarketStateProvider(
        load_close_state=load_close_state,
        capture_close_state=capture_close_state,
        capture_intraday_state=capture_intraday_state,
        save_state=save_state,
    )
