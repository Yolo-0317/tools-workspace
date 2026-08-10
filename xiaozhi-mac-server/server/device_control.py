"""Control AtomS3R device via onboard MCP tools (volume, etc.)."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

_MCP_ID = 9001


async def call_device_tool(session, name: str, arguments: dict[str, Any] | None = None) -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": _MCP_ID,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments or {},
        },
    }
    await session.send_json(
        {
            "session_id": session.session_id,
            "type": "mcp",
            "payload": payload,
        }
    )
    log.info("Device MCP call: %s(%s)", name, arguments or {})


async def set_device_volume(session, volume: int) -> None:
    vol = max(0, min(100, int(volume)))
    await call_device_tool(session, "self.audio_speaker.set_volume", {"volume": vol})


async def bump_device_volume(session, delta: int = 15) -> int:
    current = int(getattr(session, "device_volume", 70))
    target = max(0, min(100, current + int(delta)))
    session.device_volume = target
    await set_device_volume(session, target)
    return target


async def ensure_device_volume(session) -> None:
    from server.config import settings

    session.device_volume = settings.device_default_volume
    await set_device_volume(session, session.device_volume)
