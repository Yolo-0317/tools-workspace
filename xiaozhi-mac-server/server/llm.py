"""LLM chat routing: Ollama (local) or DeepSeek API."""

from __future__ import annotations

import logging

import httpx

from server.config import settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是小智，一个温柔、简短的儿童语音助手。"
    "回答用口语化中文，2-3 句话以内，适合 4-8 岁孩子听。"
    "不要使用 emoji 或表情符号。"
    "不要使用 markdown（星号、井号、编号列表），不要输出 JSON。"
    "这是纯语音播报：只写会被念出来的话，不要写神态、动作、外貌描写"
    "（如「笑容可掬」「眨眨眼」「开心地说」「温柔地」），也不要用括号旁白。"
)

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


def trim_history(history: list[dict[str, str]], max_turns: int | None = None) -> list[dict[str, str]]:
    limit = max_turns if max_turns is not None else settings.llm_history_turns
    if limit <= 0:
        return []
    max_messages = limit * 2
    if len(history) <= max_messages:
        return history
    return history[-max_messages:]


def build_messages(user_text: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *trim_history(history),
        {"role": "user", "content": user_text},
    ]


def record_chat_turn(
    history: list[dict[str, str]], user_text: str, reply: str
) -> None:
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})
    trimmed = trim_history(history)
    history[:] = trimmed


def _fallback_reply(user_text: str, reason: str) -> str:
    log.warning("LLM fallback (%s)", reason)
    if settings.llm_backend == "deepseek":
        return (
            f"我听到你说：{user_text}。"
            "我现在还没连上大模型，请检查 DEEPSEEK_API_KEY 或网络。"
        )
    return (
        f"我听到你说：{user_text}。"
        "我现在还没连上大模型，你可以先在终端里试试文字模式。"
    )


async def chat_with_ollama(user_text: str, history: list[dict[str, str]]) -> str:
    messages = build_messages(user_text, history)
    payload = {"model": settings.ollama_model, "messages": messages, "stream": False}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{settings.ollama_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return (data.get("message") or {}).get("content", "").strip()
    except Exception as exc:
        return _fallback_reply(user_text, f"ollama: {exc}")


async def chat_with_deepseek(user_text: str, history: list[dict[str, str]]) -> str:
    if not settings.deepseek_api_key:
        return _fallback_reply(user_text, "missing DEEPSEEK_API_KEY")

    messages = build_messages(user_text, history)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.deepseek_api_key}",
    }
    payload = {
        "model": settings.deepseek_model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": settings.llm_max_tokens,
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(DEEPSEEK_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return (data["choices"][0]["message"]["content"] or "").strip()
    except Exception as exc:
        return _fallback_reply(user_text, f"deepseek: {exc}")


async def chat_with_llm(user_text: str, history: list[dict[str, str]]) -> str:
    if settings.llm_backend == "deepseek":
        return await chat_with_deepseek(user_text, history)
    return await chat_with_ollama(user_text, history)
