"""聊天 REST + SSE 路由。"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from backend.config import settings
from backend.services import chat_store
from backend.services.chat_agent import chat_agent_service

router = APIRouter(prefix="/api/chat", tags=["chat"])

_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


class CreateSessionBody(BaseModel):
    title: str = "新对话"


class SendMessageBody(BaseModel):
    content: str = Field(..., min_length=1, max_length=8000)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_rate_limit(request: Request) -> None:
    key = _client_key(request)
    now = time.time()
    bucket = _rate_buckets[key]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= settings.chat_rate_limit:
        raise HTTPException(status_code=429, detail="发送过于频繁，请稍后再试")
    bucket.append(now)


@router.get("/health")
async def chat_health() -> dict[str, Any]:
    return chat_agent_service.health()


@router.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    return {"sessions": chat_store.list_sessions()}


@router.post("/sessions")
async def create_session(body: CreateSessionBody) -> dict[str, Any]:
    session = chat_store.create_session(title=body.title)
    return {"session": session}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    session = chat_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"session": session}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    await chat_agent_service.drop_agent(session_id)
    if not chat_store.delete_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


@router.get("/sessions/{session_id}/messages")
async def list_messages(session_id: str) -> dict[str, Any]:
    if not chat_store.get_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"messages": chat_store.list_messages(session_id)}


@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, body: SendMessageBody, request: Request):
    if not chat_store.get_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    _check_rate_limit(request)

    async def event_generator():
        async for chunk in chat_agent_service.stream_reply(session_id, body.content):
            # sse_starlette expects dict with event/data or raw string
            if chunk.startswith("event:"):
                lines = chunk.strip().split("\n")
                event_name = lines[0].split(": ", 1)[1]
                data = lines[1].split(": ", 1)[1]
                yield {"event": event_name, "data": data}
            else:
                yield {"data": chunk}

    return EventSourceResponse(event_generator())
