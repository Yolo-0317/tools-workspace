#!/usr/bin/env python3
"""创建或更新公众号贴图（newspic）草稿。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_codex_images import (
    CodexImageGenerationRequired,
    prepare_newspic_topic_images,
)
from scripts.tools.wechat_mp_newspic import (
    upsert_newspic_draft,
    validate_newspic_image_sources,
    validate_newspic_input,
)


def _resolve_newspic_images(args: argparse.Namespace) -> tuple[list[Path], Path]:
    topic = str(args.topic or "").strip()
    images = list(args.images or [])
    sources_path = args.image_sources
    if topic:
        if images or sources_path is not None:
            raise ValueError("--topic 自动取图不能同时使用 --images 或 --image-sources")
        prepared = prepare_newspic_topic_images(
            topic=topic,
            research_urls=list(args.research_url or []),
            target_count=int(args.image_count),
        )
        return list(prepared.image_paths), prepared.sources_path
    if bool(images) != bool(sources_path):
        raise ValueError("手工贴图模式必须同时提供 --images 与 --image-sources")
    if not images or sources_path is None:
        raise ValueError("必须提供 --topic，或同时提供 --images 与 --image-sources")
    return images, Path(sources_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="创建公众号贴图（图片消息）草稿")
    parser.add_argument("--title", required=True)
    parser.add_argument("--content", required=True, help="说明文字或 UTF-8 文本文件路径")
    parser.add_argument(
        "--topic",
        default="",
        help="同题报道图检索词；启用 Codex 自动素材模式",
    )
    parser.add_argument(
        "--research-url",
        action="append",
        default=[],
        help="优先取图的同题报道页，可重复传入",
    )
    parser.add_argument(
        "--image-count",
        type=int,
        choices=range(6, 10),
        default=6,
        metavar="6..9",
        help="自动素材模式的目标图片数，默认 6",
    )
    parser.add_argument("--images", nargs="+", type=Path)
    parser.add_argument(
        "--image-sources",
        type=Path,
        help="每张图的来源与原创补位原因 JSON",
    )
    parser.add_argument("--slot", default="newspic")
    parser.add_argument("--author", default="")
    parser.add_argument(
        "--watermark",
        default=None,
        help="右下角图片水印；virtual_lifestyle 槽位默认使用栀夏署名",
    )
    parser.add_argument("--force-reupload", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="完成取图、来源与内容校验，但不上传微信公众号",
    )
    args = parser.parse_args()
    content_path = Path(args.content)
    content = (
        content_path.read_text(encoding="utf-8").strip()
        if content_path.is_file()
        else args.content.strip()
    )
    watermark = (
        args.watermark
        if args.watermark is not None
        else ("栀夏 · ZHI XIA" if args.slot == "virtual_lifestyle" else "")
    )
    try:
        image_paths, image_sources_path = _resolve_newspic_images(args)
    except CodexImageGenerationRequired as exc:
        print(f"需要 Codex 原创补图: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    if args.dry_run:
        validate_newspic_input(
            title=args.title,
            content=content,
            image_paths=image_paths,
        )
        validate_newspic_image_sources(
            image_paths=image_paths,
            sources_path=image_sources_path,
        )
        print(f"DRY-RUN [{args.slot}] 图片 {len(image_paths)} 张 · {args.title}")
        for image_path in image_paths:
            print(image_path)
        print(f"来源清单: {image_sources_path}")
        return 0
    media_id, action = upsert_newspic_draft(
        slot_key=args.slot,
        title=args.title,
        content=content,
        image_paths=image_paths,
        image_sources_path=image_sources_path,
        author=args.author,
        force_reupload=args.force_reupload,
        watermark=watermark,
    )
    print(f"OK [{args.slot}] {action} media_id={media_id} · {args.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
