"""LLM intent routing: chat / play / clarify (no regex)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import httpx

from server.config import settings

log = logging.getLogger(__name__)

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

ROUTER_SYSTEM = """你是小智儿童语音助手的意图路由器。结合对话历史，判断用户当前这句话要做什么。
只输出 JSON 对象，不要 markdown，不要额外文字：
{"action":"chat|play|clarify","reply":"中文口语回复","search_query":"play 时的网盘搜索词","media_hint":"story_audio|movie|music|any"}

action 含义：
- chat：问候、闲聊、问问题、感谢、告别等，不涉及网盘点播
- play：用户要听/看/播放某个作品或主题（含「想听」「讲个故事」「播放」）
- clarify：仅在完全听不懂、无法猜意图时使用；能合理默认时不要 clarify

默认策略（语音儿童场景）：
- 说作品名但未说故事/电影时，action=play，media_hint=story_audio，不要追问
- 「讲个故事」「儿童故事」「随便听一个」→ play，search_query 填主题
- 若上一轮已在 clarify，本轮必须给出 play 或 chat，禁止再次 clarify

字段规则：
- reply：chat/clarify 必填，1-2 句口语；play 时可留空或极短确认
- search_query：play 时填作品名/主题，不要填「想听」等动词
- media_hint：story_audio / movie / music / any
"""


@dataclass(frozen=True)
class RoutedIntent:
    action: str
    reply: str
    search_query: str = ""
    media_hint: str = "any"


def _extract_json_object(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(raw[start : end + 1])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    return _regex_extract_intent(raw)


def _regex_extract_intent(text: str) -> dict | None:
    action_m = re.search(r'"action"\s*:\s*"(chat|play|clarify)"', text, re.I)
    if not action_m:
        return None
    reply_m = re.search(r'"reply"\s*:\s*"([^"]*)"', text)
    query_m = re.search(r'"search_query"\s*:\s*"([^"]*)"', text)
    hint_m = re.search(r'"media_hint"\s*:\s*"(story_audio|movie|music|any)"', text, re.I)
    obj: dict[str, str] = {"action": action_m.group(1).lower()}
    if reply_m:
        obj["reply"] = reply_m.group(1)
    if query_m:
        obj["search_query"] = query_m.group(1)
    if hint_m:
        obj["media_hint"] = hint_m.group(1).lower()
    return obj


def _history_lines(history: list[dict[str, str]], limit: int = 8) -> str:
    if not history:
        return "（无）"
    lines: list[str] = []
    for msg in history[-limit:]:
        role = "用户" if msg.get("role") == "user" else "小智"
        content = str(msg.get("content") or "").strip()
        if content:
            lines.append(f"{role}：{content}")
    return "\n".join(lines) if lines else "（无）"


def _last_assistant_was_clarify(history: list[dict[str, str]] | None) -> bool:
    if not history:
        return False
    for msg in reversed(history):
        role = msg.get("role")
        content = str(msg.get("content") or "").strip()
        if role == "assistant" and content:
            return "故事" in content and "电影" in content and "？" in content
        if role == "user":
            break
    return False


def _normalize_action(value: str) -> str:
    action = (value or "").strip().lower()
    if action in {"chat", "play", "clarify"}:
        return action
    return "chat"


def _normalize_media_hint(value: str) -> str:
    hint = (value or "any").strip().lower()
    if hint in {"story_audio", "movie", "music", "any"}:
        return hint
    return "any"


async def _chat_fallback(
    user_text: str,
    history: list[dict[str, str]] | None,
    *,
    reason: str,
) -> RoutedIntent:
    log.warning("Intent router chat fallback (%s)", reason)
    from server.llm import chat_with_llm

    reply = await chat_with_llm(user_text, history or [])
    if not reply:
        reply = "我在呢，你可以再说一次吗？"
    return RoutedIntent(action="chat", reply=reply)


async def _call_router_llm(user_block: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.deepseek_api_key}",
    }
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": ROUTER_SYSTEM},
            {"role": "user", "content": user_block},
        ],
        "temperature": 0.2,
        "max_tokens": 280,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(DEEPSEEK_URL, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def analyze_user_intent(
    user_text: str,
    history: list[dict[str, str]] | None = None,
) -> RoutedIntent:
    text = (user_text or "").strip()
    if not text:
        return RoutedIntent(action="clarify", reply="我没听清，你可以再说一次吗？")

    if len(text) <= 2 and text in {"嗯", "啊", "呃", "哦", "噢"}:
        return RoutedIntent(
            action="clarify",
            reply="我只听到一点点声音，你可以完整说一句吗？比如「想听冰雪奇缘」。",
        )

    if not settings.deepseek_api_key:
        return RoutedIntent(
            action="chat",
            reply="我还连不上大模型，请检查 DEEPSEEK_API_KEY。",
        )

    user_block = (
        f"对话历史：\n{_history_lines(history or [])}\n\n"
        f"用户当前说：{text}"
    )
    if _last_assistant_was_clarify(history):
        user_block += "\n\n注意：上一轮已追问过，本轮禁止再 clarify，请直接 play 或 chat。"

    content = ""
    try:
        content = await _call_router_llm(user_block)
    except Exception as exc:
        log.warning("Intent router failed: %s", exc)
        return await _chat_fallback(text, history, reason=f"api: {exc}")

    obj = _extract_json_object(content)
    if not obj:
        log.warning("Intent router invalid JSON: %r", (content or "")[:240])
        return await _chat_fallback(text, history, reason="invalid_json")

    action = _normalize_action(str(obj.get("action", "chat")))
    reply = str(obj.get("reply") or "").strip()
    search_query = str(obj.get("search_query") or "").strip()
    media_hint = _normalize_media_hint(str(obj.get("media_hint") or "any"))

    if action == "clarify" and _last_assistant_was_clarify(history):
        action = "play"
        if not search_query:
            search_query = text
        media_hint = "story_audio"
        if not reply:
            reply = f"好的，我给你找{search_query}的故事。"

    if action == "play" and not search_query:
        search_query = text
    if action in {"chat", "clarify"} and not reply:
        reply = "好的，我在听呢。" if action == "chat" else "你可以说「想听某某故事」，我就能帮你找。"

    log.info(
        "Intent routed action=%s query=%r media=%s",
        action,
        search_query,
        media_hint,
    )
    return RoutedIntent(
        action=action,
        reply=reply,
        search_query=search_query,
        media_hint=media_hint,
    )
