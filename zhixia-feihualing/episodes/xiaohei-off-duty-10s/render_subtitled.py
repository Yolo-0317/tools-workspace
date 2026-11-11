"""Render Xiaohei's timed captions in the established 1080p style."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
EPISODE = Path(__file__).resolve().parent
SOURCE = ROOT / "assets/generated-video/xiaohei-off-duty-10s-original.mp4"
OUTPUT = ROOT / "exports/xiaohei-off-duty-subtitled-1080p-v01.mp4"
CUES = EPISODE / "subtitles.json"
RENDERER = ROOT / "episodes/xiaohei-selective-hearing-10s/render_dialogue_subtitles.swift"


def probe(*args):
    return subprocess.run(
        ["ffprobe", "-v", "error", *args, str(SOURCE)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cues", type=Path, default=CUES)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    options = parser.parse_args()
    if options.output.exists():
        raise FileExistsError(f"Output already exists: {options.output}")
    cues = json.loads(options.cues.read_text())
    previous_end = 0.0
    for cue in cues:
        assert previous_end <= cue["start"] < cue["end"] <= 10.08
        previous_end = cue["end"]

    frames = int(probe("-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1").strip())
    tags = json.loads(probe("-show_entries", "format_tags=AIGC", "-of", "json")).get("format", {}).get("tags", {})

    with tempfile.TemporaryDirectory(prefix="xiaohei-off-duty-captions-") as temporary:
        art = Path(temporary)
        env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(art / "clang"), SWIFT_MODULECACHE_PATH=str(art / "swift"))
        subprocess.run(["swift", str(RENDERER), str(options.cues), str(art)], check=True, env=env)

        filters = ["[0:v]scale=1080:1920:flags=lanczos:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[base]"]
        for index, cue in enumerate(cues, 1):
            prior = "base" if index == 1 else f"v{index - 1}"
            filters.append(
                f"[{prior}][{index}:v]overlay=x=0:y=0:"
                f"enable='gte(t,{cue['start']})*lt(t,{cue['end']})':eof_action=pass[v{index}]"
            )
        filters.append(f"[v{len(cues)}]trim=end_frame={frames},format=yuv420p[out]")

        args = ["ffmpeg", "-v", "error", "-n", "-i", str(SOURCE)]
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
        args.append(str(options.output))
        subprocess.run(args, check=True)
    print(options.output)


if __name__ == "__main__":
    main()
