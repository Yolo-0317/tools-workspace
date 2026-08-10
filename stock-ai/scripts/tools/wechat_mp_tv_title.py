#!/usr/bin/env python3
"""影视稿标题：参考豆瓣剧评/公号真人标题，32 字内口语化。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
REF_PATH = ROOT / "data/wechat_mp_tv_title_references.json"
TZ = ZoneInfo("Asia/Shanghai")
TITLE_MAX = 32

TV_TITLE_FORBIDDEN_RE = re.compile(
    r"又上热搜|这次吵|热搜在聊|值得现在补吗|先说结论：|双榜热议|热点深评"
)


@lru_cache(maxsize=1)
def _load_title_refs() -> dict[str, Any]:
    if not REF_PATH.is_file():
        return {"feel_words": [], "forbidden": []}
    return json.loads(REF_PATH.read_text(encoding="utf-8"))


def _clip(text: str, *, max_len: int = TITLE_MAX) -> str:
    from scripts.tools.wechat_mp_content import _clip_wechat_title

    return _clip_wechat_title(text, max_len=max_len)


def _douban_score(topic: dict[str, Any]) -> str | None:
    ratings = topic.get("ratings") or {}
    db = ratings.get("douban") if isinstance(ratings, dict) else None
    if not isinstance(db, dict):
        return None
    raw = db.get("score")
    if raw is None:
        return None
    try:
        val = float(raw)
        return str(int(val)) if val == int(val) else f"{val:.1f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return None


def _feel_word(topic: dict[str, Any], *, seed: int) -> str:
    words = list(_load_title_refs().get("feel_words") or [])
    if not words:
        words = ["比预期复杂一点", "比想象中稳", "后劲比开场大"]
    return words[seed % len(words)]


def _platform_kind(topic: dict[str, Any]) -> tuple[str, str]:
    p = str(topic.get("platform") or "").strip()
    if p.upper() == "HBO":
        plat = "HBO"
    elif "netflix" in p.lower():
        plat = "Netflix"
    elif "漫威" in p or "院线" in p:
        plat = "漫威"
    else:
        plat = p.split("/")[0].strip() or "这部"
    kind = "电影" if str(topic.get("type") or "") == "film" else "剧"
    return plat, kind


def build_tv_title_candidates(topic: dict[str, Any], *, now: datetime | None = None) -> list[str]:
    """按真人剧评标题套路生成候选（已考虑 32 字上限）。"""
    now = now or datetime.now(TZ)
    zh = str(topic.get("title_zh") or "").strip()
    if not zh:
        return ["这部片值得看吗？"]
    trend = str(topic.get("trend_title") or "").strip()
    plat, kind = _platform_kind(topic)
    score = _douban_score(topic)
    seed = now.toordinal() + int(topic.get("heat_score") or 0) + len(zh)
    feel = _feel_word(topic, seed=seed)
    hook = str(topic.get("hook") or "")[:14]

    out: list[str] = []

    # 定稿金样 / curated override 风格
    out.append(f"追完《{zh}》，爽完为什么没特痛快？")
    out.append(f"看完《{zh}》，{feel}")

    # 豆瓣剧评：豆瓣X.X，《片名》…
    if score:
        out.extend(
            [
                f"豆瓣{score}，《{zh}》到底好不好看？",
                f"豆瓣开分{score}，这部《{zh}》稳吗？",
                f"豆瓣{score}，《{zh}》值回票价吗？",
            ]
        )

    # 分派电影：开播即爆 / 平台+类型+争议
    if any(k in trend for k in ("好看吗", "值不值", "票房", "上映", "首映")):
        out.extend(
            [
                f"周末看了《{zh}》，出来想说两句",
                f"《{zh}》值不值得现在看？",
                f"首映看完《{zh}》，我站哪边？",
            ]
        )
    if any(k in (trend + hook) for k in ("烂片", "魔改", "编剧", "争议", "崩", "吵")):
        out.extend(
            [
                f"《{zh}》口碑两极，我捋一遍",
                f"补完《{zh}》，骂得冤枉吗？",
                f"{plat}这部{kind}，为什么观众吵起来了？",
            ]
        )
    if any(k in trend for k in ("开播", "上线", "定档", "回归", "续集", "第二季", "第三季")):
        out.append(f"开播就冲榜，《{zh}》后劲在哪？")
        out.append(f"《{zh}》回归，老粉还买账吗？")

    # 分派电影：片名+命题（压缩版）
    if kind == "电影" and score and float(score) >= 7.5:
        out.append(f"《{zh}》，这次漫威没失手？")
    if len(zh) <= 6:
        out.append(f"「{zh}」扒开了一层什么")

    # 通用（hook 过长或与片名重复则不用）
    short_hook = hook if hook and hook not in zh and len(hook) <= 10 else ""
    out.extend(
        [
            f"{plat}这部{kind}，{short_hook}？" if short_hook else f"{plat}这部{kind}，值得追吗？",
            f"周末适合开刷《{zh}》吗？",
        ]
    )

    # 去重 + 禁语 + 截断
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in out:
        t = _clip(raw.strip())
        if not t or t in seen:
            continue
        if TV_TITLE_FORBIDDEN_RE.search(t):
            continue
        seen.add(t)
        cleaned.append(t)
    return cleaned or [f"《{zh}》值得看吗？"]


def pick_tv_review_title(topic: dict[str, Any], *, now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    zh = str(topic.get("title_zh") or "").strip()
    candidates = build_tv_title_candidates(topic, now=now)
    score = _douban_score(topic)
    trend = str(topic.get("trend_title") or "")
    seed = now.toordinal() + int(topic.get("heat_score") or 0) + len(zh)

    tiers: list[list[str]] = []
    if score:
        tiers.append([c for c in candidates if c.startswith(f"豆瓣{score}") and zh in c])
    if any(k in trend for k in ("好看吗", "值不值", "票房", "首映")):
        tiers.append([c for c in candidates if "到底好不好看" in c or c.startswith("看完《")])
    if any(k in trend for k in ("烂片", "魔改", "编剧", "争议")):
        tiers.append([c for c in candidates if "口碑两极" in c or "骂得冤枉" in c or "吵起来" in c])
    tiers.append([c for c in candidates if c.startswith("追完《")])
    tiers.append([c for c in candidates if zh in c])

    for tier in tiers:
        if tier:
            return tier[seed % len(tier)]
    return candidates[0]


def title_reference_prompt_block() -> str:
    """DeepSeek 改标题时可选注入（规则优先）。"""
    data = _load_title_refs()
    lines = ["【标题参考·真人剧评】32 字内，口语，像追剧笔记："]
    for row in (data.get("samples") or [])[:6]:
        lines.append(f"- {row.get('title')}（{row.get('pattern')}）")
    forbidden = "、".join(data.get("forbidden") or [])
    if forbidden:
        lines.append(f"禁止：{forbidden}")
    return "\n".join(lines)
