#!/usr/bin/env python3
"""列出公众平台素材库图片，便于配置 WECHAT_MP_THUMB_MEDIA_ID。"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import batchget_material_images, mp_configured

TZ = ZoneInfo("Asia/Shanghai")


def main() -> int:
    parser = argparse.ArgumentParser(description="列出微信素材库图片")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()

    if not mp_configured():
        print("❌ 未配置 WECHAT_MP_APPID / WECHAT_MP_SECRET", file=sys.stderr)
        return 1

    from scripts.tools.wechat_mp_client import _list_all_material_images

    if args.offset == 0 and args.count >= 20:
        items = _list_all_material_images(max_items=max(args.count, 500))
        err = None
        items = items[args.offset : args.offset + args.count] if args.count else items
    else:
        items, err = batchget_material_images(offset=args.offset, count=args.count)
    if err:
        print(f"❌ {err}", file=sys.stderr)
        return 1
    if not items:
        print("素材库暂无图片，请在 mp.weixin.qq.com → 素材管理 上传")
        return 0

    print(f"共 {len(items)} 条（offset={args.offset}）\n")
    for i, it in enumerate(items):
        ts = int(it.get("update_time") or 0)
        when = datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d %H:%M") if ts else "-"
        from scripts.tools.wechat_mp_client import _material_display_name

        print(f"[{i}] {_material_display_name(it)}")
        print(f"    media_id={it.get('media_id')}")
        print(f"    updated={when}")
        if it.get("url"):
            print(f"    url={it.get('url')}")
        print()
    print("在 .env 设置例如：")
    print("  WECHAT_MP_THUMB_MEDIA_ID=<上面 media_id>")
    print("或 WECHAT_MP_THUMB_INDEX=0  # 按本次列表下标")
    print("或 WECHAT_MP_THUMB_NAME=封面关键词  # 匹配 name 子串")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
