"""选股单股 SOP 异步任务（OpenCLI 串行）。"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

_TZ = ZoneInfo("Asia/Shanghai")
_LOCK = threading.Lock()
_SOP_SERIAL = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(_TZ).isoformat(timespec="seconds")


def get_job(job_id: str) -> dict[str, Any] | None:
    return _JOBS.get(job_id)


def list_jobs(*, active_only: bool = False, limit: int = 30) -> list[dict[str, Any]]:
    """返回 SOP 任务列表（新→旧）。active_only 仅 queued/running。"""
    _prune_old_jobs()
    with _LOCK:
        jobs = [dict(j) for j in _JOBS.values()]
    jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)
    if active_only:
        jobs = [j for j in jobs if j.get("status") in {"queued", "running"}]
    return jobs[: max(1, min(limit, 100))]


def _prune_old_jobs(max_age_hours: int = 6) -> None:
    """清理已完成超过 max_age_hours 的任务，避免内存堆积。"""
    cutoff = datetime.now(_TZ).timestamp() - max_age_hours * 3600
    terminal = {"done", "done_with_warning", "failed"}

    def _ts(job: dict[str, Any]) -> float:
        raw = job.get("finished_at") or job.get("created_at") or ""
        if not raw:
            return 0.0
        try:
            return datetime.fromisoformat(raw).timestamp()
        except ValueError:
            return 0.0

    with _LOCK:
        stale = [
            jid
            for jid, job in _JOBS.items()
            if job.get("status") in terminal and _ts(job) < cutoff
        ]
        for jid in stale:
            del _JOBS[jid]


def _set_job(job_id: str, **fields: Any) -> None:
    with _LOCK:
        base = dict(_JOBS.get(job_id) or {})
        base.update(fields)
        base["job_id"] = job_id
        _JOBS[job_id] = base


def start_selection_sop_job(
    *,
    code: str,
    trade_date: str,
    strategy: str = "combined",
    row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """排队执行单股 SOP + 微信推送。"""
    from backend.services import stock_bridge

    code = str(code).split(".")[0].zfill(6)
    stock_name = ""
    if row:
        stock_name = str(row.get("名称") or row.get("name") or "").strip()
    job_id = uuid.uuid4().hex[:12]
    _set_job(
        job_id,
        status="queued",
        code=code,
        name=stock_name,
        trade_date=trade_date,
        strategy=strategy,
        created_at=_now_iso(),
        message="已排队，等待 OpenCLI 采集…",
    )

    def _worker() -> None:
        _set_job(job_id, status="running", started_at=_now_iso(), message="东财 SOP 采集中…")
        try:
            with _SOP_SERIAL:
                _set_job(job_id, message="OpenCLI 采集中 + DeepSeek 分析…")
                result = stock_bridge.run_selection_sop_single(
                    code,
                    trade_date=trade_date,
                    strategy=strategy,
                    row=row,
                    push_wechat=True,
                )
            msg = "已推送到微信" if result.get("wechat_pushed") else "分析完成"
            err = result.get("push_error")
            if err:
                msg = f"分析完成，但微信推送失败：{err}"
            _set_job(
                job_id,
                status="done" if result.get("wechat_pushed") else "done_with_warning",
                finished_at=_now_iso(),
                message=msg,
                name=result.get("name") or stock_name,
                result=result,
            )
        except Exception as exc:  # noqa: BLE001
            _set_job(
                job_id,
                status="failed",
                finished_at=_now_iso(),
                message=str(exc),
                error=str(exc),
            )

    threading.Thread(target=_worker, name=f"sop-{code}", daemon=True).start()
    return dict(_JOBS[job_id])
