#!/usr/bin/env python3
"""从 manifest 下载 Pexels 正文插图到 assets/wechat_mp/inline/。"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
INLINE_ROOT = ROOT / "assets" / "wechat_mp" / "inline"
MANIFEST_PATH = INLINE_ROOT / "manifest.json"


def _pexels_url(photo_id: int, *, width: int = 900) -> str:
    return (
        f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg"
        f"?auto=compress&cs=tinysrgb&w={width}"
    )


def download_one(*, file: str, photo_id: int, width: int, force: bool) -> bool:
    dest = INLINE_ROOT / file
    if dest.is_file() and not force:
        return False
    url = _pexels_url(photo_id, width=width)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="下载公众号 inline 插图（Pexels）")
    parser.add_argument("--force", action="store_true", help="覆盖已存在文件")
    parser.add_argument("--limit", type=int, default=0, help="最多下载 N 张（0=全部）")
    args = parser.parse_args()

    if not MANIFEST_PATH.is_file():
        print(f"❌ 缺少 manifest: {MANIFEST_PATH}", file=sys.stderr)
        return 1

    meta = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    width = int(meta.get("width") or 900)
    rows = list(meta.get("figures") or [])
    if args.limit > 0:
        rows = rows[: args.limit]

    INLINE_ROOT.mkdir(parents=True, exist_ok=True)
    new_count = 0
    skip = 0
    fail = 0
    for row in rows:
        fname = str(row.get("file") or "").strip()
        pid = int(row.get("pexels_id") or 0)
        if not fname or pid <= 0:
            continue
        try:
            if download_one(file=fname, photo_id=pid, width=width, force=args.force):
                new_count += 1
                print(f"✅ {fname}")
            else:
                skip += 1
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"❌ {fname}: {exc}", file=sys.stderr)

    print(f"完成：新增/覆盖 {new_count}，跳过 {skip}，失败 {fail}，目录 {INLINE_ROOT}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
