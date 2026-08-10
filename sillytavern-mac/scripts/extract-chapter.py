#!/usr/bin/env python3
"""从 source/meinvjiangshan.txt 提取单章，供续写助手载入。"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "meinvjiangshan.txt"
OUT_DIR = ROOT / "data" / "chapter-context"
OUT_FILE = OUT_DIR / "current.json"

CN_DIGIT = "零一二三四五六七八九"
CN_UNIT = ("", "十", "百", "千")


def int_to_cn(n: int) -> str:
    if n <= 0:
        raise ValueError("chapter number must be positive")
    if n < 10:
        return CN_DIGIT[n]
    if n < 20:
        return "十" + (CN_DIGIT[n % 10] if n > 10 else "")
    if n < 100:
        tens, ones = divmod(n, 10)
        s = CN_DIGIT[tens] + "十"
        if ones:
            s += CN_DIGIT[ones]
        return s
    raise ValueError(f"chapter number too large: {n}")


def normalize_chapter_arg(arg: str) -> str:
    arg = arg.strip()
    if re.fullmatch(r"\d+", arg):
        return f"第{int_to_cn(int(arg))}章"
    if "章" not in arg:
        return f"第{arg}章"
    if not arg.startswith("第"):
        return f"第{arg}"
    return arg


def load_text() -> str:
    raw = SOURCE.read_bytes()
    for enc in ("gb18030", "gbk", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"无法解码: {SOURCE}")


def extract(title: str) -> dict:
    text = load_text()
    markers = list(re.finditer(r"正文\s*(第[一二三四五六七八九十百千零〇两]+章)", text))
    by_title = {m.group(1): i for i, m in enumerate(markers)}
    if title not in by_title:
        available = ", ".join(m.group(1) for m in markers[:8])
        raise SystemExit(f"未找到章节: {title}（示例: {available} …共 {len(markers)} 章）")

    i = by_title[title]
    start = markers[i].end()
    end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
    body = text[start:end].strip()
    if len(body) > 12000:
        raise SystemExit(
            f"{title} 过长（{len(body)} 字），可能源文件分章异常；请换一章或手动截取。"
        )
    tail_len = min(500, len(body))
    return {
        "title": title,
        "chars": len(body),
        "text": body,
        "tail": body[-tail_len:],
    }


def list_titles() -> list[str]:
    text = load_text()
    return re.findall(r"正文\s*(第[一二三四五六七八九十百千零〇两]+章)", text)


def load_next_hint(title: str) -> dict | None:
    hints_path = ROOT / "data" / "xuxie" / "next-chapter-hints.json"
    if not hints_path.exists():
        return None
    hints = json.loads(hints_path.read_text(encoding="utf-8"))
    return hints.get(title)


def main() -> None:
    parser = argparse.ArgumentParser(description="提取《美女江山一锅煮》单章")
    parser.add_argument("chapter", nargs="?", help="章名或序号，如 2 / 第二章 / 第十二")
    parser.add_argument("--list", action="store_true", help="列出全部章名")
    args = parser.parse_args()

    if args.list:
        for i, t in enumerate(list_titles(), 1):
            print(f"{i:2d}. {t}")
        return

    if not args.chapter:
        parser.error("需要章序或章名，或使用 --list")

    title = normalize_chapter_arg(args.chapter)
    data = extract(title)
    titles = list_titles()
    if title in titles:
        idx = titles.index(title)
        if idx + 1 < len(titles):
            data["next_title"] = titles[idx + 1]
    hint = load_next_hint(title)
    if hint:
        data["next_hint"] = hint

    # 与 data/xuxie/scenes 同步（破庙70 等）
    chapter_scene_map = {
        "第七十章": ("破庙70", "第七十章（破庙煮天锅虚影）", "破庙线"),
        "第六十九章": ("破庙69", "第六十九章（破庙前夜）", "破庙线"),
        "第七十一章": ("破庙71", "第七十一章（虚影剥衣）", "破庙线"),
    }
    if title in chapter_scene_map:
        sid, stitle, arc = chapter_scene_map[title]
        data["primary_id"] = sid
        scene_path = ROOT / "data" / "xuxie" / "scenes" / f"{sid}.json"
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        scene_payload = {
            "scene_id": sid,
            "title": stitle,
            "arc": arc,
            "source_ref": title,
            "chars": data["chars"],
            "text": data["text"],
            "tail": data["tail"],
            "next_title": data.get("next_title"),
            "next_hint": data.get("next_hint"),
        }
        scene_path.write_text(
            json.dumps(scene_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    elif OUT_FILE.exists():
        prev = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        if prev.get("primary_id"):
            data["primary_id"] = prev["primary_id"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    extra = ""
    if data.get("next_title"):
        extra = f"，下一章 {data['next_title']}"
        if hint:
            extra += "（已匹配走向摘要）"
    print(f"已提取 {title}（{data['chars']} 字）{extra} -> {OUT_FILE}")


if __name__ == "__main__":
    main()
