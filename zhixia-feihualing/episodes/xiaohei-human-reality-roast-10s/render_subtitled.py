"""Mask Xiaohei's exposed lower belly and add timed captions at 1080x1920."""

import json
from math import hypot
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
EPISODE = Path(__file__).resolve().parent
SOURCE = ROOT / "assets/generated-video/xiaohei-human-reality-roast-10s-original.mp4"
OUTPUT = ROOT / "exports/xiaohei-human-reality-roast-subtitled-1080p-v01.mp4"
CUES = EPISODE / "subtitles.json"
RENDERER = EPISODE / "render_subtitle_cards.swift"


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def write_privacy_mask(path, center_x, center_y, radius_x, radius_y):
    width, height = 496, 864
    pixels = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            radius = hypot((x - center_x) / radius_x, (y - center_y) / radius_y)
            alpha = max(0.0, min(1.0, (1.0 - radius) / 0.24))
            alpha = alpha * alpha * (3 - 2 * alpha)
            pixels[y * width + x] = round(alpha * 255)
    path.write_bytes(f"P5\n{width} {height}\n255\n".encode() + pixels)


def main():
    if OUTPUT.exists():
        raise FileExistsError(f"Output exists: {OUTPUT}")
    cues = json.loads(CUES.read_text(encoding="utf-8"))
    previous = 0.0
    for cue in cues:
        assert previous <= cue["start"] < cue["end"] <= 10.08
        previous = cue["end"]
    frames = int(run("ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(SOURCE)).strip())
    tags = json.loads(run("ffprobe", "-v", "error", "-show_entries", "format_tags=AIGC", "-of", "json", str(SOURCE))).get("format", {}).get("tags", {})

    with tempfile.TemporaryDirectory(prefix="xiaohei-human-roast-") as temporary:
        work = Path(temporary)
        art = work / "cards"
        art.mkdir()
        mask = work / "privacy-mask.pgm"
        write_privacy_mask(mask, 253, 588, 92, 74)
        env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(work / "clang"), SWIFT_MODULECACHE_PATH=str(work / "swift"))
        subprocess.run(["swift", str(RENDERER), str(CUES), str(art)], check=True, env=env)

        filters = [
            "[0:v]format=yuv420p,split=2[original][blur_input]",
            "[blur_input]boxblur=luma_radius=24:luma_power=5:chroma_radius=12:chroma_power=5[blurred]",
            "[1:v]format=yuv420p[mask]",
            "[original][blurred][mask]maskedmerge=enable='lte(t,7.84)',scale=1080:1920:flags=lanczos:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[base]",
        ]
        for index, cue in enumerate(cues, 2):
            prior = "base" if index == 2 else f"caption{index - 1}"
            filters.append(
                f"[{prior}][{index}:v]overlay=x=0:y=0:"
                f"enable='gte(t,{cue['start']})*lt(t,{cue['end']})':eof_action=pass[caption{index}]"
            )
        filters.append(f"[caption{len(cues) + 1}]trim=end_frame={frames},format=yuv420p[out]")

        args = ["ffmpeg", "-v", "error", "-n", "-i", str(SOURCE), "-loop", "1", "-framerate", "24", "-i", str(mask)]
        for cue in cues:
            args.extend(["-loop", "1", "-framerate", "24", "-i", str(art / f"{cue['id']}.png")])
        args.extend([
            "-filter_complex", ";".join(filters), "-map", "[out]", "-map", "0:a:0",
            "-t", "10.08", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "copy", "-map_metadata", "0",
            "-movflags", "+faststart+use_metadata_tags",
        ])
        if "AIGC" in tags:
            args.extend(["-metadata", f"AIGC={tags['AIGC']}"])
        args.append(str(OUTPUT))
        subprocess.run(args, check=True)
    print(OUTPUT)


if __name__ == "__main__":
    main()
