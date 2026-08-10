"""LLM turn with MCP tool calling (search/play Quark audio on device)."""

from __future__ import annotations

import json
import logging
import asyncio
from typing import Any

import httpx

from server.config import settings
from server.intent_router import DEEPSEEK_URL
from server.llm import record_chat_turn
from server.quark_mcp_tools import play_quark_on_session, search_quark_audio
from server.playback_intent import match_playback_intent
from server.user_turn import SendBinary, SendJson, _emit_spoken_reply

log = logging.getLogger(__name__)

MCP_SYSTEM = """你是小智儿童语音助手。用户通过语音和你对话。
你可以闲聊，也可以在夸克网盘里找故事/儿歌/电影并播放到已连接的小智音箱。

规则：
- 用户要听/看/播放某内容时，优先调用 play_quark_audio，不要只口头答应
- 不确定网盘里有什么时，可先 search_quark_audio 再 play
- 内容别名见 data/quark_content_aliases.json（玥玥：西游记、冰雪奇缘、Wow English、Alphablocks、童老师等）
- 用户说「继续播放/接着播/续播」：调用 resume_playback
- 用户说「下一集/下一首/换一集」：调用 play_next_episode（会自动根据播放记忆找下一集）
- 用户说「重新播放/再播一遍/刚才那个」：调用 replay_last
- 用户问「有什么可以听/有哪些故事」：调用 list_available_content
- 用户问「刚才播什么」：根据下方播放记忆口语回答，不必调用工具
- 用户说「声音大点/小点/音量」：用 adjust_device_volume 或 set_device_volume
- 用户说「停/别播了/停止播放」：调用 stop_playback
- 长内容播放中想打断：先说唤醒词「你好小智」，再说停或新指令；播放会连续进行，不会每几秒自动暂停
- 暂不支持快进/倒退；可续播、换集或重播
- 工具执行后，用 1-2 句口语中文告诉小朋友结果，每句不超过 20 字，总共不超过 2 句
- 纯语音播报：只写会被 TTS 念出来的话；不要写神态/动作/外貌描写（如「笑容可掬」「眨眨眼」「开心地」），不要括号旁白
- 不要用 markdown：禁止 **加粗**、编号列表（1. 2.）、井号标题；用口语短句即可
- 不要输出 markdown 或 JSON
- 调用 play_quark_audio 成功后不要冗长描述「找到了/开始播放」——设备会播简短确认语，你回复留空或一句「好的」即可
"""

MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_quark_audio",
            "description": "在夸克网盘搜索音频/故事/电影，返回候选列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "作品名或主题"},
                    "media_hint": {
                        "type": "string",
                        "enum": ["story_audio", "movie", "music", "any"],
                        "description": "内容类型，默认 story_audio",
                    },
                    "limit": {"type": "integer", "description": "返回条数，默认 10"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_quark_audio",
            "description": "在已连接的小智设备上播放夸克网盘里的音频/故事",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "作品名或主题"},
                    "media_hint": {
                        "type": "string",
                        "enum": ["story_audio", "movie", "music", "any"],
                    },
                    "user_text": {
                        "type": "string",
                        "description": "用户原话，可留空",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_device_volume",
            "description": "设置小智音箱音量，0-100",
            "parameters": {
                "type": "object",
                "properties": {
                    "volume": {"type": "integer", "description": "目标音量 0-100"},
                },
                "required": ["volume"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "adjust_device_volume",
            "description": "相对调节小智音箱音量，正数变大负数变小",
            "parameters": {
                "type": "object",
                "properties": {
                    "delta": {"type": "integer", "description": "变化量，例如 15 或 -15"},
                },
                "required": ["delta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_available_content",
            "description": "列出网盘库存索引里可播的儿童系列（已扫描的音频清单）",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "返回条数，默认 12"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resume_playback",
            "description": "从上次打断的位置继续播放",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replay_last",
            "description": "重新播放刚才/上一次的内容（从头开始）",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_next_episode",
            "description": "播放当前系列的下一集/下一首（依据播放记忆）",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_playback",
            "description": "停止当前正在播放的故事/音频，便于换集或重新点播",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


async def _run_tool(
    name: str,
    args: dict[str, Any],
    *,
    session,
    user_text: str,
) -> dict[str, Any]:
    if name == "search_quark_audio":
        return await asyncio.to_thread(
            search_quark_audio,
            str(args.get("query") or ""),
            media_hint=str(args.get("media_hint") or "story_audio"),
            limit=int(args.get("limit") or 10),
        )
    if name == "play_quark_audio":
        query = str(args.get("query") or "").strip()
        media_hint = str(args.get("media_hint") or "story_audio")
        spoken = str(args.get("user_text") or user_text or query).strip()
        return await play_quark_on_session(
            session,
            query,
            user_text=spoken,
            media_hint=media_hint,
            mode="search",
        )
    if name == "list_available_content":
        from server.media_index import index_available, list_series_summary

        if not index_available():
            return {
                "success": False,
                "error": "库存索引尚未生成",
                "items": [],
            }
        limit = int(args.get("limit") or 12)
        items = list_series_summary(limit)
        return {"success": True, "count": len(items), "items": items}
    if name == "resume_playback":
        return await play_quark_on_session(
            session,
            "",
            user_text=user_text,
            mode="resume",
        )
    if name == "replay_last":
        return await play_quark_on_session(
            session,
            "",
            user_text=user_text,
            mode="replay",
        )
    if name == "play_next_episode":
        return await play_quark_on_session(
            session,
            "",
            user_text=user_text,
            mode="next",
        )
    if name == "set_device_volume":
        from server.device_control import set_device_volume

        vol = int(args.get("volume") or settings.device_default_volume)
        session.device_volume = max(0, min(100, vol))
        await set_device_volume(session, session.device_volume)
        return {"success": True, "volume": session.device_volume}
    if name == "adjust_device_volume":
        from server.device_control import bump_device_volume

        delta = int(args.get("delta") or 15)
        vol = await bump_device_volume(session, delta)
        return {"success": True, "volume": vol, "delta": delta}
    if name == "stop_playback":
        await session.stop_playback(reason="tool")
        return {"success": True, "stopped": True}
    return {"success": False, "error": f"unknown tool: {name}"}


async def _deepseek_tool_turn(
    user_text: str,
    history: list[dict[str, str]],
    *,
    session,
) -> tuple[str, bool]:
    if not settings.deepseek_api_key:
        return "我还不能联网思考，请稍后再试。", False

    play_started = False

    memory_ctx = session.playback_memory.context_for_llm()
    from server.media_index import context_for_llm as index_ctx

    system = f"{MCP_SYSTEM}\n\n播放记忆：\n{memory_ctx}\n\n{index_ctx()}"

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for turn in history[-settings.llm_history_turns :]:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in {"user", "assistant"}:
            messages.append({"role": role, "content": content})
            continue
        user_part = turn.get("user", "")
        assistant_part = turn.get("assistant", "")
        if user_part:
            messages.append({"role": "user", "content": user_part})
        if assistant_part:
            messages.append({"role": "assistant", "content": assistant_part})
    messages.append({"role": "user", "content": user_text})

    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        for _round in range(4):
            payload = {
                "model": settings.deepseek_model,
                "messages": messages,
                "tools": MCP_TOOLS,
                "tool_choice": "auto",
                "max_tokens": settings.llm_max_tokens,
            }
            resp = await client.post(DEEPSEEK_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            tool_calls = message.get("tool_calls") or []

            if tool_calls:
                messages.append(message)
                for call in tool_calls:
                    fn = call.get("function") or {}
                    name = str(fn.get("name") or "")
                    raw_args = fn.get("arguments") or "{}"
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {}
                    log.info("MCP tool call: %s(%s)", name, args)
                    result = await _run_tool(
                        name,
                        args,
                        session=session,
                        user_text=user_text,
                    )
                    if name in {
                        "play_quark_audio",
                        "resume_playback",
                        "replay_last",
                        "play_next_episode",
                    } and result.get("started"):
                        play_started = True
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id"),
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                continue

            reply = str(message.get("content") or "").strip()
            if reply:
                return reply, play_started

    return "好的，我试试看。", play_started


async def handle_user_turn_mcp(
    user_text: str,
    *,
    history: list[dict[str, str]],
    session,
    send_json: SendJson,
    send_binary: SendBinary,
    session_id: str,
) -> None:
    text = (user_text or "").strip()
    if not text:
        await _emit_spoken_reply(
            send_json=send_json,
            send_binary=send_binary,
            session_id=session_id,
            user_text=user_text or "（空）",
            reply="我没听清，你可以再说一次吗？",
            emotion="sad",
        )
        return

    playback_intent = match_playback_intent(text)
    if playback_intent is not None:
        mode_map = {
            "resume": "resume",
            "next": "next",
            "replay": "replay",
        }
        if playback_intent.action == "memory_query":
            ctx = session.playback_memory.context_for_llm()
            last = session.playback_memory.last_played()
            if last:
                reply = f"刚才在播《{last.short_title()}》。"
            else:
                reply = "还没有播放记录呢。"
            record_chat_turn(history, text, reply)
            await _emit_spoken_reply(
                send_json=send_json,
                send_binary=send_binary,
                session_id=session_id,
                user_text=text,
                reply=reply,
                emotion="happy",
            )
            log.debug("Playback memory query: %s", ctx)
            return
        mode = mode_map.get(playback_intent.action)
        if mode:
            result = await play_quark_on_session(
                session,
                "",
                user_text=text,
                mode=mode,
            )
            if result.get("started"):
                log.info("Fast-path playback %s", mode)
                return
            err = str(result.get("error") or "暂时不能播放")
            record_chat_turn(history, text, err)
            await _emit_spoken_reply(
                send_json=send_json,
                send_binary=send_binary,
                session_id=session_id,
                user_text=text,
                reply=err,
                emotion="sad",
            )
            return

    reply, play_started = await _deepseek_tool_turn(text, history, session=session)

    if play_started or getattr(session, "_playback_active", False):
        session.mcp_audio_already_spoken = False
        if reply:
            record_chat_turn(history, text, reply)
        log.info("Skip duplicate TTS after quark playback started")
        return

    if getattr(session, "mcp_audio_already_spoken", False):
        session.mcp_audio_already_spoken = False
        if reply:
            record_chat_turn(history, text, reply)
        return

    record_chat_turn(history, text, reply)
    await _emit_spoken_reply(
        send_json=send_json,
        send_binary=send_binary,
        session_id=session_id,
        user_text=text,
        reply=reply,
        emotion="happy",
    )
