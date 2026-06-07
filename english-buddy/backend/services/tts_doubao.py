"""ByteDance Volcano / 豆包语音合成（在线，需控制台开通）."""

from __future__ import annotations

import base64
import os
import uuid
from typing import Optional

import httpx

DOUBAO_API_URL = os.getenv(
    "DOUBAO_TTS_URL", "https://openspeech.bytedance.com/api/v1/tts"
)
DOUBAO_APP_ID = os.getenv("DOUBAO_APP_ID", "").strip()
DOUBAO_ACCESS_TOKEN = os.getenv("DOUBAO_ACCESS_TOKEN", "").strip()
DOUBAO_CLUSTER = os.getenv("DOUBAO_CLUSTER", "volcano_tts").strip()

# 豆包 App 常见女声：小何（亲切）· 爽快思思（活泼，更像「豆包」聊天感）
DOUBAO_VOICE_DEFAULT = os.getenv(
    "DOUBAO_VOICE_DEFAULT", "zh_female_xiaohe_uranus_bigtts"
)
DOUBAO_SPEED_RATIO = float(os.getenv("DOUBAO_SPEED_RATIO", "1.0"))
# 带读英文：en；中英混可不设
DOUBAO_EXPLICIT_LANGUAGE = os.getenv("DOUBAO_EXPLICIT_LANGUAGE", "en").strip()


def doubao_configured() -> bool:
    return bool(DOUBAO_APP_ID and DOUBAO_ACCESS_TOKEN)


def _parse_speed(rate: str | None) -> float:
    """Map edge-style TTS_RATE (-12%) to doubao speed_ratio."""
    if not rate:
        return DOUBAO_SPEED_RATIO
    s = rate.strip().rstrip("%")
    try:
        pct = float(s)
    except ValueError:
        return DOUBAO_SPEED_RATIO
    # -18% -> 0.82, +0% -> 1.0
    return max(0.5, min(2.0, 1.0 + pct / 100.0))


async def synthesize_mp3_bytes(
    text: str,
    voice_type: str | None = None,
    *,
    rate: str | None = None,
) -> bytes:
    if not doubao_configured():
        raise RuntimeError(
            "豆包 TTS 未配置：在 .env 设置 DOUBAO_APP_ID 与 DOUBAO_ACCESS_TOKEN "
            "（火山引擎 → 豆包语音）"
        )
    voice = (voice_type or "").strip() or DOUBAO_VOICE_DEFAULT
    speed = _parse_speed(rate)

    audio_cfg: dict = {
        "voice_type": voice,
        "encoding": "mp3",
        "speed_ratio": round(speed, 2),
    }
    if DOUBAO_EXPLICIT_LANGUAGE:
        audio_cfg["explicit_language"] = DOUBAO_EXPLICIT_LANGUAGE

    payload = {
        "app": {
            "appid": DOUBAO_APP_ID,
            "token": "access_token",
            "cluster": DOUBAO_CLUSTER,
        },
        "user": {"uid": "english-buddy"},
        "audio": audio_cfg,
        "request": {
            "reqid": str(uuid.uuid4()),
            "text": text.strip(),
            "operation": "query",
        },
    }
    headers = {
        "Authorization": f"Bearer;{DOUBAO_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(DOUBAO_API_URL, json=payload, headers=headers)

    try:
        body = resp.json()
    except Exception as exc:
        raise RuntimeError(f"豆包 TTS 响应非 JSON: HTTP {resp.status_code}") from exc

    code = body.get("code")
    if resp.status_code != 200 or code != 3000:
        msg = body.get("message") or resp.text
        raise RuntimeError(f"豆包 TTS 失败 code={code}: {msg}")

    data_b64 = body.get("data")
    if not data_b64:
        raise RuntimeError("豆包 TTS 返回空音频")
    return base64.b64decode(data_b64)
