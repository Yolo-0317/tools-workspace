#!/usr/bin/env python3
"""公众号标题+正文：DeepSeek 爆款写稿（排版配图由 Agent/Codex 流水线负责）。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.deepseek_client import call_deepseek, is_llm_configured

TITLE_MAX = 32

DIANJI_SYSTEM_PROMPT = (
    "你是《典籍里的中国》的「场记转写器」，不是评论员、不是观众、不是安利号小编。\n"
    "任务：把某一集舞台场面用纯纪实语言写成约 800 字讨论稿。\n"
    "硬性约束：\n"
    "1. 叙事人隐形（正文无「我」「我们」，戏中人物台词里的「我」除外）\n"
    "2. 只用镜头、对白、动作、客观转述，不写「他心里想」\n"
    "3. 禁：泪目、破防、感动、震撼、史诗、强烈推荐、鼻头一酸、太绝了、封神\n"
    "4. 开篇必须是戏里最狠的画面+对白，禁止以年月日、开播、节目简介开头\n"
    "5. 结尾停在画面或台词回响，禁止升华说教\n"
    "只输出 JSON。"
)

DEFAULT_SYSTEM_PROMPT = (
    "你是资深公众号编辑，擅长爆款标题和让人读完的开头。只输出 JSON。"
)


def wechat_mp_writer_backend() -> str:
    return os.getenv("WECHAT_MP_WRITER_BACKEND", "deepseek").strip().lower()


def is_deepseek_writer_configured() -> bool:
    return wechat_mp_writer_backend() == "deepseek" and is_llm_configured(backend="deepseek")


def is_dianji_subject(subject: str, *, topic_key: str = "") -> bool:
    blob = f"{subject} {topic_key}".strip()
    if not blob:
        return False
    if re.search(r"dianji[-_]", blob, re.I):
        return True
    return "典籍里的中国" in blob or "典籍里" in blob


def _dianji_topic_hints(topic_key: str) -> dict[str, str]:
    key = (topic_key or "").strip()
    if not key:
        return {}
    topics_path = (
        Path(__file__).resolve().parents[2] / "data" / "wechat_mp_dianji_zhongguo_topics.json"
    )
    if not topics_path.is_file():
        return {}
    try:
        data = json.loads(topics_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    slug = key.replace("_", "-")
    for season in data.get("seasons") or []:
        for ep in season.get("episodes") or []:
            cache = str(ep.get("cache") or "")
            if slug in cache or slug.endswith(key):
                return {
                    "ep": str(ep.get("ep") or ""),
                    "classic": str(ep.get("classic") or ""),
                    "nail": str(ep.get("nail") or ""),
                }
    return {}


def build_deepseek_dianji_user_prompt(
    subject: str,
    *,
    extra: str = "",
    topic_key: str = "",
) -> str:
    hints = _dianji_topic_hints(topic_key)
    ep = hints.get("ep") or "X"
    classic = hints.get("classic") or subject
    nail = hints.get("nail") or "本集唯一钉子"
    tail = f"\n补充：{extra.strip()}" if extra.strip() else ""
    return (
        f"【本期素材】\n"
        f"剧集：《典籍里的中国》第 {ep} 集《{classic}》\n"
        f"主题线索：{subject}\n"
        f"核心讨论点（钉子）：{nail}\n\n"
        "请写：\n"
        "a. 标题（32字内，无「我」；可用台词梗概/代价速写/古今错位）\n"
        "b. 正文 4～6 段约 800 字：第1段画面钉子+对白；第2段代价；第3段古今反差；"
        "第4段讨论钉子（问句）；第5段画面回响收束\n\n"
        "只输出 JSON：{\"title\":\"...\",\"body\":\"正文\"} 或 body 为段落数组\n"
        f"{tail}"
    )


def build_deepseek_writer_prompt(
    subject: str,
    *,
    extra: str = "",
    topic_key: str = "",
) -> str:
    """极简爆款写稿 prompt；典籍专栏叠加场面+对白开头要求。"""
    subject = (subject or "").strip()
    tail = f"\n补充：{extra.strip()}" if extra.strip() else ""
    dianji_block = ""
    if is_dianji_subject(subject, topic_key=topic_key):
        dianji_block = (
            "\n专栏：开篇场面+对白；背景时间放第2段之后，勿作首句。\n"
        )
    return (
        f"写一篇适合发微信公众号的短文。\n\n"
        f"主题：{subject}\n\n"
        "要求：\n"
        "1. 爆款标题（32字以内，让人想点开）\n"
        "2. 正文约800字，开头要有钩子、让人想读完，纯段落，不要小标题\n"
        "3. 你自己发挥，写得像真人看完节目跟朋友讲\n"
        f"{dianji_block}\n"
        "只输出 JSON，不要其它文字：\n"
        '{"title":"标题","body":"正文"}'
        f"{tail}"
    )


def _parse_writer_response(raw: str) -> dict[str, str]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            title = str(data.get("title") or "").strip()
            body_raw = data.get("body")
            if isinstance(body_raw, list):
                body = "\n\n".join(str(p).strip() for p in body_raw if str(p).strip())
            else:
                body = str(body_raw or "").strip()
            if title and body:
                return {"title": title[:TITLE_MAX], "body": body}
    except json.JSONDecodeError:
        pass
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("DeepSeek 写稿返回为空")
    title = lines[0][:TITLE_MAX]
    body = "\n\n".join(lines[1:]).strip() or title
    return {"title": title, "body": body}


def generate_deepseek_mp_piece(
    subject: str,
    *,
    extra: str = "",
    topic_key: str = "",
    temperature: float = 0.85,
    max_tokens: int = 2200,
) -> dict[str, str]:
    if not is_deepseek_writer_configured():
        raise RuntimeError(
            "DeepSeek 写稿未配置：设置 WECHAT_MP_WRITER_BACKEND=deepseek 且 DEEPSEEK_API_KEY"
        )
    dianji = is_dianji_subject(subject, topic_key=topic_key)
    if dianji:
        system = DIANJI_SYSTEM_PROMPT
        user = build_deepseek_dianji_user_prompt(
            subject, extra=extra, topic_key=topic_key
        )
    else:
        system = DEFAULT_SYSTEM_PROMPT
        user = build_deepseek_writer_prompt(subject, extra=extra, topic_key=topic_key)
    raw = call_deepseek(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        backend="deepseek",
    )
    parsed = _parse_writer_response(raw)
    body = re.sub(r"\n{3,}", "\n\n", parsed["body"]).strip()
    return {"title": parsed["title"][:TITLE_MAX], "body": body}


def subject_from_topic(topic: dict[str, Any]) -> str:
    trend = str(topic.get("trend_title") or "").strip()
    zh = str(topic.get("title_zh") or "").strip()
    label = str(topic.get("title_override") or topic.get("title_en") or "").strip()
    if trend:
        return trend
    if zh:
        return f"典籍里的中国 {zh}" if "典籍" not in zh else zh
    return label or "社会话题"


def generate_discussion_deepseek(topic: dict[str, Any]) -> str:
    piece = generate_deepseek_mp_piece(subject_from_topic(topic))
    return piece["body"]


def record_deepseek_writer_event(kind: str) -> None:
    from scripts.tools.wechat_mp_codex_client import CodexGenerationEvent, _EVENTS

    event = CodexGenerationEvent(
        provider="deepseek",
        mode="codex_exec",
        cli_version="deepseek-api",
        generated_at=__import__("datetime").datetime.now(
            __import__("zoneinfo").ZoneInfo("Asia/Shanghai")
        ).isoformat(timespec="seconds"),
        kind=kind.strip(),
    )
    _EVENTS.set((*_EVENTS.get(), event))
