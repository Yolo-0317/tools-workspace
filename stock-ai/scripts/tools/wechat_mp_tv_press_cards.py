#!/usr/bin/env python3
"""剧评用舆情卡片：X 讨论截图风格（公开帖文整理，非官方界面）。"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

_CJK_FONT_CANDIDATES: tuple[tuple[str, int], ...] = (
    ("/System/Library/Fonts/STHeiti Light.ttc", 0),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 0),
    ("/Library/Fonts/Arial Unicode.ttf", 0),
    ("/System/Library/Fonts/PingFang.ttc", 0),
)


def _load_font(size: int, *, latin: bool = False) -> Any:
    from PIL import ImageFont

    if latin:
        for path in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    for path, index in _CJK_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


def generate_x_discussion_card(
    path: Path,
    *,
    display_name: str,
    handle: str,
    body: str,
    meta: str = "",
    width: int = 900,
) -> Path:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    name_font = _load_font(22)
    handle_font = _load_font(18)
    body_font = _load_font(20)
    meta_font = _load_font(16)
    badge_font = _load_font(20, latin=True)

    margin = 28
    wrap = 38 if any(ord(c) > 127 for c in body) else 52
    lines = textwrap.wrap(body.strip(), width=wrap) or [body.strip()]
    line_h = 30
    body_h = len(lines) * line_h
    height = margin * 2 + 56 + body_h + (24 if meta else 0) + 18

    img = Image.new("RGB", (width, height), (21, 32, 43))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=16, outline=(56, 68, 77), width=2)

    avatar_x, avatar_y = margin, margin
    draw.ellipse((avatar_x, avatar_y, avatar_x + 44, avatar_y + 44), fill=(113, 118, 123))
    draw.text((width - margin - 18, margin + 8), "X", fill=(231, 233, 234), font=badge_font)

    draw.text((avatar_x + 56, margin + 2), display_name[:24], fill=(231, 233, 234), font=name_font)
    draw.text((avatar_x + 56, margin + 28), handle[:28], fill=(113, 118, 123), font=handle_font)

    y = margin + 58
    for line in lines:
        draw.text((margin, y), line, fill=(231, 233, 234), font=body_font)
        y += line_h
    if meta:
        draw.text((margin, y + 4), meta[:60], fill=(113, 118, 123), font=meta_font)

    img.save(path, format="JPEG", quality=90, optimize=True)
    return path


def ensure_x_cards(spec: dict[str, Any], out_dir: Path) -> None:
    cards = spec.get("x_cards") if isinstance(spec.get("x_cards"), list) else []
    for item in cards:
        if not isinstance(item, dict):
            continue
        fname = str(item.get("file") or "").strip()
        if not fname:
            continue
        dest = out_dir / fname
        generate_x_discussion_card(
            dest,
            display_name=str(item.get("display_name") or "X 网友"),
            handle=str(item.get("handle") or "@user"),
            body=str(item.get("body") or ""),
            meta=str(item.get("meta") or "公开讨论 · 2026-06"),
        )
