#!/usr/bin/env python3
"""LLM 统一封装：DeepSeek API 或 Cursor CLI（agent --model auto）。"""

from __future__ import annotations

import os
import time

import requests

from scripts.tools.cursor_agent_client import (
    call_cursor_agent,
    cursor_agent_available,
    messages_to_prompt,
)

DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
MCP_MODEL = os.getenv("DEEPSEEK_MCP_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"))
DEFAULT_URL = "https://api.deepseek.com/v1/chat/completions"
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def llm_backend() -> str:
    """deepseek | cursor（默认写稿/战报等）"""
    return os.getenv("LLM_BACKEND", "deepseek").strip().lower()


def sop_llm_backend() -> str:
    """东财 SOP 并发终审：默认 deepseek，与 LLM_BACKEND 解耦。"""
    return os.getenv("SOP_LLM_BACKEND", "deepseek").strip().lower()


def _resolve_backend(explicit: str | None) -> str:
    return (explicit or llm_backend()).strip().lower()


def is_llm_configured(*, backend: str | None = None) -> bool:
    b = _resolve_backend(backend)
    if b == "cursor":
        return cursor_agent_available()
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def is_sop_llm_configured() -> bool:
    return is_llm_configured(backend=sop_llm_backend())


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


def _api_key() -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY 未设置")
    return api_key


def _cursor_model(explicit: str | None) -> str:
    return explicit or os.getenv("CURSOR_AGENT_MODEL", "auto")


def call_deepseek(
    messages: list[dict[str, str]],
    *,
    max_retries: int | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1200,
    model: str | None = None,
    timeout: tuple[float, float] | None = None,
    backend: str | None = None,
) -> str:
    """Chat Completions（messages 列表）。backend 覆盖 LLM_BACKEND（SOP 传 sop_llm_backend()）。"""
    if _resolve_backend(backend) == "cursor":
        _ = temperature, max_tokens, timeout  # Cursor CLI 不支持细粒度采样参数
        return call_cursor_agent(
            messages_to_prompt(messages),
            model=_cursor_model(model),
            max_retries=max_retries,
        )

    max_retries = max_retries if max_retries is not None else _env_int("DEEPSEEK_RETRIES", 3)
    connect_timeout = _env_float("DEEPSEEK_CONNECT_TIMEOUT_SECONDS", 10)
    read_timeout = _env_float("DEEPSEEK_TIMEOUT_SECONDS", 120)
    if timeout is None:
        timeout = (connect_timeout, read_timeout)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_api_key()}",
    }
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(DEFAULT_URL, headers=headers, json=payload, timeout=timeout)
            if resp.status_code in RETRYABLE_STATUS:
                raise RuntimeError(f"DeepSeek API HTTP {resp.status_code}: {resp.text[:200]}")
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt >= max_retries:
                break
            time.sleep(max(0.5, _env_float("DEEPSEEK_RETRY_BACKOFF_SECONDS", 2) * (2 ** (attempt - 1))))
    raise RuntimeError(f"DeepSeek API 调用失败（已重试 {max_retries} 次）: {last_err}")


def call_deepseek_prompt(
    prompt: str,
    *,
    temperature: float = 0.3,
    system: str = "你是一个专业的量化交易分析师，擅长技术分析和量价分析。",
    max_tokens: int | None = None,
    model: str | None = None,
    continue_on_length: bool | None = None,
    backend: str | None = None,
) -> str:
    """单条 user prompt（MCP / 持仓分析沿用；DeepSeek 支持 length 自动续写）。"""
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    if _resolve_backend(backend) == "cursor":
        content = call_cursor_agent(
            messages_to_prompt(messages),
            model=_cursor_model(model),
        )
        if continue_on_length is False:
            return content
        # Cursor 无 finish_reason；若明显截断可再续写一次
        if len(content) >= _env_int("CURSOR_AGENT_CONTINUE_MIN_CHARS", 3500):
            cont = call_cursor_agent(
                messages_to_prompt(
                    messages
                    + [{"role": "assistant", "content": content}]
                    + [{"role": "user", "content": "请从上次中断处继续输出，保持相同格式，不要重复前文。"}]
                ),
                model=_cursor_model(model),
            )
            content = (content.rstrip() + "\n" + cont.lstrip()).strip()
        return content

    max_tokens = max_tokens if max_tokens is not None else _env_int("DEEPSEEK_MAX_TOKENS", 1600)
    if continue_on_length is None:
        continue_on_length = str(os.getenv("DEEPSEEK_CONTINUE_ON_LENGTH") or "true").lower() in (
            "1",
            "true",
            "yes",
            "y",
            "on",
        )

    content, finish = _request_raw(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model or MCP_MODEL,
    )

    if continue_on_length and str(finish).lower() == "length":
        cont_messages = (
            messages
            + [{"role": "assistant", "content": content}]
            + [{"role": "user", "content": "请从上次中断处继续输出，保持相同格式，不要重复前文。"}]
        )
        cont_text, _ = _request_raw(
            cont_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model or MCP_MODEL,
        )
        content = (content.rstrip() + "\n" + cont_text.lstrip()).strip()

    return content


def _request_raw(
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    model: str,
) -> tuple[str, str | None]:
    max_retries = _env_int("DEEPSEEK_RETRIES", 3)
    connect_timeout = _env_float("DEEPSEEK_CONNECT_TIMEOUT_SECONDS", 10)
    read_timeout = _env_float("DEEPSEEK_TIMEOUT_SECONDS", 60)
    backoff_base = _env_float("DEEPSEEK_RETRY_BACKOFF_SECONDS", 2)

    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": int(max_tokens),
    }

    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                DEFAULT_URL,
                json=data,
                headers=headers,
                timeout=(connect_timeout, read_timeout),
            )
            if resp.status_code in RETRYABLE_STATUS:
                raise RuntimeError(f"DeepSeek API HTTP {resp.status_code}: {resp.text[:200]}")
            resp.raise_for_status()
            result = resp.json()
            choice = (result.get("choices") or [{}])[0] or {}
            content = ((choice.get("message") or {}) or {}).get("content") or ""
            return str(content), choice.get("finish_reason")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt >= max_retries:
                break
            time.sleep(max(0.5, backoff_base * (2 ** (attempt - 1))))
    raise RuntimeError(f"DeepSeek API 调用失败（已重试 {max_retries} 次）: {last_err}")
