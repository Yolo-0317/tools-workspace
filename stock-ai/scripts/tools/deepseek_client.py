#!/usr/bin/env python3
"""DeepSeek Chat API 轻量封装。"""

from __future__ import annotations

import os

import requests

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_URL = "https://api.deepseek.com/v1/chat/completions"


def call_deepseek(
    messages: list[dict[str, str]],
    *,
    max_retries: int = 3,
    temperature: float = 0.3,
    max_tokens: int = 1200,
    model: str = DEFAULT_MODEL,
) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY 未设置")

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_err: Exception | None = None
    for _ in range(max_retries):
        try:
            resp = requests.post(DEFAULT_URL, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
            last_err = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    raise RuntimeError(str(last_err))
