#!/usr/bin/env python3
"""DeepSeek 成稿后 Agent 层：观察者口吻、逻辑与禁「初发现节目」腔。"""

from __future__ import annotations

import re
from typing import Any

# 像第一次刷到节目的开篇
_DISCOVERY_OPENING_RE = re.compile(
    r"(昨晚看|刚看完|第一次看|本来以为|没想到|结果.{0,6}出场|我整个人)"
)

# 第一人称亲历 / 日记腔（观察者稿硬删）
_FIRST_PERSON_RE = re.compile(
    r"(^|[。！？\n])我(们)?(当时|整个人|忽然|特意|躺|给我爸|翻出来|在沙发)"
)

# 收尾升华腔
_PITCH_TAIL_RE = re.compile(
    r"你如果有空|真的去看看|别嫌它|绝对看不腻|强烈建议"
)
_SERMON_TAIL_RE = re.compile(r"(希望|最好的|值得我们|让我们)")
_TIMELINE_OPEN_RE = re.compile(r"^\s*\d{4}年")
_SCENE_OPEN_MARKERS = ("「", "」", "嚎", "哭", "抱", "竹简", "嘶哑", "掘")


def _first_paragraph(text: str) -> str:
    parts = [p.strip() for p in (text or "").strip().split("\n\n") if p.strip()]
    return parts[0] if parts else ""


def protect_opening_paragraph(before: str, after: str) -> str:
    """润色层不得磨平场面开头：第一段含场面标记且被改写则还原。"""
    fp_before = _first_paragraph(before)
    fp_after = _first_paragraph(after)
    if not fp_before or fp_before == fp_after:
        return after
    if any(m in fp_before for m in _SCENE_OPEN_MARKERS):
        tail = after.split("\n\n", 1)[1].strip() if "\n\n" in after else ""
        return fp_before + (f"\n\n{tail}" if tail else "")
    return after


def scan_deepseek_observer_issues(text: str) -> list[str]:
    issues: list[str] = []
    if not text.strip():
        return ["正文为空"]
    first = _first_paragraph(text)
    if _DISCOVERY_OPENING_RE.search(text[:200]):
        issues.append("开篇像第一次发现节目（昨晚看/本来以为等）")
    if _TIMELINE_OPEN_RE.match(first):
        issues.append("开篇时间公文（首段以年份开头）")
    if text.count("我") >= 3:
        issues.append(f"第一人称「我」过多（{text.count('我')} 处）")
    for pat, label in (
        (_FIRST_PERSON_RE, "第一人称亲历叙述"),
        (_PITCH_TAIL_RE, "安利式收尾"),
    ):
        if pat.search(text):
            issues.append(label)
    if "你知道" in text[:300] and "吗？" in text[:300]:
        issues.append("开篇科普腔「你知道…吗」")
    last = _first_paragraph(text.split("\n\n")[-1] if text else "")
    if last and _SERMON_TAIL_RE.search(last):
        issues.append("收尾升华腔（希望/值得/让我们）")
    return issues


def polish_deepseek_observer_voice(title: str, body: str) -> dict[str, str]:
    """
    规则层快速清洗（非 LLM）。DeepSeek 爆款稿进缓存前必过。
    复杂改写由 Agent 按 human-say-pass / 角色卡手工或再调 LLM。
    """
    t = (title or "").strip()
    b = (body or "").strip()
    t = re.sub(r"我[^，。！？]{0,12}(惨|哭|绷不住)", "把人演哭", t)
    t = re.sub(r"^我", "", t).strip() or t
    if len(t) > 32:
        t = t[:32]

    # 仅做明显安利句删除；全文改写走缓存人工/agent
    lines = []
    for line in b.splitlines():
        if _PITCH_TAIL_RE.search(line):
            continue
        lines.append(line)
    b = "\n".join(lines).strip()
    b = re.sub(r"\n{3,}", "\n\n", b)
    return {"title": t, "body": b}


def assert_observer_ready(title: str, body: str) -> None:
    issues = scan_deepseek_observer_issues(body)
    if "我" in title:
        issues.append("标题含第一人称「我」")
    if issues:
        raise ValueError("DeepSeek 稿需观察者润色: " + "; ".join(issues))


def polish_deepseek_observer_llm(
    title: str,
    body: str,
    *,
    dianji: bool = False,
) -> dict[str, str]:
    """DeepSeek 第二层：观察者口吻，禁初发现节目腔与第一人称叙事。"""
    from scripts.tools.deepseek_client import call_deepseek
    from scripts.tools.wechat_mp_deepseek_writer import (
        _parse_writer_response,
        is_deepseek_writer_configured,
        is_dianji_subject,
    )

    if not is_deepseek_writer_configured():
        return polish_deepseek_observer_voice(title, body)

    dianji = dianji or is_dianji_subject(title) or is_dianji_subject(body[:120])
    opening_rule = (
        "2. 保护性剪辑：禁止改写、重排第一段；具体名词/数量/动作不可替换\n"
        "3. 删作者第一人称「我」「我们」及评价煽情词，保留戏里台词\n"
        if dianji
        else "2. 开头不要像第一次刷到节目\n"
        "3. 不用「你知道…吗」科普腔开头\n"
    )
    prompt = (
        "你是主编终审，只做保护性剪辑，不是润色改写。\n\n"
        "必须做到：\n"
        "1. 删作者视角残留（正文「我」「我们」、私人经历、沙发哭、给爸发微信等）\n"
        f"{opening_rule}"
        "4. 删掉安利收尾；末段删「希望/值得/让我们」类升华句\n"
        "5. 保留事实、对白、口语劲道\n"
        "6. 标题不含「我」，32字以内\n\n"
        f"标题：{title}\n\n正文：\n{body}\n\n"
        "只输出 JSON：{\"title\":\"...\",\"body\":\"...\"}"
    )
    raw = call_deepseek(
        [
            {"role": "system", "content": "公众号观察者口吻改稿。只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.45,
        max_tokens=2800,
        backend="deepseek",
    )
    parsed = _parse_writer_response(raw)
    protected_body = protect_opening_paragraph(body, parsed["body"])
    out = polish_deepseek_observer_voice(parsed["title"], protected_body)
    issues = scan_deepseek_observer_issues(out["body"])
    if "我" in out["title"]:
        issues.append("标题含我")
    if issues:
        raise ValueError("观察者润色后仍有问题: " + "; ".join(issues))
    return out
