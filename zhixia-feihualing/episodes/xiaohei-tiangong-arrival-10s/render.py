"""Add subtitles to the Xiaohei Tiangong video, preserving the source audio."""

import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
EPISODE = Path(__file__).resolve().parent
SOURCE = ROOT / "assets/generated-video/xiaohei-tiangong-arrival-10s-original.mp4"
CUES = EPISODE / "subtitles.json"
OUTPUT_720 = ROOT / "exports/xiaohei-tiangong-arrival-subtitled-720p-v01.mp4"
OUTPUT_1080 = ROOT / "exports/xiaohei-tiangong-arrival-subtitled-1080p-v01.mp4"
SUBTITLE_RENDERER = ROOT / "episodes/xiaohei-ai-pet-10s/render_subtitles.swift"


def run(*args):
    subprocess.run(args, check=True)


def probe(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def main():
    if OUTPUT_720.exists() or OUTPUT_1080.exists():
        raise FileExistsError("Versioned output already exists")
    cues = json.loads(CUES.read_text())
    previous_end = 0.0
    for cue in cues:
        assert previous_end <= cue["start"] < cue["end"] <= 10.08
        previous_end = cue["end"]
    metadata = json.loads(probe(
        "ffprobe", "-v", "error", "-show_entries", "format_tags=AIGC", "-of", "json", str(SOURCE)
    )).get("format", {}).get("tags", {})
    with tempfile.TemporaryDirectory(prefix="xiaohei-tiangong-subtitles-") as temp:
        temp = Path(temp)
        art = temp / "subtitles"
        art.mkdir()
        env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(temp / "clang"), SWIFT_MODULECACHE_PATH=str(temp / "swift"))
        subprocess.run(["swift", "-module-cache-path", str(temp / "swift"), str(SUBTITLE_RENDERER), str(CUES), str(art)], check=True, env=env)
        filters = ["[0:v]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1[clean]"]
        for input_index, cue in enumerate(cues, 1):
            previous = "clean" if input_index == 1 else f"caption{input_index - 1}"
            filters.append(
                f"[{previous}][{input_index}:v]overlay="
                f"enable='gte(t,{cue['start']})*lt(t,{cue['end']})':eof_action=pass[caption{input_index}]"
            )
        args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-i", str(SOURCE)]
        for cue in cues:
            args.extend(["-loop", "1", "-framerate", "24", "-i", str(art / f"{cue['id']}.png")])
        args.extend([
            "-filter_complex", ";".join(filters), "-map", f"[caption{len(cues)}]", "-map", "0:a:0",
            "-t", "10.08", "-r", "24", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-c:a", "copy", "-map_metadata", "0",
            "-movflags", "+faststart+use_metadata_tags",
        ])
        if "AIGC" in metadata:
            args.extend(["-metadata", f"AIGC={metadata['AIGC']}"])
        run(*args, str(OUTPUT_720))
    upsample = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-i", str(OUTPUT_720),
        "-vf", "scale=1080:1920:flags=lanczos,setsar=1", "-map", "0:v:0", "-map", "0:a:0",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-map_metadata", "0", "-movflags", "+faststart+use_metadata_tags",
    ]
    if "AIGC" in metadata:
        upsample.extend(["-metadata", f"AIGC={metadata['AIGC']}"])
    run(*upsample, str(OUTPUT_1080))
    print(OUTPUT_1080)


if __name__ == "__main__":
    main()
