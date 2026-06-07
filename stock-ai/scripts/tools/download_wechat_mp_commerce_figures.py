#!/usr/bin/env python3
"""从 inline-commerce manifest 下载带货插图（Unsplash / Pexels）。"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

ROOT = Path(__file__).resolve().parents[2]
COMMERCE_ROOT = ROOT / "assets" / "wechat_mp" / "inline-commerce"


def _pexels_url(photo_id: int, *, width: int = 900) -> str:
    return (
        f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg"
        f"?auto=compress&cs=tinysrgb&w={width}"
    )


def _unsplash_url(photo_key: str, *, width: int = 900) -> str:
    return (
        f"https://images.unsplash.com/photo-{photo_key}"
        f"?auto=format&fit=crop&w={width}&q=80"
    )


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    if len(data) < 8000:
        raise RuntimeError(f"文件过小（{len(data)} bytes），可能下载失败: {dest.name}")
    dest.write_bytes(data)


def download_row(*, row: dict, root: Path, width: int, force: bool) -> bool:
    fname = str(row.get("file") or "").strip()
    if not fname:
        return False
    dest = root / fname
    if dest.is_file() and not force:
        return False

    source = str(row.get("source") or "pexels").strip().lower()
    if source == "unsplash":
        key = str(row.get("unsplash_photo") or "").strip()
        if not key:
            raise ValueError(f"{fname}: 缺少 unsplash_photo")
        url = _unsplash_url(key, width=width)
    else:
        pid = int(row.get("pexels_id") or 0)
        if pid <= 0:
            raise ValueError(f"{fname}: 缺少 pexels_id")
        url = _pexels_url(pid, width=width)

    _download(url, dest)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="下载带货 inline-commerce 插图")
    parser.add_argument(
        "--vertical",
        default="home",
        help="子目录名，默认 home",
    )
    parser.add_argument("--force", action="store_true", help="覆盖已存在文件")
    parser.add_argument("--limit", type=int, default=0, help="最多下载 N 张（0=全部）")
    args = parser.parse_args()

    root = COMMERCE_ROOT / args.vertical
    manifest = root / "manifest.json"
    if not manifest.is_file():
        print(f"❌ 缺少 manifest: {manifest}", file=sys.stderr)
        return 1

    meta = json.loads(manifest.read_text(encoding="utf-8"))
    width = int(meta.get("width") or 900)
    rows = list(meta.get("figures") or [])
    if args.limit > 0:
        rows = rows[: args.limit]

    root.mkdir(parents=True, exist_ok=True)
    new_count = skip = fail = 0
    for row in rows:
        fname = str(row.get("file") or "").strip()
        try:
            if download_row(row=row, root=root, width=width, force=args.force):
                new_count += 1
                print(f"✅ {fname}")
            else:
                skip += 1
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"❌ {fname}: {exc}", file=sys.stderr)

    print(f"完成：新增/覆盖 {new_count}，跳过 {skip}，失败 {fail}，目录 {root}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
