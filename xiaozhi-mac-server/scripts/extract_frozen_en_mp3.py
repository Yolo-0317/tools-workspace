#!/usr/bin/env python3
"""Download Frozen BD from Quark, then extract English audio to local MP3.

Uses quark-drive download (faster/resumable) then local ffmpeg.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.quark_client import QuarkClient  # noqa: E402

JOBS = [
    {
        "out": "01-冰雪奇缘1-英文音轨.mp3",
        "fid": "~1JZVU6Cs9ml8MkVLKkw_0lm7HeKNZLgl3oe8d9J94cajdmzgz1zlUVG_Y1aOnK8p20RGzFhgQFzWY-wH5q7Htfs",
        "filename": "冰雪奇缘.BD.1080p.国粤英三语双字.mkv",
        "audio_map": "0:a:m:language:eng",
        "size": 2023428590,
    },
    {
        "out": "02-冰雪奇缘2-英文音轨.mp3",
        "fid": "~10SxzD1-ore4YOc8fBQ1txw1h_xSPgQCItwuqqseWO4MrrP3O40Z9dddz9_mQeW2fdwPw9XBJ4OHYswSdLRCASc",
        "filename": "冰雪奇缘2.BD1080p.国粤英三.mp4",
        "audio_map": "0:a:2",
        "size": 3125880315,
    },
]


def download_fid(
    client: QuarkClient, fid: str, out_dir: Path, expected_name: str, expected_size: int
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = out_dir / expected_name
    if existing.is_file() and existing.stat().st_size >= expected_size * 0.98:
        print(f"reuse video: {existing} ({existing.stat().st_size} bytes)")
        return existing

    src = client.resolve_stream_source(
        fid, filename_hint=expected_name, size_hint=expected_size
    )
    dest = out_dir / (src.filename or expected_name)
    # Multi-connection resume; Quark CDN needs Cookie.
    if subprocess.run(["which", "aria2c"], capture_output=True).returncode == 0:
        cmd = [
            "aria2c",
            "-c",
            "-x",
            "16",
            "-s",
            "16",
            "-k",
            "1M",
            "--file-allocation=none",
            f"--header=Cookie: {src.cookie}",
            "-d",
            str(out_dir),
            "-o",
            dest.name,
            src.download_url,
        ]
        print(f"aria2c download → {dest.name} (expect ~{expected_size // (1024*1024)} MiB)")
    else:
        cmd = [
            "curl",
            "-L",
            "--fail",
            "--retry",
            "5",
            "--retry-delay",
            "2",
            "-C",
            "-",
            "-H",
            f"Cookie: {src.cookie}",
            "-o",
            str(dest),
            "--progress-bar",
            src.download_url,
        ]
        print(f"curl download → {dest.name} (expect ~{expected_size // (1024*1024)} MiB)")
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size < 1_000_000:
        raise SystemExit(f"download failed for {expected_name} (code={proc.returncode})")
    print(f"downloaded: {dest} ({dest.stat().st_size} bytes)")
    return dest


def extract_mp3(video: Path, dest: Path, audio_map: str, bitrate: str, force: bool) -> None:
    if dest.exists() and dest.stat().st_size > 1_000_000 and not force:
        print(f"skip mp3: {dest}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i",
        str(video),
        "-map",
        audio_map,
        "-vn",
        "-acodec",
        "libmp3lame",
        "-ab",
        bitrate,
        str(dest),
    ]
    print("extract:", dest.name)
    t0 = time.time()
    subprocess.run(cmd, check=True)
    print(f"done: {dest} ({dest.stat().st_size} bytes) in {time.time() - t0:.0f}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "exports" / "frozen_en_mp3",
    )
    ap.add_argument(
        "--video-dir",
        type=Path,
        default=ROOT / "data" / "exports" / "frozen_bd_cache",
    )
    ap.add_argument("--bitrate", default="160k")
    ap.add_argument("--only", type=int, choices=(1, 2))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--skip-download", action="store_true", help="Only extract if video already local")
    args = ap.parse_args()

    client = QuarkClient.from_env(workspace_root=ROOT.parent)
    if client is None:
        raise SystemExit("QuarkClient.from_env failed (CLI / hermes config missing)")

    jobs = JOBS if not args.only else [JOBS[args.only - 1]]
    for job in jobs:
        if args.skip_download:
            video = args.video_dir / job["filename"]
            if not video.is_file():
                raise SystemExit(f"missing video: {video}")
        else:
            video = download_fid(
                client, job["fid"], args.video_dir, job["filename"], job["size"]
            )
        extract_mp3(video, args.out_dir / job["out"], job["audio_map"], args.bitrate, args.force)

    readme = args.out_dir / "README.txt"
    readme.write_text(
        "冰雪奇缘电影英文音轨（预抽 MP3）\n"
        "================================\n"
        "上传建议：夸克 玥玥/冰雪奇缘英文音轨/\n"
        "  01-冰雪奇缘1-英文音轨.mp3\n"
        "  02-冰雪奇缘2-英文音轨.mp3\n"
        "\n"
        "上传完成后告诉 Agent，再改 frozen_movie 索引指向新 fid。\n"
        f"视频缓存（可删）：{args.video_dir}\n",
        encoding="utf-8",
    )
    print(f"README: {readme}")


if __name__ == "__main__":
    main()
