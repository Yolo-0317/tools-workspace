"""Cursor CLI ACP（agent acp）客户端 — 与 wechat-acp 同款 JSON-RPC 协议。"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from backend.config import settings
from backend.services.agent_cli import (
    _agent_subprocess_env,
    agent_cli_available,
    check_agent_login,
)

logger = logging.getLogger(__name__)

NotificationHandler = Callable[[dict[str, Any]], Awaitable[None]]


class AcpSessionError(Exception):
    """ACP 会话不存在或已失效。"""


class AcpBridge:
    """长驻 agent acp 子进程，按 ACP 协议驱动多轮对话。"""

    def __init__(self) -> None:
        self._proc: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._write_lock = asyncio.Lock()
        self._notify_handler: NotificationHandler | None = None
        self._loaded_sessions: set[str] = set()
        self._ready = False
        self._start_error = ""

    @property
    def ready(self) -> bool:
        return self._ready and self._proc is not None and self._proc.returncode is None

    @property
    def start_error(self) -> str:
        return self._start_error

    async def start(self) -> None:
        if self.ready:
            return
        await self.stop()
        cmd = ["agent", "--model", settings.agent_model, "acp"]
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(settings.agent_cwd),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_agent_subprocess_env(),
            )
        except OSError as exc:
            self._start_error = str(exc)
            raise

        self._reader_task = asyncio.create_task(self._read_loop())
        try:
            await self._request(
                "initialize",
                {
                    "protocolVersion": 1,
                    "clientCapabilities": {
                        "fs": {"readTextFile": False, "writeTextFile": False},
                        "terminal": False,
                    },
                    "clientInfo": {"name": "home-hub", "version": "1.0.0"},
                },
                timeout=30,
            )
            await self._request(
                "authenticate",
                {"methodId": "cursor_login"},
                timeout=30,
            )
        except Exception as exc:
            self._start_error = str(exc)
            await self.stop()
            raise

        self._ready = True
        self._start_error = ""

    async def stop(self) -> None:
        self._ready = False
        self._loaded_sessions.clear()
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None
        if self._proc and self._proc.returncode is None:
            self._proc.kill()
            await self._proc.wait()
        self._proc = None
        for future in self._pending.values():
            if not future.done():
                future.set_exception(asyncio.CancelledError())
        self._pending.clear()

    async def stream_prompt(
        self,
        prompt: str,
        *,
        acp_session_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        if not self.ready:
            await self.start()

        events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        async def on_notify(params: dict[str, Any]) -> None:
            for event in _session_update_to_events(params, settings.forward_thoughts):
                await events.put(event)

        self._notify_handler = on_notify
        session_id = acp_session_id
        prompt_timeout = max(60, settings.agent_acp_prompt_timeout)

        try:
            session_id = await self._ensure_session(session_id)
            if not acp_session_id:
                yield {"kind": "init", "session_id": session_id}

            prompt_task = asyncio.create_task(
                self._request(
                    "session/prompt",
                    {
                        "sessionId": session_id,
                        "prompt": [{"type": "text", "text": prompt}],
                    },
                    timeout=prompt_timeout,
                )
            )

            while True:
                if prompt_task.done() and events.empty():
                    break
                try:
                    event = await asyncio.wait_for(events.get(), timeout=0.15)
                    yield event
                except TimeoutError:
                    if prompt_task.done():
                        break

            while not events.empty():
                yield await events.get()

            try:
                result = await prompt_task
            except AcpSessionError:
                raise
            except Exception as exc:
                yield {"kind": "error", "message": str(exc)}
                yield {
                    "kind": "result",
                    "session_id": session_id,
                    "text": "",
                    "is_error": True,
                }
                return

            stop_reason = str((result or {}).get("stopReason") or "")
            is_error = stop_reason not in ("", "end_turn")
            yield {
                "kind": "result",
                "session_id": session_id,
                "text": "",
                "is_error": is_error,
            }
        finally:
            self._notify_handler = None

    async def _ensure_session(self, acp_session_id: str | None) -> str:
        cwd = str(settings.agent_cwd)
        if acp_session_id is None:
            result = await self._request(
                "session/new",
                {"cwd": cwd, "mcpServers": []},
                timeout=60,
            )
            sid = str(result["sessionId"])
            self._loaded_sessions.add(sid)
            return sid

        if acp_session_id not in self._loaded_sessions:
            try:
                await self._request(
                    "session/load",
                    {
                        "sessionId": acp_session_id,
                        "cwd": cwd,
                        "mcpServers": [],
                    },
                    timeout=60,
                )
            except Exception as exc:
                raise AcpSessionError(str(exc)) from exc
            self._loaded_sessions.add(acp_session_id)
        return acp_session_id

    async def _request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout: float,
    ) -> Any:
        if not self._proc or not self._proc.stdin:
            raise RuntimeError("ACP 进程未启动")

        async with self._write_lock:
            req_id = self._next_id
            self._next_id += 1
            loop = asyncio.get_running_loop()
            future: asyncio.Future[Any] = loop.create_future()
            self._pending[req_id] = future
            payload = (
                json.dumps(
                    {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params},
                    ensure_ascii=False,
                )
                + "\n"
            )
            self._proc.stdin.write(payload.encode("utf-8"))
            await self._proc.stdin.drain()

        try:
            msg = await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(f"ACP {method} 超时（{int(timeout)}s）") from None

        if msg.get("error"):
            err = msg["error"]
            detail = err.get("message") or str(err)
            if method in {"session/load", "session/prompt"} and _looks_like_missing_session(
                detail, err
            ):
                raise AcpSessionError(detail)
            raise RuntimeError(detail)
        return msg.get("result")

    async def _respond(self, req_id: int, result: dict[str, Any]) -> None:
        if not self._proc or not self._proc.stdin:
            return
        async with self._write_lock:
            payload = (
                json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}, ensure_ascii=False)
                + "\n"
            )
            self._proc.stdin.write(payload.encode("utf-8"))
            await self._proc.stdin.drain()

    async def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        while True:
            line = await self._proc.stdout.readline()
            if not line:
                break
            raw = line.decode("utf-8", errors="replace").strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("ACP 非 JSON 行: %s", raw[:200])
                continue
            await self._dispatch(msg)

        if self._proc and self._proc.returncode not in (None, 0):
            stderr = ""
            if self._proc.stderr:
                stderr = (await self._proc.stderr.read()).decode("utf-8", errors="replace")
            self._start_error = stderr.strip() or f"agent acp 退出码 {self._proc.returncode}"
            self._ready = False

    async def _dispatch(self, msg: dict[str, Any]) -> None:
        req_id = msg.get("id")
        if req_id is not None and (msg.get("result") is not None or msg.get("error") is not None):
            future = self._pending.pop(int(req_id), None)
            if future and not future.done():
                future.set_result(msg)
            return

        method = msg.get("method")
        if not method:
            return

        if method == "session/update":
            if self._notify_handler:
                await self._notify_handler(msg.get("params") or {})
            return

        if method == "session/request_permission" and req_id is not None:
            await self._respond(
                int(req_id),
                {"outcome": {"outcome": "selected", "optionId": "allow-once"}},
            )
            return

        if method == "cursor/create_plan" and req_id is not None:
            await self._respond(int(req_id), {"outcome": {"outcome": "accepted"}})
            return

        if method == "cursor/ask_question" and req_id is not None:
            await self._respond(
                int(req_id),
                {"outcome": {"outcome": "skipped", "reason": "web-auto"}},
            )
            return

        if method == "cursor/generate_image" and req_id is not None:
            await self._respond(
                int(req_id),
                {"outcome": {"outcome": "rejected", "reason": "web-chat"}},
            )
            return

        if method == "cursor/task" and req_id is not None:
            await self._respond(int(req_id), {"outcome": {"outcome": "completed"}})
            return


def _looks_like_missing_session(detail: str, err: dict[str, Any]) -> bool:
    text = detail.lower()
    if "session" in text and any(k in text for k in ("not found", "invalid", "unknown", "expired")):
        return True
    code = err.get("code")
    return code in (-32602, -32603) and "session" in text


def _session_update_to_events(
    params: dict[str, Any],
    forward_thoughts: bool,
) -> list[dict[str, Any]]:
    update = params.get("update") or {}
    kind = update.get("sessionUpdate")
    events: list[dict[str, Any]] = []

    if kind == "agent_message_chunk":
        content = update.get("content") or {}
        if content.get("type") == "text":
            text = str(content.get("text") or "")
            if text:
                events.append({"kind": "text_delta", "text": text})
        return events

    if kind == "agent_thought_chunk" and forward_thoughts:
        content = update.get("content") or {}
        if content.get("type") == "text":
            text = str(content.get("text") or "")
            if text:
                events.append({"kind": "thinking_delta", "text": text})
        return events

    if kind == "tool_call":
        events.append(
            {
                "kind": "tool_start",
                "tool": update.get("title") or update.get("kind") or "tool",
                "tool_call_id": update.get("toolCallId"),
            }
        )
        return events

    if kind == "tool_call_update":
        status = str(update.get("status") or "")
        if status in {"completed", "failed", "cancelled"}:
            events.append(
                {
                    "kind": "tool_end",
                    "tool": update.get("toolCallId") or "tool",
                    "status": status,
                }
            )
        return events

    return events


acp_bridge = AcpBridge()


async def stream_acp_prompt(
    prompt: str,
    *,
    session_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """与 agent_cli.stream_agent_prompt 相同的事件结构。"""
    try:
        async for event in acp_bridge.stream_prompt(prompt, acp_session_id=session_id):
            yield event
    except AcpSessionError as exc:
        yield {"kind": "error", "message": str(exc), "code": "session_not_found"}
    except TimeoutError as exc:
        yield {"kind": "error", "message": str(exc), "code": "timeout"}
    except Exception as exc:  # noqa: BLE001
        yield {"kind": "error", "message": str(exc), "code": "acp_error"}


__all__ = [
    "AcpBridge",
    "AcpSessionError",
    "acp_bridge",
    "agent_cli_available",
    "check_agent_login",
    "stream_acp_prompt",
]
