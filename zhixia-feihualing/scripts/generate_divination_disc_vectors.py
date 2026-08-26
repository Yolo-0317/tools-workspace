#!/usr/bin/env python3
"""生成星轨六爻盘的确定性 SVG 母板与状态组件。"""

from __future__ import annotations

import argparse
import math
from pathlib import Path


CENTER = 512
RING_RADII = (440, 414, 354, 292, 224)
YAO_Y_BOTTOM_UP = (632, 584, 536, 488, 440, 392)
YAO_X1 = 390
YAO_X2 = 634
YIN_GAP = 34
SHANLEI_YI = ("yang", "yin", "yin", "yin", "yin", "yang")


DEFS = """
<defs>
  <radialGradient id="disc-fill" cx="50%" cy="46%" r="55%">
    <stop offset="0" stop-color="#173039" stop-opacity="0.42"/>
    <stop offset="0.62" stop-color="#0b1d25" stop-opacity="0.28"/>
    <stop offset="1" stop-color="#04090d" stop-opacity="0.08"/>
  </radialGradient>
  <linearGradient id="cyan-gold" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#8fdfe5"/>
    <stop offset="0.48" stop-color="#f3f1df"/>
    <stop offset="1" stop-color="#d6ad67"/>
  </linearGradient>
  <filter id="soft-glow" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur stdDeviation="4" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="line-glow" x="-50%" y="-100%" width="200%" height="300%">
    <feGaussianBlur stdDeviation="7" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
""".strip()


def point(radius: float, degrees: float) -> tuple[float, float]:
    angle = math.radians(degrees - 90)
    return CENTER + radius * math.cos(angle), CENTER + radius * math.sin(angle)


def svg_document(body: str, view_box: str = "0 0 1024 1024") -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{view_box}" fill="none">\n{DEFS}\n{body}\n</svg>\n'
    )


def ring_markup() -> str:
    rings = []
    for index, radius in enumerate(RING_RADII, start=1):
        opacity = 0.88 if index in (1, 3, 5) else 0.48
        width = 2.2 if index == 1 else 1.25
        rings.append(
            f'<circle data-role="disc-ring" data-index="{index}" '
            f'cx="{CENTER}" cy="{CENTER}" r="{radius}" '
            f'stroke="#d6ad67" stroke-opacity="{opacity}" stroke-width="{width}"/>'
        )
    for radius in (426, 390, 374, 336, 316, 270, 246):
        rings.append(
            f'<circle data-role="disc-ring" cx="{CENTER}" cy="{CENTER}" r="{radius}" '
            'stroke="#94d9de" stroke-opacity="0.20" stroke-width="1" '
            'stroke-dasharray="2 11"/>'
        )
    return "\n".join(rings)


def sector_markup() -> str:
    items = []
    for index in range(8):
        degrees = index * 45
        x1, y1 = point(224, degrees)
        x2, y2 = point(440, degrees)
        nx, ny = point(384, degrees)
        items.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            'stroke="#d6ad67" stroke-opacity="0.34" stroke-width="1"/>'
        )
        items.append(
            f'<circle cx="{nx:.2f}" cy="{ny:.2f}" r="19" fill="#071116" fill-opacity="0.72" '
            'stroke="#d6ad67" stroke-opacity="0.72" stroke-width="1.25"/>'
        )
        motif = []
        for offset in (-7, 0, 7):
            motif.append(
                f'<line x1="{nx - 9:.2f}" y1="{ny + offset:.2f}" '
                f'x2="{nx + 9:.2f}" y2="{ny + offset:.2f}" '
                'stroke="#d6ad67" stroke-opacity="0.70" stroke-width="1.2"/>'
            )
        items.extend(motif)
    return "\n".join(items)


def constellation_markup() -> str:
    items = []
    for sector in range(8):
        sector_points = []
        for local_index in range(6):
            degrees = sector * 45 - 17.5 + local_index * 7
            radius = 264 + ((sector * 53 + local_index * 37) % 142)
            x, y = point(radius, degrees)
            sector_points.append((x, y))
            size = 2.6 if (sector + local_index) % 5 == 0 else 1.35
            color = "#eef8ee" if (sector + local_index) % 4 else "#82d8df"
            items.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{size}" fill="{color}" '
                f'fill-opacity="{0.92 if size > 2 else 0.62}"/>'
            )
        path = " L ".join(f"{x:.2f} {y:.2f}" for x, y in sector_points)
        items.append(
            f'<path data-role="constellation-link" d="M {path}" '
            'stroke="#78cbd3" stroke-opacity="0.22" stroke-width="0.9"/>'
        )
    return "\n".join(items)


