"""Deterministic, source-backed prompts for DeepSeek browser writing."""

from __future__ import annotations

import re
from typing import Literal, Sequence
from urllib.parse import urlparse

BrowserPromptKind = Literal["hotspot", "literary"]

_SENSITIVE_RE = re.compile(
    r"(?:cookie|deepseek_api_key|wechat_mp_secret|token\s*=|\.env\b)", re.I
)


def _distinct_domains(urls: Sequence[str]) -> set[str]:
    return {
        (urlparse(url.strip()).hostname or "").lower()
        for url in urls
        if (urlparse(url.strip()).hostname or "").strip()
    }


def build_browser_prompt(
    *,
    kind: BrowserPromptKind,
    topic: str,
    thesis: str,
    fact_lines: Sequence[str],
    research_urls: Sequence[str],
) -> str:
    if kind not in {"hotspot", "literary"}:
        raise ValueError("kind 只允许 hotspot 或 literary")
    clean_topic = (topic or "").strip()
    clean_thesis = (thesis or "").strip()
    facts = tuple(line.strip() for line in fact_lines if line.strip())
    urls = tuple(url.strip() for url in research_urls if url.strip())
    if not clean_topic:
        raise ValueError("topic 不能为空")
    if len(clean_thesis) < 20:
        raise ValueError("原创判断不得少于 20 字")
    if not facts:
        raise ValueError("至少需要一条已核验事实")
    if len(_distinct_domains(urls)) < 3:
        raise ValueError("至少需要 3 个不同来源域")

    source_block = "\n".join(f"- {line}" for line in facts)
    url_block = "\n".join(f"- {url}" for url in urls)
    if kind == "hotspot":
        craft = """写作要求：
1. 标题不超过32字，用具体的人、动作、代价或利益冲突吸引点击，禁止虚假悬念。
2. 开篇直接进入冲突现场或具体后果，不用“近日”“引发关注”等通稿导语。
3. 全文围绕一句话钉子展开，事实、责任边界和普通人处境逐层推进。
4. 写出可站队、可反驳的判断，但不得虚构采访、当事人心理、聊天记录或不存在的个案。
5. 不要小标题，不要列表，不要编审过程，不要解释写法。
6. 结尾留下一个有边界的讨论问题，不强迫转发。"""
    else:
        craft = """写作要求：
1. 标题不超过32字，用作品中的选择、代价、人物命运或一句原文建立吸引力。
2. 第一段从作品场面、原文细节或节目动作进入，禁止百科式时间导语。
3. 叙述者保持隐形，不得虚构观看经历，不写“我哭了”“昨晚刚看”。
4. 直接引文必须来自事实包并控制长度；篇数、字数、时代和人物关系不得混写。
5. 全文围绕一句话钉子展开，不堆作品梗概，不做空泛升华。
6. 不要小标题，不要列表，不要解释写法；结尾停在画面、原文或一个讨论问题上。"""

    prompt = f"""请写一篇微信公众号长文。

稿型：{kind}
主题：{clean_topic}
一句话钉子：{clean_thesis}

以下是已核验事实，只能在这些事实范围内展开：
{source_block}

公开来源页：
{url_block}

{craft}

全文建议1600—2400字，使用适合手机阅读的短段落。第一行标题，空一行后输出纯段落正文，不附解释。"""
    if _SENSITIVE_RE.search(prompt):
        raise ValueError("提示词包含敏感字段，已拒绝发送")
    return prompt
