"""聊天服务：Cursor CLI ACP（agent acp）+ SSE。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from backend.config import settings
from backend.services import agent_acp, chat_store
from backend.services.agent_lock import AgentBusyError, agent_lock


class ChatAgentService:
    def __init__(self) -> None:
        self._login_ok = False
        self._login_detail = ""
        self._acp_error = ""

    async def startup(self) -> None:
        status = await agent_acp.check_agent_login()
        self._login_ok = bool(status.get("logged_in"))
        self._login_detail = str(status.get("detail") or "")
        if self._login_ok and agent_acp.agent_cli_available():
            try:
                await agent_acp.acp_bridge.start()
                self._acp_error = ""
            except Exception as exc:  # noqa: BLE001
                self._acp_error = str(exc)

    async def shutdown(self) -> None:
        await agent_acp.acp_bridge.stop()

    def health(self) -> dict[str, Any]:
        acp_ready = agent_acp.acp_bridge.ready
        return {
            "ready": self._login_ok
            and agent_acp.agent_cli_available()
            and acp_ready
            and not self._acp_error,
            "backend": "agent_acp",
            "auth": "agent login + agent acp（同 wechat-acp）",
            "model": settings.agent_model,
            "agent_cwd": str(settings.agent_cwd),
            "forward_thoughts": settings.forward_thoughts,
            "login_detail": self._login_detail,
            "acp_ready": acp_ready,
            "acp_error": self._acp_error or agent_acp.acp_bridge.start_error,
            "agent_lock": agent_lock.status(),
        }

    async def drop_agent(self, session_id: str) -> None:
        chat_store.clear_cursor_agent_id(session_id)

    async def stream_reply(
        self, session_id: str, user_text: str
    ) -> AsyncIterator[str]:
        if not user_text.strip():
            yield _sse("error", {"message": "消息不能为空"})
            return

        session = chat_store.get_session(session_id)
        if not session:
            yield _sse("error", {"message": "会话不存在"})
            return

        if not agent_acp.agent_cli_available():
            yield _sse(
                "error",
                {"message": "未找到 Cursor CLI（agent）", "code": "no_agent_cli"},
            )
            return

        if not self._login_ok:
            yield _sse(
                "error",
                {
                    "message": "请先在本机执行 agent login",
                    "code": "not_logged_in",
                    "detail": self._login_detail,
                },
            )
            return

        if not agent_acp.acp_bridge.ready:
            try:
                await agent_acp.acp_bridge.start()
                self._acp_error = ""
            except Exception as exc:  # noqa: BLE001
                self._acp_error = str(exc)
                yield _sse(
                    "error",
                    {
                        "message": f"ACP 启动失败：{exc}",
                        "code": "acp_start_failed",
                    },
                )
                return

        chat_store.add_message(session_id, "user", user_text)
        resume_ids: list[str | None] = [session.get("cursor_agent_id")]
        if resume_ids[0]:
            resume_ids.append(None)

        try:
            async with agent_lock.acquire(f"web:{session_id}"):
                assistant_parts: list[str] = []
                thinking_parts: list[str] = []
                final_session: str | None = resume_ids[0]
                last_error: str | None = None
                last_error_code: str | None = None

                for attempt_idx, resume_id in enumerate(resume_ids):
                    if attempt_idx > 0:
                        chat_store.clear_cursor_agent_id(session_id)
                        final_session = None
                        assistant_parts.clear()
                        last_error = None
                        last_error_code = None
                        yield _sse(
                            "status",
                            {
                                "phase": "retry",
                                "message": "会话异常，正在新建 Agent 会话重试…",
                            },
                        )

                    yield _sse("status", {"phase": "thinking"})

                    async for event in agent_acp.stream_acp_prompt(
                        user_text,
                        session_id=resume_id,
                    ):
                        kind = event.get("kind")
                        if kind == "init":
                            sid = event.get("session_id")
                            if sid:
                                chat_store.set_cursor_agent_id(session_id, sid)
                                final_session = sid
                            continue
                        if kind == "thinking_delta":
                            chunk = event.get("text", "")
                            thinking_parts.append(chunk)
                            yield _sse(
                                "thinking_delta", {"text": chunk}
                            )
                            continue
                        if kind == "text_delta":
                            chunk = event.get("text", "")
                            assistant_parts.append(chunk)
                            yield _sse("text_delta", {"text": chunk})
                            continue
                        if kind == "tool_start":
                            yield _sse(
                                "tool_start",
                                {
                                    "tool": event.get("tool", "tool"),
                                    "tool_call_id": event.get("tool_call_id"),
                                },
                            )
                            continue
                        if kind == "tool_end":
                            yield _sse(
                                "tool_end",
                                {
                                    "tool": event.get("tool", "tool"),
                                    "status": event.get("status"),
                                },
                            )
                            continue
                        if kind == "result":
                            if event.get("session_id"):
                                final_session = event["session_id"]
                                chat_store.set_cursor_agent_id(session_id, final_session)
                            if event.get("is_error"):
                                msg = "Agent 执行未完成"
                                last_error = msg
                                last_error_code = "agent_error"
                                yield _sse(
                                    "error",
                                    {"message": msg, "code": "agent_error"},
                                )
                            continue
                        if kind == "error":
                            msg = str(event.get("message") or "未知错误")
                            code = str(event.get("code") or "agent_error")
                            last_error = msg
                            last_error_code = code
                            if code != "session_not_found":
                                yield _sse(
                                    "error",
                                    {"message": msg, "code": code},
                                )

                    if assistant_parts or not last_error:
                        break
                    if last_error_code == "session_not_found" and attempt_idx == 0:
                        continue

                full_text = "".join(assistant_parts).strip()
                thinking_text = "".join(thinking_parts).strip()
                if thinking_text:
                    chat_store.add_message(session_id, "thinking", thinking_text)
                if full_text:
                    chat_store.add_message(session_id, "assistant", full_text)

                if full_text:
                    status = "success"
                elif last_error:
                    status = "error"
                else:
                    status = "empty"

                yield _sse(
                    "done",
                    {
                        "status": status,
                        "session_id": final_session,
                        "text": full_text,
                        "error": last_error,
                        "code": last_error_code,
                    },
                )
        except AgentBusyError as exc:
            msg = str(exc)
            yield _sse("error", {"message": msg, "code": "agent_busy"})
            yield _sse("done", {"status": "error", "error": msg, "code": "agent_busy"})
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            yield _sse("error", {"message": msg, "code": "internal"})
            yield _sse("done", {"status": "error", "error": msg, "code": "internal"})


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


chat_agent_service = ChatAgentService()
