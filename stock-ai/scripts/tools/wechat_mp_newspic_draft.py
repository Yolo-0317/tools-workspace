#!/usr/bin/env python3
"""创建或更新公众号贴图（newspic）草稿。"""
from __future__ import annotations
import argparse
from pathlib import Path
from scripts._bootstrap import ensure_repo_root_on_path
ensure_repo_root_on_path()
from scripts.tools.wechat_mp_newspic import upsert_newspic_draft

def main() -> int:
    parser = argparse.ArgumentParser(description="创建公众号贴图（图片消息）草稿")
    parser.add_argument("--title", required=True)
    parser.add_argument("--content", required=True, help="说明文字或 UTF-8 文本文件路径")
    parser.add_argument("--images", required=True, nargs="+", type=Path)
    parser.add_argument("--image-sources", required=True, type=Path, help="每张图的来源与原创补位原因 JSON")
    parser.add_argument("--slot", default="newspic")
    parser.add_argument("--author", default="")
    parser.add_argument("--watermark", default=None, help="右下角图片水印；virtual_lifestyle 槽位默认使用栀夏署名")
    parser.add_argument("--force-reupload", action="store_true")
    args = parser.parse_args()
    content_path = Path(args.content)
    content = content_path.read_text(encoding="utf-8").strip() if content_path.is_file() else args.content.strip()
    watermark = args.watermark if args.watermark is not None else ("栀夏 · ZHI XIA" if args.slot == "virtual_lifestyle" else "")
    media_id, action = upsert_newspic_draft(slot_key=args.slot, title=args.title, content=content, image_paths=args.images, image_sources_path=args.image_sources, author=args.author, force_reupload=args.force_reupload, watermark=watermark)
    print(f"OK [{args.slot}] {action} media_id={media_id} · {args.title}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
