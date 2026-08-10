"""XiaoZhi WebSocket JSON message helpers."""

from __future__ import annotations

import json
import uuid
from typing import Any


def new_session_id() -> str:
    return str(uuid.uuid4())


def server_hello(
    session_id: str,
    sample_rate: int = 24000,
    frame_ms: int = 60,
) -> dict[str, Any]:
    return {
        "type": "hello",
        "transport": "websocket",
        "session_id": session_id,
        "audio_params": {
            "format": "opus",
            "sample_rate": sample_rate,
            "channels": 1,
            "frame_duration": frame_ms,
        },
    }


def stt_message(session_id: str, text: str) -> dict[str, Any]:
    return {"session_id": session_id, "type": "stt", "text": text}


def llm_message(session_id: str, text: str, emotion: str = "happy") -> dict[str, Any]:
    return {
        "session_id": session_id,
        "type": "llm",
        "emotion": emotion,
        "text": text,
    }


def tts_message(session_id: str, state: str, text: str | None = None) -> dict[str, Any]:
    msg: dict[str, Any] = {"session_id": session_id, "type": "tts", "state": state}
    if text is not None:
        msg["text"] = text
    return msg


def dumps(msg: dict[str, Any]) -> str:
    return json.dumps(msg, ensure_ascii=False)