def empty_slots_markup() -> str:
    width = YAO_X2 - YAO_X1
    slots = []
    for position, y in enumerate(YAO_Y_BOTTOM_UP, start=1):
        slots.append(
            f'<rect data-role="empty-slot" data-position="{position}" '
            f'x="{YAO_X1}" y="{y - 7}" width="{width}" height="14" rx="7" '
            'fill="#9acbd0" fill-opacity="0.055" stroke="#b9d9d8" '
            'stroke-opacity="0.36" stroke-width="1.4"/>'
        )
    return "\n".join(slots)


def master_group() -> str:
    top_x, top_y = point(458, 0)
    return f"""
<g id="disc-root" data-role="disc-master">
  <circle cx="{CENTER}" cy="{CENTER}" r="452" fill="url(#disc-fill)"/>
  <circle cx="{CENTER}" cy="{CENTER}" r="446" stroke="#8bd9df" stroke-opacity="0.14" stroke-width="8" filter="url(#soft-glow)"/>
  {ring_markup()}
  {sector_markup()}
  {constellation_markup()}
  <circle cx="{CENTER}" cy="{CENTER}" r="204" fill="#02070a" fill-opacity="0.48" stroke="#d6ad67" stroke-opacity="0.26"/>
  {empty_slots_markup()}
  <path d="M {top_x:.2f} {top_y - 8:.2f} l 7 8 l -7 8 l -7 -8 z" fill="#b84738" fill-opacity="0.92"/>
</g>
""".strip()


def yao_markup(kind: str, position: int, y: int | None = None) -> str:
    if kind not in {"yang", "yin"}:
        raise ValueError(f"未知爻类型：{kind}")
    if position < 1 or position > 6:
        raise ValueError(f"爻位必须在 1—6：{position}")
    y = YAO_Y_BOTTOM_UP[position - 1] if y is None else y
    common = (
        f'data-role="filled-yao" data-kind="{kind}" data-position="{position}" '
        'stroke="url(#cyan-gold)" stroke-width="12" stroke-linecap="round" '
        'filter="url(#line-glow)"'
    )
    if kind == "yang":
        return f'<line {common} x1="{YAO_X1}" y1="{y}" x2="{YAO_X2}" y2="{y}"/>'
    middle = (YAO_X1 + YAO_X2) / 2
    left_end = middle - YIN_GAP / 2
    right_start = middle + YIN_GAP / 2
    return (
        f'<g {common}>'
        f'<line x1="{YAO_X1}" y1="{y}" x2="{left_end}" y2="{y}"/>'
        f'<line x1="{right_start}" y1="{y}" x2="{YAO_X2}" y2="{y}"/>'
        '</g>'
    )


def state_document(kinds: tuple[str, ...]) -> str:
    lines = "\n".join(yao_markup(kind, position) for position, kind in enumerate(kinds, start=1))
    return svg_document(f"{master_group()}\n<g data-role=\"yao-state\">{lines}</g>")


def component_document(kind: str) -> str:
    line = yao_markup(kind, 1, y=128)
    return svg_document(line, view_box="340 80 344 96")


def design_board_document() -> str:
    return svg_document(
        '<rect width="1920" height="1080" fill="#020507"/>'
        '<g transform="translate(20 64) scale(0.92)">'
        f'{master_group()}</g>',
        view_box="0 0 1920 1080",
    )


def build_assets(output_root: Path) -> None:
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    assets = {
        "disc-master.svg": svg_document(master_group()),
        "component-yang.svg": component_document("yang"),
        "component-yin.svg": component_document("yin"),
        "state-empty.svg": state_document(()),
        "state-partial-3.svg": state_document(("yang", "yin", "yin")),
        "state-shanlei-yi.svg": state_document(SHANLEI_YI),
        "design-board.svg": design_board_document(),
    }
    for filename, content in assets.items():
        (output_root / filename).write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    build_assets(args.output_root)


if __name__ == "__main__":
    main()
