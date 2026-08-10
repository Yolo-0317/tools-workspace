"""投资看板 API。"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.services import hub_auth, stock_bridge

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary(
    slot: str = "eod",
    strategy: str = "combined",
    live: bool = False,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            stock_bridge.export_dashboard,
            snapshot_slot=slot,
            strategy=strategy,
            live_quotes=live,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/portfolio")
async def portfolio_current() -> dict[str, Any]:
    try:
        return await asyncio.to_thread(stock_bridge.load_current_portfolio)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/portfolio/workbench")
async def portfolio_workbench() -> dict[str, Any]:
    """账户操作台：执行卡快照、行动队列与主题暴露。"""
    try:
        return stock_bridge.load_portfolio_workbench()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/monitor/rules")
async def monitor_rules(live: bool = True) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(stock_bridge.load_monitor_rules, live=live)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/monitor/dates")
async def monitor_dates(limit: int = 90) -> dict[str, Any]:
    dates = await asyncio.to_thread(
        stock_bridge.list_monitor_state_dates,
        limit=min(limit, 365),
    )
    return {"dates": dates}


@router.get("/monitor/state")
async def monitor_state(date: str | None = None) -> dict[str, Any]:
    return await asyncio.to_thread(stock_bridge.load_monitor_state, date)


@router.get("/advisor")
async def advisor_summary() -> dict[str, Any]:
    """投顾主策略摘要（阶段、回本、本周必做、最新周复盘）。"""
    try:
        return await asyncio.to_thread(stock_bridge.load_advisor_summary_with_weekly)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/advisor/weekly-reviews")
async def advisor_weekly_reviews(limit: int = 12) -> dict[str, Any]:
    try:
        rows = await asyncio.to_thread(
            stock_bridge.load_advisor_weekly_reviews,
            limit=min(max(1, limit), 52),
        )
        return {"reviews": rows}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/advisor/weekly-reviews/latest")
async def advisor_weekly_review_latest() -> dict[str, Any]:
    try:
        row = await asyncio.to_thread(stock_bridge.load_latest_advisor_weekly_review)
        return {"review": row}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/discipline")
async def discipline() -> dict[str, Any]:
    try:
        return await asyncio.to_thread(stock_bridge.load_discipline)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/portfolio/history")
async def portfolio_history(days: int = 90, slot: str = "eod") -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            stock_bridge.load_portfolio_history,
            days=min(days, 365),
            snapshot_slot=slot,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/portfolio/snapshot")
async def portfolio_snapshot(date: str, slot: str = "eod") -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            stock_bridge.load_portfolio_snapshot,
            date,
            snapshot_slot=slot,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/selection/strategies")
async def selection_strategies() -> dict[str, Any]:
    try:
        strategies = await asyncio.to_thread(stock_bridge.list_selection_strategies)
        return {"strategies": strategies}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/selection/dates")
async def selection_dates(strategy: str = "all") -> dict[str, Any]:
    try:
        dates = await asyncio.to_thread(
            stock_bridge.list_selection_dates,
            strategy=strategy,
        )
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
        return await asyncio.to_thread(
            stock_bridge.load_selection_kline,
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
    strategy: str = "all",
) -> dict[str, Any]:
    try:
        payload = await asyncio.to_thread(
            stock_bridge.load_selection_history,
            trade_date,
            strategy=strategy,
        )
        if getattr(request.state, "hub_role", "admin") == "share":
            return hub_auth.sanitize_selection_payload(payload)
        return payload
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/alerts/snapshot")
async def snapshot_alerts(limit: int = 30) -> dict[str, Any]:
    lines = await asyncio.to_thread(
        stock_bridge.tail_snapshot_alerts,
        limit=min(limit, 200),
    )
    return {"lines": lines}


@router.get("/jobs")
async def launchd_jobs() -> dict[str, Any]:
    jobs = await asyncio.to_thread(stock_bridge.load_launchd_jobs)
    return {"jobs": jobs}


def _news_disabled() -> None:
    from backend.config import settings

    if not settings.news_enabled:
        raise HTTPException(status_code=404, detail="财经快讯功能已关闭")


@router.get("/news/meta")
async def news_meta(date: str | None = None) -> dict[str, Any]:
    _news_disabled()
    try:
        return await asyncio.to_thread(stock_bridge.load_news_meta, date_str=date)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/news/items")
async def news_items(
    date: str | None = None,
    category: str | None = None,
    sentiment: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    _news_disabled()
    try:
        return await asyncio.to_thread(
            stock_bridge.load_news_items,
            date_str=date,
            category=category,
            sentiment=sentiment,
            limit=limit,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/news/briefings")
async def news_briefings(date: str | None = None) -> dict[str, Any]:
    _news_disabled()
    try:
        return await asyncio.to_thread(stock_bridge.load_news_briefings, date_str=date)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/news/briefings/latest")
async def news_briefing_latest() -> dict[str, Any]:
    _news_disabled()
    try:
        return await asyncio.to_thread(stock_bridge.load_latest_briefing)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/emotion/dates")
async def emotion_cycle_dates() -> dict[str, Any]:
    try:
        return await asyncio.to_thread(stock_bridge.list_emotion_cycle_dates)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/emotion")
async def emotion_cycle(
    trade_date: str | None = None,
    slot: str | None = None,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            stock_bridge.load_emotion_cycle,
            trade_date,
            checklist_slot=slot,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class SelectionSopAnalyzeBody(BaseModel):
    code: str
    trade_date: str
    strategy: str = "combined"


@router.post("/selection/sop-analyze")
async def selection_sop_analyze(
    request: Request,
    body: SelectionSopAnalyzeBody,
) -> dict[str, Any]:
    if getattr(request.state, "hub_role", None) != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可触发东财 SOP 分析")
    from backend.services import sop_jobs

    code = str(body.code).split(".")[0].zfill(6)
    try:
        row = await asyncio.to_thread(
            stock_bridge.find_selection_row,
            body.trade_date,
            body.strategy,
            code,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail=f"选股列表中未找到 {code}")
    job = sop_jobs.start_selection_sop_job(
        code=code,
        trade_date=body.trade_date,
        strategy=body.strategy,
        row=row,
    )
    return job


@router.get("/selection/sop-jobs")
async def selection_sop_jobs_list(
    request: Request,
    active_only: bool = False,
    limit: int = 30,
) -> dict[str, Any]:
    if getattr(request.state, "hub_role", None) != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看 SOP 任务")
    from backend.services import sop_jobs

    jobs = sop_jobs.list_jobs(active_only=active_only, limit=limit)
    active = sum(1 for j in jobs if j.get("status") in {"queued", "running"})
    return {"jobs": jobs, "active_count": active}


@router.get("/selection/sop-jobs/{job_id}")
async def selection_sop_job_status(request: Request, job_id: str) -> dict[str, Any]:
    if getattr(request.state, "hub_role", None) != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看 SOP 任务")
    from backend.services import sop_jobs

    job = sop_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job
