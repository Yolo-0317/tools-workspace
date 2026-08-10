#!/usr/bin/env python3
"""Bridge xiaozhi.me MCP WebSocket endpoint to local stdio MCP servers."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

import websockets
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.example", override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("MCP_PIPE")

INITIAL_BACKOFF = 1
MAX_BACKOFF = 600


def load_config() -> dict:
    path = os.environ.get("MCP_CONFIG") or str(_ROOT / "mcp_config.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build_server_command(target: str) -> tuple[list[str], dict[str, str]]:
    cfg = load_config()
    servers = cfg.get("mcpServers", {}) if isinstance(cfg, dict) else {}
    if target in servers:
        entry = servers[target] or {}
        if entry.get("disabled"):
            raise RuntimeError(f"Server '{target}' is disabled")
        typ = (entry.get("type") or "stdio").lower()
        child_env = os.environ.copy()
        for key, value in (entry.get("env") or {}).items():
            child_env[str(key)] = str(value)
        if typ != "stdio":
            raise RuntimeError(f"Unsupported server type: {typ}")
        command = entry.get("command") or sys.executable
        args = entry.get("args") or []
        return [command, *args], child_env

    script_path = Path(target)
    if not script_path.is_absolute():
        script_path = _ROOT / script_path
    if not script_path.exists():
        raise RuntimeError(f"Missing MCP server script: {script_path}")
    return [sys.executable, str(script_path)], os.environ.copy()


async def pipe_websocket_to_process(websocket, process, target: str) -> None:
    try:
        while True:
            message = await websocket.recv()
            if isinstance(message, bytes):
                message = message.decode("utf-8")
            process.stdin.write(message + "\n")
            process.stdin.flush()
    finally:
        if process.stdin and not process.stdin.closed:
            process.stdin.close()


async def pipe_process_to_websocket(process, websocket, target: str) -> None:
    while True:
        data = await asyncio.to_thread(process.stdout.readline)
        if not data:
            logger.info("[%s] MCP process stdout closed", target)
            break
        await websocket.send(data)


async def pipe_process_stderr_to_terminal(process, target: str) -> None:
    while True:
        data = await asyncio.to_thread(process.stderr.readline)
        if not data:
            break
        sys.stderr.write(data)
        sys.stderr.flush()


async def connect_to_server(uri: str, target: str) -> None:
    process = None
    try:
        logger.info("[%s] Connecting to %s", target, uri)
        async with websockets.connect(uri) as websocket:
            cmd, env = build_server_command(target)
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                text=True,
                env=env,
                cwd=str(_ROOT),
            )
            logger.info("[%s] Started MCP server: %s", target, " ".join(cmd))
            await asyncio.gather(
                pipe_websocket_to_process(websocket, process, target),
                pipe_process_to_websocket(process, websocket, target),
                pipe_process_stderr_to_terminal(process, target),
            )
    finally:
        if process is not None:
            logger.info("[%s] Stopping MCP server process", target)
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


async def connect_with_retry(uri: str, target: str) -> None:
    backoff = INITIAL_BACKOFF
    attempt = 0
    while True:
        try:
            if attempt > 0:
                logger.info("[%s] Reconnect in %ss (attempt %s)", target, backoff, attempt)
                await asyncio.sleep(backoff)
            await connect_to_server(uri, target)
        except Exception as exc:
            attempt += 1
            logger.warning("[%s] Connection lost: %s", target, exc)
            backoff = min(backoff * 2, MAX_BACKOFF)


def signal_handler(_sig, _frame) -> None:
    logger.info("Interrupted, exiting")
    sys.exit(0)


async def _main() -> None:
    endpoint = os.environ.get("MCP_ENDPOINT")
    if not endpoint:
        raise RuntimeError("Set MCP_ENDPOINT (xiaozhi.me console MCP WebSocket URL)")

    target = sys.argv[1] if len(sys.argv) >= 2 else "quark-audio"
    await connect_with_retry(endpoint, target)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
