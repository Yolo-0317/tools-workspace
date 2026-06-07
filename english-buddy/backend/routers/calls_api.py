"""Active voice-call session stats."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from services.call_registry import call_registry

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.get("/active")
async def active_calls() -> Dict[str, Any]:
    """How many WebSocket clients are connected and in read-along."""
    return await call_registry.snapshot()
