"""通过 Cursor CLI（agent login）驱动聊天，与 wechat-acp 相同。"""

from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from backend.config import settings


class AgentCliError(Exception):
    pass


@dataclass
class AgentRunResult:
    session_id: str | None
    text: str
    is_error: bool
    raw_error: str = ""


def agent_cli_available() -> bool:
    return shutil.which("agent") is not None


async def check_agent_login() -> dict[str, Any]:
    if not agent_cli_available():
        return {"logged_in": False, "detail": "未找到 agent 命令"}
    proc = await asyncio.create_subprocess_exec(
        "agent",
        "status",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    text = (out or err).decode("utf-8", errors="replace").strip()
    logged_in = "Logged in" in text or "logged in" in text.lower()
    return {"logged_in": logged_in, "detail": text}


async def stream_agent_prompt(
    prompt: str,
    *,
    session_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """解析 agent -p stream-json 行，yield 结构化事件。"""
    cwd = str(settings.agent_cwd)
    model = settings.agent_model
    cmd = [
        "agent",
        "-p",
        "--force",
        "--output-format",
        "stream-json",
        "--stream-partial-output",
        "--model",
        model,
    ]
    if session_id:
        cmd.extend(["--resume", session_id])
    cmd.append(prompt)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None
    assert proc.stderr is not None

    new_session_id: str | None = session_id
    stderr_chunks: list[str] = []
    last_assistant_text = ""

    async def drain_stderr() -> None:
        assert proc.stderr is not None
        data = await proc.stderr.read()
        if data:
            stderr_chunks.append(data.decode("utf-8", errors="replace"))

    stderr_task = asyncio.create_task(drain_stderr())

    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            raw = line.decode("utf-8", errors="replace").strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                yield {"kind": "log", "text": raw}
                continue

            etype = event.get("type")
            if etype == "system" and event.get("subtype") == "init":
                new_session_id = event.get("session_id") or new_session_id
                yield {
                    "kind": "init",
                    "session_id": new_session_id,
                    "auth_source": event.get("apiKeySource"),
                }
                continue

            if etype == "thinking" and settings.forward_thoughts:
                if event.get("subtype") == "delta":
                    yield {"kind": "thinking_delta", "text": event.get("text", "")}
                continue

            if etype == "assistant":
                msg = event.get("message") or {}
                parts: list[str] = []
                for block in msg.get("content") or []:
                    if block.get("type") == "text" and block.get("text"):
                        parts.append(str(block["text"]))
                full = "".join(parts)
                if not full:
                    continue
                if full.startswith(last_assistant_text):
                    delta = full[len(last_assistant_text) :]
                else:
                    delta = full
                last_assistant_text = full
                if delta:
                    yield {"kind": "text_delta", "text": delta}
                continue

            if etype == "result":
                yield {
                    "kind": "result",
                    "session_id": event.get("session_id") or new_session_id,
                    "text": event.get("result") or "",
                    "is_error": bool(event.get("is_error")),
                }
                continue

            if etype == "error" or event.get("is_error"):
                yield {"kind": "error", "message": raw}
    finally:
        await proc.wait()
        await stderr_task

    if proc.returncode not in (0, None) and stderr_chunks:
        yield {
            "kind": "error",
            "message": "".join(stderr_chunks).strip() or f"agent 退出码 {proc.returncode}",
        }
