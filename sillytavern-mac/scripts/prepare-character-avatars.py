#!/usr/bin/env python3
"""从封面 / 公版图裁切 ST 角色头像（512x512 PNG）。"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "characters"
OUT = ASSETS / "avatars"

# 来源说明见 assets/characters/SOURCES.md
SPECS = [
    {
        "out": "鬼瑶儿.png",
        "src": ASSETS / "vol3l.jpg",
        "box": (0.12, 0.02, 0.88, 0.58),  # 第三卷封面女主（官方插画）
    },
    {
        "out": "战天风.png",
        "src": ASSETS / "vol4l.jpg",
        "box": (0.18, 0.02, 0.82, 0.52),  # 第四卷封面男主
    },
    {
        "out": "苏晨.png",
        "src": ASSETS / "wiki-suchen-gentle.jpg",
        "box": (0.08, 0.0, 0.92, 0.55),  # 百美新詠叶小鸾（温婉闺秀气质）
    },
]


def crop_box(im: Image.Image, rel: tuple[float, float, float, float]) -> Image.Image:
    w, h = im.size
    l, t, r, b = rel
    x0, y0 = int(w * l), int(h * t)
    x1, y1 = int(w * r), int(h * b)
    side = min(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    x0 = max(0, cx - side // 2)
    y0 = max(0, cy - side // 2)
    x1 = min(w, x0 + side)
    y1 = min(h, y0 + side)
    if x1 - x0 < side:
        x0 = max(0, x1 - side)
    if y1 - y0 < side:
        y0 = max(0, y1 - side)
    return im.crop((x0, y0, x0 + side, y0 + side))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for spec in SPECS:
        src: Path = spec["src"]
        if not src.exists():
            raise SystemExit(f"缺少源图: {src}（先运行 scripts/fetch-character-avatars.sh）")
        im = Image.open(src).convert("RGB")
        portrait = crop_box(im, spec["box"]).resize((512, 512), Image.Resampling.LANCZOS)
        dest = OUT / spec["out"]
        portrait.save(dest, format="PNG", optimize=True)
        print(f"已写入 {dest} ({src.name})")


if __name__ == "__main__":
    main()
