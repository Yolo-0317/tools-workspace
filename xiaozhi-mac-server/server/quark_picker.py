"""Use LLM to pick the best Quark file from search candidates."""

from __future__ import annotations

import json
import logging
import re

import httpx

from server.config import settings
from server.quark_client import QuarkFile

log = logging.getLogger(__name__)

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

_PICKER_SYSTEM = """你是儿童网盘点播助手。根据用户原话与 media_hint，从候选文件中选出最适合播放的一个。
只输出一行 JSON，不要 markdown：
{"index": 0}
或
{"index": null, "reason": "简短说明"}

规则：
- 根据用户意图选格式：故事/有声书、电影、儿歌，不要机械偏好某种后缀
- 避免：预告、片花、铃声、采访、歌单、MV、纯 BGM（除非用户要 music）
- 文件名应匹配用户提到的作品/主题
- index 必须是候选列表里的整数下标；都不合适则 null
"""


def _extract_json_object(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _candidate_rows(files: list[QuarkFile], limit: int) -> list[dict]:
    rows: list[dict] = []
    for i, item in enumerate(files[:limit]):
        size_mb = round(item.size / (1024 * 1024), 1) if item.size else 0
        rows.append(
            {
                "i": i,
                "name": item.filename[:120],
                "ext": item.ext,
                "size_mb": size_mb,
            }
        )
    return rows


def pick_quark_index_with_llm(
    user_text: str,
    keyword: str,
    candidates: list[QuarkFile],
    *,
    media_hint: str = "any",
) -> int | None:
    """Return candidate index, or None to keep heuristic ranking."""
    if not candidates or not settings.deepseek_api_key:
        return None
    if not settings.quark_pick_llm:
        return None
    # Heuristic is enough for 1–2 files; LLM only adds latency (felt as freeze).
    if len(candidates) <= 2:
        return None

    limit = min(len(candidates), settings.quark_pick_top)
    rows = _candidate_rows(candidates, limit)
    hint = (media_hint or "any").strip().lower()
    hint_label = {
        "story_audio": "故事/有声书（优先完整讲述，避免预告片花）",
        "movie": "电影/动画片全片（可 mp4/mkv，必要时提取音轨）",
        "music": "儿歌/歌曲",
        "any": "未限定，由文件名与语境判断",
    }.get(hint, "未限定，由文件名与语境判断")
    user_block = (
        f"用户原话：{user_text.strip() or keyword}\n"
        f"搜索关键词：{keyword.strip()}\n"
        f"用户想要的媒体类型：{hint_label}\n"
        f"候选文件：{json.dumps(rows, ensure_ascii=False)}"
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.deepseek_api_key}",
    }
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": _PICKER_SYSTEM},
            {"role": "user", "content": user_block},
        ],
        "temperature": 0.1,
        "max_tokens": 120,
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(DEEPSEEK_URL, headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        log.warning("Quark LLM pick failed: %s", exc)
        return None

    obj = _extract_json_object(content)
    if not obj:
        log.warning("Quark LLM pick invalid JSON: %r", (content or "")[:200])
        return None
    if obj.get("index") is None:
        log.info("Quark LLM pick declined: %s", obj.get("reason", ""))
        return None
    try:
        index = int(obj["index"])
    except (TypeError, ValueError):
        return None
    if index < 0 or index >= limit:
        log.warning("Quark LLM pick out of range: %s", index)
        return None
    log.info(
        "Quark LLM pick index=%s file=%s",
        index,
        candidates[index].filename,
    )
    return index


def reorder_candidates_by_llm(
    user_text: str,
    keyword: str,
    candidates: list[QuarkFile],
    *,
    media_hint: str = "any",
) -> list[QuarkFile]:
    index = pick_quark_index_with_llm(
        user_text,
        keyword,
        candidates,
        media_hint=media_hint,
    )
    if index is None:
        return candidates
    picked = candidates[index]
    rest = [item for i, item in enumerate(candidates) if i != index]
    return [picked, *rest]
