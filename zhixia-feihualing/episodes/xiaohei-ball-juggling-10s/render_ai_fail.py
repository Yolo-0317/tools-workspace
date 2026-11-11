"""Package the owner-provided ball clip in Xiaohei's AI-blooper layout."""

import json
from math import hypot
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
EPISODE = Path(__file__).resolve().parent
SOURCE = ROOT / "assets/generated-video/xiaohei-ball-juggling-10s-original.mp4"
OUTPUT = ROOT / "exports/xiaohei-ball-juggling-ai-fail-1080p-v04.mp4"
CUES = EPISODE / "subtitles-ai-fail-v01.json"
CARD_RENDERER = ROOT / "episodes/xiaohei-emotional-stability-10s/render_ai_fail_cards.swift"


def write_mask(path, center_y):
    width, height = 496, 864
    pixels = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            radius = hypot((x - 325) / 23, (y - center_y) / 26)
            alpha = max(0.0, min(1.0, (1.0 - radius) / 0.20))
            alpha = alpha * alpha * (3 - 2 * alpha)
            pixels[y * width + x] = round(alpha * 255)
    path.write_bytes(f"P5\n{width} {height}\n255\n".encode() + pixels)


def main():
    if OUTPUT.exists():
        raise FileExistsError(f"Output exists; use a new version: {OUTPUT}")
    cues = json.loads(CUES.read_text())
    previous = 0.0
    for cue in cues:
        assert previous <= cue["start"] < cue["end"] <= 10.08
        previous = cue["end"]
    assert abs(previous - 10.08) < 0.001

    with tempfile.TemporaryDirectory(prefix="xiaohei-ball-ai-fail-") as temporary:
        work = Path(temporary)
        art = work / "cards"
        art.mkdir()
        mask_low = work / "privacy-low.pgm"
        mask_high = work / "privacy-high.pgm"
        write_mask(mask_low, 300)
        write_mask(mask_high, 245)
        env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(work / "clang"), SWIFT_MODULECACHE_PATH=str(work / "swift"))
        subprocess.run(["swift", str(CARD_RENDERER), str(CUES), str(art)], check=True, env=env)

        filters = [
            "[0:v]format=yuv420p,split=2[original][blur_input]",
            "[blur_input]boxblur=luma_radius=16:luma_power=3:chroma_radius=8:chroma_power=3,split=2[blur_low][blur_high]",
            "[1:v]format=yuv420p[mask_low]",
            "[2:v]format=yuv420p[mask_high]",
            "[original][blur_low][mask_low]maskedmerge=enable='between(t,1.5,3.1)'[privacy1]",
            "[privacy1][blur_high][mask_high]maskedmerge=enable='between(t,3.1,4.8)',scale=940:1637:flags=lanczos[clip]",
            "color=c=0x141a1c:s=1080x1920:r=24:d=10.08[background]",
            "[background][clip]overlay=x=70:y=283:shortest=1[base]",
        ]
        for index, cue in enumerate(cues, 3):
            prior = "base" if index == 3 else f"caption{index - 1}"
            filters.append(
                f"[{prior}][{index}:v]overlay=x=0:y=0:"
                f"enable='gte(t,{cue['start']})*lt(t,{cue['end']})':eof_action=pass[caption{index}]"
            )
        filters.append(f"[caption{len(cues) + 2}]format=yuv420p[out]")
        args = [
            "ffmpeg", "-v", "error", "-n", "-i", str(SOURCE),
            "-loop", "1", "-framerate", "24", "-i", str(mask_low),
            "-loop", "1", "-framerate", "24", "-i", str(mask_high),
        ]
        for cue in cues:
            args.extend(["-loop", "1", "-framerate", "24", "-i", str(art / f"{cue['id']}.png")])
        args.extend([
            "-filter_complex", ";".join(filters), "-map", "[out]", "-map", "0:a:0",
            "-t", "10.08", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "copy", "-map_metadata", "0",
            "-movflags", "+faststart+use_metadata_tags", str(OUTPUT),
        ])
        subprocess.run(args, check=True)
    print(OUTPUT)


if __name__ == "__main__":
    main()
