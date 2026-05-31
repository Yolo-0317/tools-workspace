"""投资看板 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.services import hub_auth, stock_bridge

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary(
    slot: str = "eod",
    strategy: str = "combined",
) -> dict[str, Any]:
    try:
        return stock_bridge.export_dashboard(snapshot_slot=slot, strategy=strategy)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/portfolio")
async def portfolio_current() -> dict[str, Any]:
    try:
        return stock_bridge.load_current_portfolio()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/monitor/rules")
async def monitor_rules() -> dict[str, Any]:
    try:
        return {"rules": stock_bridge.load_monitor_rules()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/monitor/dates")
async def monitor_dates(limit: int = 90) -> dict[str, Any]:
    return {"dates": stock_bridge.list_monitor_state_dates(limit=min(limit, 365))}


@router.get("/monitor/state")
async def monitor_state(date: str | None = None) -> dict[str, Any]:
    return stock_bridge.load_monitor_state(date)


@router.get("/discipline")
async def discipline() -> dict[str, Any]:
    try:
        return stock_bridge.load_discipline()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/portfolio/history")
async def portfolio_history(days: int = 90, slot: str = "eod") -> dict[str, Any]:
    try:
        return stock_bridge.load_portfolio_history(days=min(days, 365), snapshot_slot=slot)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/portfolio/snapshot")
async def portfolio_snapshot(date: str, slot: str = "eod") -> dict[str, Any]:
    try:
        return stock_bridge.load_portfolio_snapshot(date, snapshot_slot=slot)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/selection/strategies")
async def selection_strategies() -> dict[str, Any]:
    try:
        return {"strategies": stock_bridge.list_selection_strategies()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/selection/dates")
async def selection_dates(strategy: str = "combined") -> dict[str, Any]:
    try:
        dates = stock_bridge.list_selection_dates(strategy=strategy)
        return {"strategy": strategy, "dates": dates}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/selection/kline")
async def selection_kline(
    code: str,
    trade_date: str,
    days: int = 60,
) -> dict[str, Any]:
    try:
        return stock_bridge.load_selection_kline(
            code,
            trade_date,
            days=min(max(days, 5), 250),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/selection")
async def selection_history(
    request: Request,
    trade_date: str,
    strategy: str = "combined",
) -> dict[str, Any]:
    try:
        payload = stock_bridge.load_selection_history(trade_date, strategy=strategy)
        if getattr(request.state, "hub_role", "admin") == "share":
            return hub_auth.sanitize_selection_payload(payload)
        return payload
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/alerts/snapshot")
async def snapshot_alerts(limit: int = 30) -> dict[str, Any]:
    return {"lines": stock_bridge.tail_snapshot_alerts(limit=min(limit, 200))}


@router.get("/jobs")
async def launchd_jobs() -> dict[str, Any]:
    return {"jobs": stock_bridge.load_launchd_jobs()}
