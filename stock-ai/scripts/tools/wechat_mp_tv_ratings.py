#!/usr/bin/env python3
"""影视评分：正文竖排文字（多平台，非页面截图）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
INLINE_TV_ROOT = ROOT / "assets" / "wechat_mp" / "inline-tv"

RATING_CARD_NAME = "ratings-card.jpg"

# 展示顺序
_RATING_SOURCE_ORDER = ("douban", "imdb", "rotten_tomatoes", "metacritic", "tmdb")


def _rating_block(topic: dict[str, Any]) -> dict[str, Any] | None:
    raw = topic.get("ratings")
    return raw if isinstance(raw, dict) else None


def _row(name: str, value: str, note: str = "") -> tuple[str, str, str]:
    return name.strip(), value.strip(), note.strip()


def collect_rating_rows(ratings: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(平台名, 分值, 备注) 列表，供竖排渲染。"""
    rows: list[tuple[str, str, str]] = []

    douban = ratings.get("douban") if isinstance(ratings.get("douban"), dict) else {}
    if douban.get("score") is not None:
        note = str(douban.get("label") or "").strip()
        votes = str(douban.get("votes") or "").strip()
        if votes:
            note = f"{note}，{votes}".strip("，") if note else votes
        rows.append(_row("豆瓣", str(douban["score"]), note))

    imdb = ratings.get("imdb") if isinstance(ratings.get("imdb"), dict) else {}
    if imdb.get("score") is not None:
        rows.append(_row("IMDb", str(imdb["score"]), str(imdb.get("label") or "").strip()))

    rt = ratings.get("rotten_tomatoes") if isinstance(ratings.get("rotten_tomatoes"), dict) else {}
    if rt.get("critics") is not None:
        rows.append(
            _row(
                "烂番茄",
                f"{rt.get('critics')}%",
                str(rt.get("label") or "影评人新鲜度").strip(),
            )
        )
    if rt.get("audience") is not None:
        rows.append(
            _row(
                "烂番茄观众",
                f"{rt.get('audience')}%",
                str(rt.get("audience_label") or "观众新鲜度").strip(),
            )
        )

    mc = ratings.get("metacritic") if isinstance(ratings.get("metacritic"), dict) else {}
    if mc.get("score") is not None:
        rows.append(_row("Metacritic", str(mc["score"]), str(mc.get("label") or "metascore").strip()))

    tmdb = ratings.get("tmdb") if isinstance(ratings.get("tmdb"), dict) else {}
    if tmdb.get("score") is not None:
        note = str(tmdb.get("label") or "").strip()
        votes = str(tmdb.get("votes") or "").strip()
        if votes and note:
            note = votes if note in votes else f"{note}，{votes}"
        elif votes:
            note = votes
        rows.append(_row("TMDB", str(tmdb["score"]), note))

    extra = ratings.get("extra")
    if isinstance(extra, list):
        for item in extra:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            value = str(item.get("value") or "").strip()
            if name and value:
                rows.append(_row(name, value, str(item.get("note") or "").strip()))

    return rows


def format_ratings_lines(topic: dict[str, Any]) -> tuple[list[str], str]:
    """竖排 bullet 行 + 可选脚注（分行注入，避免混进同一段落）。"""
    ratings = _rating_block(topic)
    if not ratings:
        return [], ""
    rows = collect_rating_rows(ratings)
    if not rows:
        return [], ""
    lines: list[str] = []
    for name, value, note in rows:
        chunk = f"· {name} {value}"
        if note:
            chunk += f"（{note}）"
        lines.append(chunk)
    as_of = str(topic.get("ratings_as_of") or ratings.get("as_of") or "").strip()
    foot = f"（截至 {as_of}，公开页面整理）" if as_of else ""
    return lines, foot


def format_ratings_text(topic: dict[str, Any]) -> str:
    """兼容旧调用：多行竖排文本。"""
    bullets, foot = format_ratings_lines(topic)
    parts = bullets + ([foot] if foot else [])
    return "\n".join(parts)


def rating_card_path(slug: str) -> Path:
    return INLINE_TV_ROOT / slug / RATING_CARD_NAME


def generate_rating_card(topic: dict[str, Any], *, path: Path | None = None) -> Path | None:
    """保留：自制评分图（正文已改纯文字，封面/备查仍可用）。"""
    ratings = _rating_block(topic)
    if not ratings:
        return None

    slug = str(topic.get("cover_slug") or "tv").strip().lower()
    if slug == "euphoria" or str(topic.get("title_en") or "").lower() == "euphoria":
        slug = "euphoria"
    out = path or rating_card_path(slug)
    out.parent.mkdir(parents=True, exist_ok=True)

    from PIL import Image, ImageDraw, ImageFont

    rows = collect_rating_rows(ratings)
    if not rows:
        return None

    w = 900
    row_h = 72
    h = 80 + len(rows) * row_h + 48
    img = Image.new("RGB", (w, h), (252, 252, 254))
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 28)
        name_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 22)
        score_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
        note_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 16)
    except OSError:
        title_font = name_font = score_font = note_font = ImageFont.load_default()

    zh = str(topic.get("title_zh") or topic.get("title_en") or "剧集")
    draw.text((40, 24), f"《{zh}》公开评分", fill=(30, 30, 35), font=title_font)
    y = 72
    for i, (name, value, note) in enumerate(rows):
        bg = (245, 248, 252) if i % 2 == 0 else (252, 252, 254)
        draw.rounded_rectangle((40, y, w - 40, y + row_h - 8), radius=10, fill=bg)
        draw.text((56, y + 10), name, fill=(60, 60, 70), font=name_font)
        draw.text((200, y + 6), value, fill=(20, 20, 28), font=score_font)
        if note:
            draw.text((420, y + 18), note, fill=(110, 110, 120), font=note_font)
        y += row_h

    as_of = str(topic.get("ratings_as_of") or ratings.get("as_of") or "").strip()
    foot = "自制信息图 · 公开页面整理"
    if as_of:
        foot = f"{foot} · 截至 {as_of}"
    draw.text((40, h - 32), foot, fill=(140, 140, 150), font=note_font)
    img.save(out, format="JPEG", quality=92, optimize=True)
    return out


def ensure_rating_card(topic: dict[str, Any], *, force: bool = False) -> Path | None:
    slug = str(topic.get("cover_slug") or "tv").strip().lower()
    if slug == "euphoria" or str(topic.get("title_en") or "").lower() == "euphoria":
        slug = "euphoria"
    dest = rating_card_path(slug)
    if dest.is_file() and not force and dest.stat().st_size > 3000:
        if not _rating_block(topic):
            return None
        return dest
    return generate_rating_card(topic, path=dest)
