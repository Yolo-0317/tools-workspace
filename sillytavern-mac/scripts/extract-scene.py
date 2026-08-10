#!/usr/bin/env python3
"""载入 data/xuxie/scenes/<场景>.json -> chapter-context/current.json"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENES_DIR = ROOT / "data" / "xuxie" / "scenes"
OUT_FILE = ROOT / "data" / "chapter-context" / "current.json"


def list_scenes() -> None:
    if not SCENES_DIR.exists():
        print("(尚无场景文件)")
        return
    for p in sorted(SCENES_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        sid = data.get("scene_id", p.stem)
        title = data.get("title", sid)
        arc = data.get("arc", "")
        chars = data.get("chars", len(data.get("text", "")))
        extra = f" · {arc}" if arc else ""
        print(f"  {sid:12s}  {title}（{chars} 字）{extra}")


def main() -> None:
    parser = argparse.ArgumentParser(description="载入续写助手预设场景")
    parser.add_argument("scene", nargs="?", help="场景 id，如 山谷绑打")
    parser.add_argument("--list", "-l", action="store_true", help="列出全部场景")
    args = parser.parse_args()

    if args.list:
        print("可用场景：")
        list_scenes()
        return

    if not args.scene:
        parser.error("需要场景 id，或使用 --list")

    scene_path = SCENES_DIR / f"{args.scene}.json"
    if not scene_path.exists():
        available = [p.stem for p in SCENES_DIR.glob("*.json")] if SCENES_DIR.exists() else []
        raise SystemExit(f"未找到场景: {args.scene}（可用: {', '.join(available) or '无'}）")

    data = json.loads(scene_path.read_text(encoding="utf-8"))
    text = data.get("text", "").strip()
    if not text:
        raise SystemExit(f"场景 {args.scene} 缺少 text")

    tail_len = min(500, len(text))
    out = {
        "title": data.get("title", args.scene),
        "scene_id": data.get("scene_id", args.scene),
        "arc": data.get("arc", ""),
        "source_ref": data.get("source_ref", ""),
        "chars": data.get("chars", len(text)),
        "text": text,
        "tail": data.get("tail", text[-tail_len:]),
        "next_title": data.get("next_title"),
        "next_hint": data.get("next_hint"),
    }
    if OUT_FILE.exists():
        prev = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        out["primary_id"] = prev.get("primary_id", "破庙70")
    else:
        out["primary_id"] = "破庙70"
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    extra = f" · {out['arc']}" if out.get("arc") else ""
    print(f"已载入场景 {args.scene}（{out['chars']} 字）{extra} -> {OUT_FILE}")


if __name__ == "__main__":
    main()
