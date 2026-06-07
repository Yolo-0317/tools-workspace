#!/usr/bin/env python3
"""market 成稿优化：结论开头、长段拆分、标题与盘面对齐。"""

from __future__ import annotations

import re
from typing import Literal

from scripts.tools.wechat_mp_market_edition import normalize_market_edition

MarketMood = Literal["index_up", "index_down", "index_up_breadth_weak", "index_down_breadth_strong", "unknown"]

OPENING_MIN_CHARS = 35
PARA_MAX_CHARS = 180  # market 专用于 opening；全稿默认见 wechat_mp_readability.para_max_chars()

_SECTION_MARKET = "> 盘面速览"
_MISLEADING_DOWN_WORDS = ("普跌", "全线下跌", "大跌", "暴跌", "弱势下行", "全线收跌")
_MISLEADING_UP_WORDS = ("普涨", "全线大涨", "暴涨", "全线飘红")


def _first_n_sentences(text: str, n: int = 2) -> tuple[str, str]:
    text = " ".join(text.split())
    if not text:
        return "", ""
    parts: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in "。！？":
            seg = buf.strip()
            if seg:
                parts.append(seg)
            buf = ""
    if buf.strip():
        parts.append(buf.strip())
    if not parts:
        return "", ""
    if len(parts) <= n:
        return "".join(parts), ""
    return "".join(parts[:n]), "".join(parts[n:])


def _has_opening_lede(body: str) -> bool:
    lines = [ln.strip() for ln in body.splitlines()]
    for i, line in enumerate(lines):
        if line.startswith("> 盘面") or line.lstrip(">").strip() == "盘面速览":
            if i == 0:
                return False
            prev = [ln for ln in lines[:i] if ln and not ln.startswith("[[fig:")]
            if not prev:
                return False
            blob = "".join(prev)
            return len(blob) >= OPENING_MIN_CHARS and bool(re.search(r"\d|涨|跌|指数", blob))
    return False


def _section_paragraph(body: str, section: str) -> str:
    lines = body.splitlines()
    collecting = False
    chunks: list[str] = []
    for line in lines:
        stripped = line.strip()
        bare = stripped.lstrip("> ").strip()
        if bare == section:
            collecting = True
            continue
        if collecting:
            if stripped.startswith("> ") and bare != section:
                break
            if stripped.startswith("[[fig:"):
                continue
            if stripped:
                chunks.append(stripped)
            elif chunks:
                break
    return " ".join(chunks)


def _synthesize_lede(market_para: str, *, edition: str) -> str:
    ed = normalize_market_edition(edition)
    idx = re.search(r"上证[^。；！？]{0,40}", market_para)
    breadth = re.search(r"(?:涨|上涨)\s*(\d+)\s*家[^。；！？]{0,20}(?:跌|下跌)\s*(\d+)\s*家", market_para)
    idx_bit = idx.group(0) if idx else "主要指数分化"
    if breadth:
        up_n, down_n = int(breadth.group(1)), int(breadth.group(2))
        if down_n > up_n * 1.2:
            struct = "指数与个股未共振，跌多涨少"
        elif up_n > down_n * 1.2:
            struct = "广度尚可，个股与指数同向"
        else:
            struct = "涨跌家数接近，结构偏震荡"
    else:
        struct = "先看指数与涨跌家数是否同向"
    if ed == "pre":
        tail = "开盘前宜先定结构，再谈方向。"
    elif ed == "midday":
        tail = "半日走完，午后重点看能否延续或修复。"
    else:
        tail = "收盘后先看结构，再定明日验证点。"
    return f"{idx_bit}；{struct}。{tail}"


def inject_market_opening_lede(body: str, *, edition: str | None = None) -> str:
    """在 `> 盘面速览` 前插入 2 句结论段（若无）。"""
    if _has_opening_lede(body):
        return body
    ed = normalize_market_edition(edition) if edition else "close"
    market_para = _section_paragraph(body, "盘面速览")
    if not market_para:
        return body

    lede, remainder = _first_n_sentences(market_para, 2)
    if len(lede) < OPENING_MIN_CHARS:
        lede = _synthesize_lede(market_para, edition=ed)
        remainder = market_para

    lines = body.splitlines()
    out: list[str] = []
    i = 0
    inserted = False
    while i < len(lines):
        line = lines[i]
        bare = line.strip().lstrip("> ").strip()
        if bare == "盘面速览" and not inserted:
            out.append(lede)
            out.append("")
            out.append(line)
            inserted = True
            i += 1
            if remainder.strip() and remainder.strip() != lede.strip():
                # 跳过原「盘面速览」下第一段，改用 remainder（去掉与 lede 重复部分）
                while i < len(lines):
                    s = lines[i].strip()
                    if not s:
                        i += 1
                        continue
                    if s.startswith("> ") or s.startswith("[[fig:"):
                        break
                    i += 1
                out.append(remainder.strip())
                out.append("")
            continue
        out.append(line)
        i += 1

    if not inserted:
        return body
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def split_long_paragraphs(body: str, *, max_chars: int = PARA_MAX_CHARS) -> str:
    """移动端：超长段在句号处拆段（market 默认 180；其它稿型用 readability 模块）。"""
    from scripts.tools.wechat_mp_readability import split_long_paragraphs as _split

    return _split(body, max_chars=max_chars)


