"""Ollama chat client."""

from __future__ import annotations

import os

import httpx

from prompts import READ_ALONG_ADDON, SYSTEM_PROMPT
from teaching.guide import load_teaching_addon
from teaching.programs import Program, get_program

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")


def system_content(
    reading_material: str | None = None,
    program: Program | None = None,
) -> str:
    prog = program or get_program(None)
    base = SYSTEM_PROMPT + prog.persona_addon() + load_teaching_addon()
    if reading_material and reading_material.strip():
        return base + READ_ALONG_ADDON.format(material=reading_material.strip())
    return base


def build_messages(
    user_text: str,
    history: list[dict[str, str]],
    reading_material: str | None = None,
    program_id: str | None = None,
) -> list[dict[str, str]]:
    program = get_program(program_id)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_content(reading_material, program)}
    ]
    for turn in history[-12:]:
        role = turn.get("role", "")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text.strip()})
    return messages


async def chat(
    user_text: str,
    history: list[dict[str, str]],
    reading_material: str | None = None,
    program_id: str | None = None,
) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": build_messages(user_text, history, reading_material, program_id),
        "stream": False,
        "options": {"temperature": 0.6, "num_predict": 120},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
        if r.status_code == 404:
            raise RuntimeError(
                f"Model '{OLLAMA_MODEL}' not found. Run: ollama pull {OLLAMA_MODEL}"
            )
        r.raise_for_status()
        data = r.json()
    text = (data.get("message") or {}).get("content") or ""
    return text.strip() or "Let's try again! Can you say that one more time?"


async def ollama_reachable() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_HOST}/api/tags")
            return r.status_code == 200
    except httpx.HTTPError:
        return False
