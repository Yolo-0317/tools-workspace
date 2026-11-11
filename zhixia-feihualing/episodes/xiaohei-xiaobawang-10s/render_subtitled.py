"""Add timed Xiaohei voiceover subtitles to the owner-provided Xiaobawang clip."""

import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
EPISODE = Path(__file__).resolve().parent
SOURCE = ROOT / "assets/generated-video/xiaohei-xiaobawang-10s-original.mp4"
OUTPUT = ROOT / "exports/xiaohei-xiaobawang-subtitled-1080p-v01.mp4"
CUES = EPISODE / "subtitles.json"
RENDERER = EPISODE / "render_subtitle_cards.swift"


def capture(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    cues = json.loads(CUES.read_text(encoding="utf-8"))
    duration = float(capture("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(SOURCE)).strip())
    frames = int(capture("ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(SOURCE)).strip())
    previous = 0.0
    for cue in cues:
        assert previous <= cue["start"] < cue["end"] <= duration
        previous = cue["end"]
    tags = json.loads(capture("ffprobe", "-v", "error", "-show_entries", "format_tags=AIGC", "-of", "json", str(SOURCE))).get("format", {}).get("tags", {})

    with tempfile.TemporaryDirectory(prefix="xiaohei-xiaobawang-") as temporary:
        work = Path(temporary)
        cards = work / "cards"
        env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(work / "clang"), SWIFT_MODULECACHE_PATH=str(work / "swift"))
        subprocess.run(["swift", str(RENDERER), str(CUES), str(cards)], check=True, env=env)

        filters = ["[0:v]scale=1080:1920:flags=lanczos:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[base]"]
        for index, cue in enumerate(cues, 1):
            prior = "base" if index == 1 else f"caption{index - 1}"
            filters.append(
                f"[{prior}][{index}:v]overlay=x=0:y=0:"
                f"enable='gte(t,{cue['start']})*lt(t,{cue['end']})':eof_action=pass[caption{index}]"
            )
        filters.append(f"[caption{len(cues)}]trim=end_frame={frames},format=yuv420p[out]")

        args = ["ffmpeg", "-v", "error", "-n", "-i", str(SOURCE)]
        for cue in cues:
            args.extend(["-loop", "1", "-framerate", "24", "-i", str(cards / f"{cue['id']}.png")])
        args.extend([
            "-filter_complex", ";".join(filters), "-map", "[out]", "-map", "0:a:0",
            "-t", str(duration), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
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