def detect_market_mood(body: str) -> MarketMood:
    blob = _section_paragraph(body, "盘面速览") or body[:800]
    index_up = bool(re.search(r"上证[^。\n]{0,30}涨\d|上证指数[^。\n]{0,20}涨", blob))
    index_down = bool(re.search(r"上证[^。\n]{0,30}跌\d|上证指数[^。\n]{0,20}跌", blob))
    m = re.search(
        r"(?:上涨|涨)\s*(\d+)\s*家[^。\n]{0,30}(?:下跌|跌)\s*(\d+)\s*家",
        blob,
    )
    if not m:
        m = re.search(
            r"(?:下跌|跌)\s*(\d+)\s*家[^。\n]{0,30}(?:上涨|涨)\s*(\d+)\s*家",
            blob,
        )
        if m:
            down_n, up_n = int(m.group(1)), int(m.group(2))
        else:
            m = re.search(r"(\d+)\s*:\s*(\d+)", blob)
            if m:
                up_n, down_n = int(m.group(1)), int(m.group(2))
            else:
                up_n = down_n = 0
    else:
        up_n, down_n = int(m.group(1)), int(m.group(2))

    if index_up and down_n > up_n * 1.15:
        return "index_up_breadth_weak"
    if index_down and up_n > down_n * 1.15:
        return "index_down_breadth_strong"
    if index_up:
        return "index_up"
    if index_down:
        return "index_down"
    return "unknown"


def align_market_title_mood(title: str, body: str) -> str:
    """标题情绪词与盘面速览数字一致，避免「普跌」但指数收涨。"""
    mood = detect_market_mood(body)
    t = (title or "").strip()
    if not t:
        return t

    if mood in {"index_up", "index_up_breadth_weak"}:
        for w in _MISLEADING_DOWN_WORDS:
            if w in t:
                t = t.replace("普跌格局", "指数涨、个股跌").replace("普跌", "指数涨、个股跌")
                t = t.replace("全线下跌", "结构分化").replace("大跌", "结构分化")
                break
    if mood in {"index_down", "index_down_breadth_strong"}:
        for w in _MISLEADING_UP_WORDS:
            if w in t:
                t = t.replace("普涨", "指数承压").replace("暴涨", "波动加大")
                break
    if mood == "index_up_breadth_weak" and "涨少跌多" not in t and "个股跌" not in t:
        # 可选：不强制改标题，仅修正误导词
        pass
    return t[:32]


def _finalize_market_read_hooks(body: str, *, edition: str | None = None) -> str:
    from scripts.tools.wechat_mp_market_edition import normalize_market_edition
    from scripts.tools.wechat_mp_read_hooks import (
        append_to_section_end,
        has_reader_hook,
        insert_after_section_title,
        insert_section_bridges,
        read_hooks_enabled,
        normalize_hook_spacing,
    )
    from scripts.tools.wechat_mp_prose import MARKET_SECTION_TITLES

    if not read_hooks_enabled("market"):
        return body

    ed = normalize_market_edition(edition) if edition else "close"
    s_market, s_outer, s_struct = MARKET_SECTION_TITLES
    ed_hint = {"pre": "盘前", "midday": "午间", "close": "收盘"}.get(ed, "收盘")

    text = body
    blob = _section_paragraph(text, s_market)
    if not has_reader_hook(blob) and not has_reader_hook(text[:400]):
        path = (
            f"本篇{ed_hint}复盘按「盘面→外围→结构」展开；"
            f"读完「结构判断」，才定明日该盯指数还是盯个股广度。"
        )
        text = insert_after_section_title(text, s_market, ["", path, ""])

    from scripts.tools.wechat_mp_read_hooks import BRIDGE_MARK

    text = insert_section_bridges(
        text,
        {
            s_outer: f"{BRIDGE_MARK}外围与资金怎么定价，决定盘面是不是「假强」。",
            s_struct: f"{BRIDGE_MARK}结构判断里，哪条验证点能证伪今天的盘面叙事。",
        },
    )
    closing = (
        "若次日指数与涨跌家数背离加剧，结构分化就算确认；"
        "反之若广度修复，才谈得上情绪回暖——这是明日盘中的硬验证。"
    )
    text = append_to_section_end(text, s_struct, closing)
    return normalize_hook_spacing(text)


def finalize_market_body(body: str, *, edition: str | None = None) -> str:
    """market 成稿后处理链：结构分段 → 结论开头 → 长段拆分 → 完读钩子。"""
    from scripts.tools.wechat_mp_prose import reflow_market_structure_section

    text = reflow_market_structure_section(body)
    text = inject_market_opening_lede(text, edition=edition)
    text = split_long_paragraphs(text)
    text = _finalize_market_read_hooks(text, edition=edition)
    return text.strip()
