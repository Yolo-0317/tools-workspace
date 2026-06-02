#!/usr/bin/env python3
"""删除素材库中自动上传的黑底 default_cover（避免被误选为封面）。"""

from __future__ import annotations

import sys

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.tools.wechat_mp_client import (
    THUMB_CACHE,
    batchget_material_images,
    del_permanent_material,
    mp_configured,
)


def main() -> int:
    if not mp_configured():
        print("❌ 未配置 WECHAT_MP_APPID / WECHAT_MP_SECRET", file=sys.stderr)
        return 1

    items, err = batchget_material_images(count=20)
    if err:
        print(f"❌ {err}", file=sys.stderr)
        return 1

    targets = [
        it
        for it in items
        if "default_cover" in str(it.get("name") or "").lower()
    ]
    if not targets:
        print("素材库中无 default_cover，无需删除")
        return 0

    for it in targets:
        mid = str(it.get("media_id") or "")
        name = it.get("name")
        derr = del_permanent_material(mid)
        if derr:
            print(f"❌ 删除失败 {name}: {derr}", file=sys.stderr)
            return 1
        print(f"OK 已删除素材 {name} media_id={mid}")

    if THUMB_CACHE.is_file():
        THUMB_CACHE.unlink()
        print(f"OK 已清除本地缓存 {THUMB_CACHE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
