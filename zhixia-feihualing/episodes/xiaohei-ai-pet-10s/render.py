"""Blur Xiaohei's lower belly and add timed subtitles while preserving source audio."""

import json
from math import hypot
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
EPISODE = Path(__file__).resolve().parent
SOURCE = ROOT / "assets/generated-video/xiaohei-ai-pet-10s-original.mp4"
OUTPUT = ROOT / "exports/xiaohei-ai-pet-privacy-subtitled-v06.mp4"
CUES = EPISODE / "subtitles.json"


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def validate_cues(cues):
    previous = 0.0
    for cue in cues:
        assert previous <= cue["start"] < cue["end"] <= 10.08
        previous = cue["end"]


def write_mask(path, center_y, radius_x, radius_y):
    width, height = 496, 864
    pixels = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            radius = hypot((x - 248) / radius_x, (y - center_y) / radius_y)
            alpha = max(0.0, min(1.0, (1.0 - radius) / 0.16))
            alpha = alpha * alpha * (3 - 2 * alpha)
            pixels[y * width + x] = round(alpha * 255)
    path.write_bytes(f"P5\n{width} {height}\n255\n".encode() + pixels)


def main():
    if OUTPUT.exists():
        raise FileExistsError(f"Output exists; make a new version: {OUTPUT}")
    cues = json.loads(CUES.read_text())
    validate_cues(cues)
    tags = json.loads(
        run("ffprobe", "-v", "error", "-show_entries", "format_tags=AIGC", "-of", "json", str(SOURCE))
    ).get("format", {}).get("tags", {})
    video_frames = int(
        run("ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(SOURCE)).strip()
    )
    with tempfile.TemporaryDirectory(prefix="xiaohei-render-") as work:
        work = Path(work)
        mask = work / "privacy-mask.pgm"
        transition_mask = work / "privacy-transition-mask.pgm"
        lower_mask = work / "privacy-lower-mask.pgm"
        write_mask(mask, 600, 87, 82)
        write_mask(transition_mask, 615, 80, 55)
        write_mask(lower_mask, 640, 75, 42)
        art = work / "subtitles"
        art.mkdir()
        env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(work / "clang"), SWIFT_MODULECACHE_PATH=str(work / "swift"))
        subprocess.run(["swift", str(EPISODE / "render_subtitles.swift"), str(CUES), str(art)], check=True, env=env)
        filters = [
            "[0:v]format=yuv420p,split=2[base][blur_input]",
            "[blur_input]boxblur=luma_radius=24:luma_power=5:chroma_radius=12:chroma_power=5,split=3[blur_main][blur_transition][blur_lower]",
            "[1:v]format=yuv420p[mask_main]",
            "[2:v]format=yuv420p[mask_transition]",
            "[3:v]format=yuv420p[mask_lower]",
            "[base][blur_main][mask_main]maskedmerge=enable='lt(t,2.6)+gte(t,6.2)'[stage1]",
            "[stage1][blur_transition][mask_transition]maskedmerge=enable='between(t,2.6,3.25)+between(t,5.8,6.2)'[stage2]",
            "[stage2][blur_lower][mask_lower]maskedmerge=enable='between(t,3.2,3.75)',"
            "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280[clean]",
        ]
        for index, cue in enumerate(cues, 4):
            prior = "clean" if index == 4 else f"caption{index - 1}"
            out = f"caption{index}"
            filters.append(
                f"[{prior}][{index}:v]overlay="
                f"enable='gte(t,{cue['start']})*lt(t,{cue['end']})':eof_action=pass[{out}]"
            )
        filters.append(f"[caption{len(cues) + 3}]trim=end_frame={video_frames}[out]")
        filter_graph = (
            ";".join(filters)
        )
        args = [
            "ffmpeg", "-v", "error", "-n", "-i", str(SOURCE),
            "-loop", "1", "-framerate", "24", "-i", str(mask),
            "-loop", "1", "-framerate", "24", "-i", str(transition_mask),
            "-loop", "1", "-framerate", "24", "-i", str(lower_mask),
        ]
        for cue in cues:
            args.extend(["-loop", "1", "-framerate", "24", "-i", str(art / (cue["id"] + ".png"))])
        args.extend([
            "-filter_complex", filter_graph, "-map", "[out]", "-map", "0:a:0",
            "-t", "10.08",
            "-c:v", "libx264", "-crf", "18", "-preset", "medium",
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
