#!/usr/bin/env python3
"""搜一搜内容规则 → eval / traffic 自动项（官方教程 01 落地）。"""

from __future__ import annotations

import re

from scripts.tools.wechat_mp_prose import (
    HOTSPOT_BANNED_SECTION_TITLES,
    HOTSPOT_BOILERPLATE_PHRASES,
    HOTSPOT_RIGID_FIELD_LABELS,
    strip_hotspot_subheadings,
)

# 标题在「…」前若以这些字结尾，视为半句话（路牌不完整）
_INCOMPLETE_BEFORE_ELLIPSIS = re.compile(
    r"[返从在与和及对向至及将被把暂临][…\.]{1,3}"
)

_TITLE_SELECTION_LEAK = re.compile(
    r"候选.{0,6}条|五条候选|在候选|没选其它|为何没选|故舍弃|同批素材|同批\s*news"
)

_HOTSPOT_LIST_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:[1-9]|10)[\.、．]\s*.{4,40}(?:\n\s*(?:[1-9]|10)[\.、．])",
    re.MULTILINE,
)

_WHY_SECTION = "为啥盯这条"  # 仅用于旧稿 leak 检测
HOTSPOT_MIN_CHARS = 2000


def _strip_for_match(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


def check_title_sousou_complete(title: str) -> tuple[bool, list[str]]:
    """标题表意完整：禁止「返…」「暂…」等搜一搜截断后仍残缺的半句。"""
    notes: list[str] = []
    t = (title or "").strip()
    if not t:
        return False, ["标题为空"]

    if _INCOMPLETE_BEFORE_ELLIPSIS.search(t):
        notes.append("标题含半句话截断（如 返…/暂…），须写完整谓语（返港/暂闭）")
        return False, notes

    if re.search(r"[…\.]{2,}", t) and not re.search(
        r"(有什么影响|有啥影响|会怎么走|有啥关系|影响大吗|该关注啥|重要吗|该怎么看|意味着啥|有关系吗|"
        r"怎么看|怎么映射|怎么拆|怎么跟|盯啥|会受影响|跟这事|啥关系|该盯)[？?]?$",
        t,
    ):
        notes.append("省略号位置不当，读者无法从标题读懂主题")
        return False, notes

    if len(t) > 32:
        notes.append(f"标题 {len(t)} 字，搜一搜列表易截断后语义残缺")
        return False, notes

    front = t[:15]
    if len(front.strip()) < 6:
        notes.append("标题前 15 字信息不足")
        return False, notes

    return True, notes


def _title_theme_tokens(title: str) -> set[str]:
    t = re.sub(r"[热点深评｜对A股怎么看？!？\s\"'「」""'']", "", title or "")
    tokens: set[str] = set()
    for n in (2, 3, 4):
        for i in range(len(t) - n + 1):
            chunk = t[i : i + n]
            if chunk.isascii():
                continue
            tokens.add(chunk)
    return tokens


def check_title_opening_aligned(
    title: str,
    body: str,
    *,
    kind: str,
) -> tuple[bool, list[str]]:
    """开篇与标题主题一致（禁止标题写 A、开篇大段写 B）。"""
    if kind not in {"hotspot", "news", "sector", "market"}:
        return True, []

    opening = ""
    for block in re.split(r"\n\s*\n", (body or "").strip()):
        b = block.strip()
        if (
            not b
            or b.startswith(">")
            or b.startswith("【说明】")
            or re.match(r"^[一二三四五六七八九十]、", b)
        ):
            continue
        opening = b[:280]
        break

    if not opening:
        return False, ["缺少与标题对照的开篇段"]

    tokens = _title_theme_tokens(title)
    if not tokens:
        return True, []

    hit = any(tok in opening for tok in tokens if len(tok) >= 2)
    if hit:
        return True, []

    # 热点深评：标题里「返港/航母」等至少一词应出现在开篇 280 字
    return False, ["开篇前 280 字与标题主题不一致（搜一搜路牌与正文首段须同题）"]


def check_hotspot_single_theme(body: str) -> tuple[bool, list[str]]:
    """hotspot 单主题长文：纯段落，禁止小标题与模板套话。"""
    from scripts.tools.wechat_mp_hotspot_article import hotspot_min_body_gate

    min_len = hotspot_min_body_gate(social=True)
    notes: list[str] = []
    plain = strip_hotspot_subheadings(body or "")

    if _HOTSPOT_LIST_PATTERN.search(plain):
        notes.append("正文像 10 条快讯清单，hotspot 须单主题深评")
        return False, notes

    if re.search(r"^>\s", plain, flags=re.MULTILINE):
        notes.append("含 `> ` 小标题，热点深评须纯段落")
        return False, notes

    if re.search(r"^#+\s", plain, flags=re.MULTILINE):
        notes.append("含 markdown 标题，热点深评须纯段落")
        return False, notes

    paras = [p for p in re.split(r"\n\n+", plain) if len(p.strip()) >= 40]
    if len(paras) < 5:
        notes.append("段落过少（至少 5 段、每段 40 字以上）")
        return False, notes

    for title in HOTSPOT_BANNED_SECTION_TITLES:
        if title in plain:
            notes.append(f"含模板节名「{title}」")
            return False, notes

    for label in HOTSPOT_RIGID_FIELD_LABELS:
        bare = label.rstrip("：:")
        if bare and bare in plain.replace(" ", ""):
            notes.append(f"含问卷体标签「{bare}」")
            return False, notes

    for phrase in HOTSPOT_BOILERPLATE_PHRASES:
        if phrase in plain:
            notes.append(f"含模板套话「{phrase}」")
            return False, notes

    if not re.search(r"\d", plain):
        notes.append("正文缺可核对数字（涨跌幅/家数/板位等）")
        return False, notes

    if len(plain.strip()) < min_len:
        notes.append(f"正文过短（<{min_len}字），热点深评须写满机制与验证点")
        return False, notes

    return True, notes


def check_hotspot_reader_meta(body: str) -> tuple[bool, list[str]]:
    """开篇禁止结构说明/阅读路径/编审预告。"""
    from scripts.tools.wechat_mp_hotspot_polish import _is_hotspot_meta_opening

    plain = (body or "").strip()
    if not plain:
        return True, []

    for part in re.split(r"\n\n+", plain):
        stripped = part.strip()
        if not stripped or stripped.startswith(">"):
            break
        if _is_hotspot_meta_opening(stripped):
            return False, ["开篇含阅读路径/结构说明等读者不需要的导语"]
        break

    return True, []


def check_hotspot_selection_leak(body: str) -> tuple[bool, list[str]]:
    """「为什么选这一题」禁止编审/候选过程外泄。"""
    lines = (body or "").splitlines()
    in_why = False
    why_text: list[str] = []

    for line in lines:
        bare = line.strip().lstrip("> ").strip()
        if bare == _WHY_SECTION:
            in_why = True
            continue
        if in_why and line.strip().startswith("> ") and bare != _WHY_SECTION:
            break
        if in_why and bare != _WHY_SECTION and line.strip():
            why_text.append(bare)

    merged = "".join(why_text)
    if not merged:
        return True, []

    if _TITLE_SELECTION_LEAK.search(merged):
        return False, ["「为什么选这一题」泄露候选/舍弃/同批素材等编审过程"]

    if re.search(r"相较[「\"']", merged):
        return False, ["「为什么选这一题」禁止相较其它标题/快讯"]

    return True, []


def check_reader_data_gap_meta(body: str) -> tuple[bool, list[str]]:
    from scripts.tools.wechat_mp_public import check_reader_data_gap_meta as _check

    return _check(body)


def sousou_notes_for_article(
    *,
    title: str,
    body: str,
    kind: str,
) -> list[str]:
    """汇总搜一搜规则未过项（供 eval dimension notes）。"""
    notes: list[str] = []
    ok, n = check_title_sousou_complete(title)
    if not ok:
        notes.extend(n)
    ok2, n2 = check_title_opening_aligned(title, body, kind=kind)
    if not ok2:
        notes.extend(n2)
    ok_data, n_data = check_reader_data_gap_meta(body)
    if not ok_data:
        notes.extend(n_data)
    if kind == "hotspot":
        ok3, n3 = check_hotspot_single_theme(body)
        if not ok3:
            notes.extend(n3)
        ok4, n4 = check_hotspot_selection_leak(body)
        if not ok4:
            notes.extend(n4)
        ok5, n5 = check_hotspot_reader_meta(body)
        if not ok5:
            notes.extend(n5)
    return notes


def sousou_title_score_adjust(title: str, *, base_score: int, max_score: int = 15) -> tuple[int, list[str]]:
    """标题维度：搜一搜完整度加减分。"""
    ok, notes = check_title_sousou_complete(title)
    if ok:
        return min(max_score, base_score + 3), notes
    return max(0, base_score - 5), notes


def sousou_body_score_adjust(
    body: str,
    *,
    title: str,
    kind: str,
    base_score: int,
    max_score: int = 25,
) -> tuple[int, list[str]]:
    notes: list[str] = []
    score = base_score

    ok_align, n_align = check_title_opening_aligned(title, body, kind=kind)
    if ok_align:
        score = min(max_score, score + 2)
    else:
        score = max(0, score - 4)
        notes.extend(n_align)

    if kind == "hotspot":
        ok_theme, n_theme = check_hotspot_single_theme(body)
        if ok_theme:
            score = min(max_score, score + 3)
        else:
            score = max(0, score - 5)
            notes.extend(n_theme)

        ok_leak, n_leak = check_hotspot_selection_leak(body)
        if not ok_leak:
            score = max(0, score - 4)
            notes.extend(n_leak)

        ok_meta, n_meta = check_hotspot_reader_meta(body)
        if not ok_meta:
            score = max(0, score - 4)
            notes.extend(n_meta)

    ok_data, n_data = check_reader_data_gap_meta(body)
    if ok_data:
        score = min(max_score, score + 2)
    else:
        score = max(0, score - 6)
        notes.extend(n_data)

    return score, notes
