#!/usr/bin/env python3
"""FastMCP server: Quark audio for cloud+HTTP (resolve URL → device self.audio.play_url)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.example", override=False)

GATEWAY = os.getenv("XIAOZHI_GATEWAY", "http://127.0.0.1:8766").rstrip("/")
# Keep under cloud agent patience; long hangs feel like Xiaozhi froze.
TIMEOUT = float(os.getenv("MCP_HTTP_TIMEOUT", "28"))

mcp = FastMCP("QuarkAudio")

_SPEAK_FAIL = "抱歉，这个故事现在播不了，换一个名字试试好不好？"
_SPEAK_TIMEOUT = "网络有点慢，我没找到可播的故事，再说一次或者换一个好不好？"
_SPEAK_DOWN = "播放服务好像没开，请爸爸妈妈检查一下后再试。"


def _fail(error: str, *, speak_hint: str = _SPEAK_FAIL, **extra) -> dict:
    out = {
        "success": False,
        "error": error,
        "speak_hint": speak_hint,
        "instruction": (
            "Speak speak_hint to the child NOW in one short sentence. "
            "Do NOT call play_url. Do NOT retry the same tool with the same query. "
            "Do NOT stay silent."
        ),
    }
    out.update(extra)
    return out


def _post(path: str, payload: dict) -> dict:
    url = f"{GATEWAY}{path}"
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(url, json=payload)
            try:
                body = resp.json()
            except Exception:
                body = _fail(f"bad_json_http_{resp.status_code}", speak_hint=_SPEAK_DOWN)
            if not isinstance(body, dict):
                body = _fail("invalid_response", speak_hint=_SPEAK_DOWN)
            if resp.status_code >= 500 and not body.get("error"):
                body = _fail(f"gateway_http_{resp.status_code}", speak_hint=_SPEAK_DOWN)
            body.setdefault("http_status", resp.status_code)
            if not body.get("success"):
                body.setdefault("speak_hint", _SPEAK_FAIL)
                body.setdefault(
                    "instruction",
                    "Speak speak_hint now. Do not call play_url. Do not stay silent.",
                )
            return body
    except httpx.TimeoutException:
        return _fail("gateway_timeout", speak_hint=_SPEAK_TIMEOUT)
    except httpx.ConnectError:
        return _fail("gateway_unreachable", speak_hint=_SPEAK_DOWN)
    except Exception as exc:
        return _fail(f"gateway_error:{exc}"[:200], speak_hint=_SPEAK_DOWN)


def _resolve(query: str, media_hint: str = "story_audio", user_text: str = "") -> dict:
    return _post(
        "/api/media/resolve",
        {
            "query": query,
            "media_hint": media_hint,
            "user_text": user_text or query,
        },
    )


def _with_play_next_step(result: dict) -> dict:
    if result.get("success") and result.get("stream_url"):
        result["next_step"] = (
            "Call device tool self.audio.play_url with url=<stream_url>. "
            "Say one short OK phrase, then play. Do not say resource missing."
        )
    elif not result.get("success"):
        result.setdefault("speak_hint", _SPEAK_FAIL)
        result.setdefault(
            "instruction",
            "Speak speak_hint now. Do not call play_url. Do not stay silent.",
        )
    return result


@mcp.tool()
def resolve_quark_stream_url(
    query: str,
    media_hint: str = "story_audio",
    user_text: str = "",
) -> str:
    """【点播必用】把用户说法解析成可播放的 stream_url（device.mp3）。
    只播已配置的玥玥夸克目录（西游记、冰雪奇缘、Wow English、哈利波特、小猪佩奇等）。
    不在目录里：立刻朗读 speak_hint，禁止 search，禁止沉默。
    成功：必须立刻 self.audio.play_url(url=stream_url)，并说一句很短的确认。
    不要先 search_quark_audio。"""
    result = _with_play_next_step(
        _resolve(query, media_hint=media_hint, user_text=user_text or query)
    )
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def play_quark_audio(
    query: str,
    media_hint: str = "story_audio",
    user_text: str = "",
) -> str:
    """【云端+HTTP】解析故事并返回 stream_url。
    成功后必须调用设备 self.audio.play_url(url=stream_url)。
    失败则朗读 speak_hint，不要沉默、不要死循环重试。"""
    result = _with_play_next_step(
        _resolve(query, media_hint=media_hint, user_text=user_text or query)
    )
    if result.get("success") and result.get("stream_url"):
        result["playback_mode"] = "device_http_play_url"
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def search_quark_audio(
    query: str,
    media_hint: str = "story_audio",
    limit: int = 10,
) -> str:
    """仅浏览候选列表（调试用）。点播请直接用 resolve_quark_stream_url / play_quark_audio。
    不要用本工具判断「有没有资源」——会慢，且容易让对话卡住。"""
    listing = _post(
        "/api/mcp/search",
        {
            "query": query,
            "media_hint": media_hint,
            "limit": limit,
        },
    )
    listing["next_step"] = (
        "If user wants to play, call resolve_quark_stream_url or play_quark_audio "
        "(do not call this search tool again)."
    )
    count = int(listing.get("count") or 0)
    if not listing.get("success") or count <= 0:
        listing["success"] = False
        listing.setdefault("speak_hint", _SPEAK_FAIL)
        listing.setdefault(
            "instruction",
            "If user asked to play, speak speak_hint. Do not stay silent.",
        )
    return json.dumps(listing, ensure_ascii=False)


@mcp.tool()
def next_quark_audio() -> str:
    """下一集：返回新的 stream_url，再调用 self.audio.play_url。失败则朗读 speak_hint。"""
    result = _with_play_next_step(_post("/api/media/next", {}))
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def resume_quark_audio() -> str:
    """续播：返回 stream_url，再调用 self.audio.play_url。失败则朗读 speak_hint。"""
    result = _with_play_next_step(_post("/api/media/resume", {}))
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def quark_playback_status() -> str:
    """调试：媒体与 MCP 网关状态。"""
    try:
        with httpx.Client(timeout=8.0) as client:
            media = client.get(f"{GATEWAY}/api/media/status")
            mcp_st = client.get(f"{GATEWAY}/api/mcp/status")
            return json.dumps(
                {
                    "media": media.json()
                    if media.headers.get("content-type", "").startswith("application/json")
                    else media.text,
                    "mcp": mcp_st.json()
                    if mcp_st.headers.get("content-type", "").startswith("application/json")
                    else mcp_st.text,
                },
                ensure_ascii=False,
            )
    except Exception as exc:
        return json.dumps(_fail(f"status_error:{exc}"[:200], speak_hint=_SPEAK_DOWN), ensure_ascii=False)


@mcp.tool()
def list_fairy_tales() -> str:
    """列出可朗读的本地白话 TXT（含短篇童话 + 西游记分回）。
    用户说灰姑娘/讲西游记第N回等时，用 read_fairy_tale 取正文后口语朗读。"""
    from server.local_stories import list_story_titles

    return json.dumps(
        {"success": True, "stories": list_story_titles()},
        ensure_ascii=False,
    )


@mcp.tool()
def read_fairy_tale(query: str) -> str:
    """【短篇/分回朗读】读取本地 TXT 正文，供你用对话 TTS 讲给小朋友听。
    外国：灰姑娘、小红帽、睡美人、白雪公主、青蛙王子、三只小猪、穿靴子的猫。
    中国短篇：孔融让梨、司马光砸缸、曹冲称象、愚公移山、女娲补天、后羿射日、嫦娥奔月、牛郎织女、精卫填海、狐假虎威。
    西游记白话：讲西游记 / 西游记第N回（约 39 回；未指定从第 1 回）。
    成功后：把返回的 body 完整朗读出来，不要调用 self.audio.play_url，不要只概括。
    失败：朗读 speak_hint，不要沉默。
    「播放西游记」有声广播剧仍用 resolve_quark_stream_url + play_url。"""
    from server.local_stories import resolve_local_story

    result = resolve_local_story(query)
    if not result.get("success"):
        result.setdefault(
            "speak_hint",
            "这个故事我还不会讲，换灰姑娘或者西游记好不好？",
        )
        result.setdefault(
            "instruction",
            "Speak speak_hint now. Do not stay silent.",
        )
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
