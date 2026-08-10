"""OpenCLI quote and fund-flow capture adapter for the evidence layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import os
from pathlib import Path
import re
import sys
from typing import Callable

from short_term_trading.chip import ChipKline, ChipMetrics, calculate_chip_metrics
from short_term_trading.evidence import CaptureRecorder


@dataclass(frozen=True)
class QuoteFundPayload:
    code: str
    price: float
    change_pct: float
    info_text: str
    fund_flow_text: str


@dataclass(frozen=True)
class ChipPayload:
    code: str
    metrics: ChipMetrics
    raw_evidence_ref: str


def _number_after_label(text: str, labels: tuple[str, ...]) -> float | None:
    for label in labels:
        match = re.search(rf"{re.escape(label)}[：:\s]*([+-]?[\d,.]+)", text or "")
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def default_quote_fund_fetcher(code: str) -> QuoteFundPayload:
    workspace_root = Path(__file__).resolve().parents[2]
    stock_ai_root = Path(os.getenv("STOCK_AI_ROOT", workspace_root / "stock-ai"))
    if not stock_ai_root.exists():
        raise RuntimeError("STOCK_AI_ROOT is unavailable for the OpenCLI adapter")
    sys.path.insert(0, str(stock_ai_root))
    from scripts.tools.fetch_eastmoney_quotes import fetch_sop_snapshots

    snapshot = fetch_sop_snapshots([code], include_fund_flow_page=True).get(code)
    if snapshot is None:
        raise RuntimeError("quote page returned no snapshot")
    return QuoteFundPayload(
        code=snapshot.code,
        price=snapshot.price,
        change_pct=snapshot.change_pct,
        info_text=snapshot.info_text,
        fund_flow_text=snapshot.fund_flow_text,
    )


def default_chip_fetcher(code: str) -> ChipPayload:
    workspace_root = Path(__file__).resolve().parents[2]
    stock_ai_root = Path(os.getenv("STOCK_AI_ROOT", workspace_root / "stock-ai"))
    if not stock_ai_root.exists():
        raise RuntimeError("STOCK_AI_ROOT is unavailable for the OpenCLI adapter")
    sys.path.insert(0, str(stock_ai_root))
    from scripts.tools.fetch_eastmoney_quotes import fetch_chip_kline_rows_opencli

    rows = fetch_chip_kline_rows_opencli(code, limit=210)
    bars: list[ChipKline] = []
    for row in rows:
        if len(row) < 11:
            raise ValueError("chip K-line row is incomplete")
        bars.append(
            ChipKline(
                trade_date=date.fromisoformat(row[0]),
                open=float(row[1]),
                close=float(row[2]),
                high=float(row[3]),
                low=float(row[4]),
                turnover_rate=float(row[10]),
            )
        )
    metrics = calculate_chip_metrics(bars)
    normalized = str(code).split(".")[0].strip().zfill(6)
    return ChipPayload(
        code=normalized,
        metrics=metrics,
        raw_evidence_ref=(
            f"eastmoney-opencli:kline:{normalized}:"
            f"{metrics.source_trade_date.isoformat()}"
        ),
    )


def capture_chip(
    code: str,
    recorder: CaptureRecorder,
    *,
    fetcher: Callable[[str], ChipPayload] = default_chip_fetcher,
    now: datetime | None = None,
) -> None:
    started_at = now or datetime.now(timezone.utc)
    try:
        payload = fetcher(code)
        finished_at = now or datetime.now(timezone.utc)
        recorder.record_payload(
            kind="chip",
            code=payload.code,
            source="eastmoney-opencli",
            parser_version="chip-cyq-v1",
            data=payload.metrics.to_payload(),
            raw_evidence_ref=payload.raw_evidence_ref,
            started_at=started_at,
            finished_at=finished_at,
        )
    except Exception as exc:  # noqa: BLE001
        recorder.record_source_error(
            kind="chip",
            code=code,
            source="eastmoney-opencli",
            parser_version="chip-cyq-v1",
            started_at=started_at,
            finished_at=now or datetime.now(timezone.utc),
            error=exc,
        )


def capture_quote_and_fund(
    code: str,
    recorder: CaptureRecorder,
    *,
    fetcher: Callable[[str], QuoteFundPayload] = default_quote_fund_fetcher,
    now: datetime | None = None,
) -> None:
    started_at = now or datetime.now(timezone.utc)
    try:
        payload = fetcher(code)
        finished_at = now or datetime.now(timezone.utc)
        quote_data = {
            "price": payload.price,
            "change_pct": payload.change_pct,
            "amount": _number_after_label(payload.info_text, ("成交额",)),
            "turnover": _number_after_label(payload.info_text, ("换手率", "换手")),
            "volume_ratio": _number_after_label(payload.info_text, ("量比",)),
        }
        recorder.record_payload(
            kind="quote",
            code=payload.code,
            source="eastmoney-opencli",
            parser_version="quote-v1",
            data=quote_data,
            raw_evidence_ref=f"eastmoney-opencli:quote:{payload.code}:{finished_at.isoformat()}",
            started_at=started_at,
            finished_at=finished_at,
        )
        fund_value = _number_after_label(payload.fund_flow_text, ("主力净流入",))
        recorder.record_payload(
            kind="fund_flow",
            code=payload.code,
            source="eastmoney-opencli",
            parser_version="fund-flow-v1",
            data={"main_net_inflow": fund_value},
            raw_evidence_ref=f"eastmoney-opencli:fund-flow:{payload.code}:{finished_at.isoformat()}",
            started_at=started_at,
            finished_at=finished_at,
        )
    except Exception as exc:  # noqa: BLE001
        recorder.record_source_error(
            kind="quote",
            code=code,
            source="eastmoney-opencli",
            parser_version="quote-v1",
            started_at=started_at,
            finished_at=now or datetime.now(timezone.utc),
            error=exc,
        )
