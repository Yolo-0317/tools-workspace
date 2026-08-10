#!/usr/bin/env python3
"""Cursor CLI（agent --print）非交互调用，走订阅额度而非 DeepSeek API。"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = ROOT / "investment-agent"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except ValueError:
        return default


def agent_bin() -> str:
    custom = os.getenv("CURSOR_AGENT_BIN", "").strip()
    if custom:
        return custom
    found = shutil.which("agent")
    if not found:
        raise RuntimeError("未找到 Cursor CLI `agent`，请先执行 agent login")
    return found


def agent_workspace() -> Path:
    for key in ("CURSOR_AGENT_WORKSPACE", "STOCK_AI_ROOT", "AGENT_CWD"):
        val = os.getenv(key, "").strip()
        if val:
            return Path(val).expanduser().resolve()
    if AGENT_ROOT.exists():
        return AGENT_ROOT
    return ROOT


def messages_to_prompt(messages: list[dict[str, str]]) -> str:
    labels = {"system": "系统指令", "user": "用户", "assistant": "助手"}
    parts: list[str] = []
    for msg in messages:
        role = str(msg.get("role") or "user")
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        parts.append(f"【{labels.get(role, role)}】\n{content}")
    if not parts:
        raise ValueError("messages 为空")
    return "\n\n".join(parts)


def call_cursor_agent(
    prompt: str,
    *,
    model: str | None = None,
    workspace: Path | None = None,
    mode: str | None = None,
    timeout_seconds: float | None = None,
    max_retries: int | None = None,
) -> str:
    """调用 `agent --print --mode ask --trust --model composer-2.5`（默认）。"""
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("prompt 为空")

    model = model or os.getenv("CURSOR_AGENT_MODEL", "composer-2.5")
    mode = mode or os.getenv("CURSOR_AGENT_MODE", "ask")
    workspace = workspace or agent_workspace()
    timeout_seconds = timeout_seconds if timeout_seconds is not None else _env_float(
        "CURSOR_AGENT_TIMEOUT_SECONDS", 300
    )
    max_retries = max_retries if max_retries is not None else _env_int("DEEPSEEK_RETRIES", 2)
    backoff = _env_float("DEEPSEEK_RETRY_BACKOFF_SECONDS", 3)

    cmd = [
        agent_bin(),
        "--print",
        "--mode",
        mode,
        "--trust",
        "--model",
        model,
        "--output-format",
        "text",
        "--workspace",
        str(workspace),
    ]

    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=str(workspace),
            )
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "agent 退出非零").strip()
                raise RuntimeError(err[:500])
            out = (proc.stdout or "").strip()
            if not out:
                raise RuntimeError("Cursor agent 返回空内容")
            return out
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt >= max_retries:
                break
            time.sleep(max(1.0, backoff * attempt))
    raise RuntimeError(f"Cursor agent 调用失败（已重试 {max_retries} 次）: {last_err}")


def cursor_agent_available() -> bool:
    try:
        agent_bin()
        return True
    except RuntimeError:
        return False
