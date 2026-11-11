"""Add timed bottom dialogue captions to the approved AI-blooper edit."""

import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
EPISODE = Path(__file__).resolve().parent
SOURCE = ROOT / "exports/xiaohei-selective-hearing-ai-fail-captioned-1080p-v04.mp4"
OUTPUT = ROOT / "exports/xiaohei-selective-hearing-ai-fail-dialogue-1080p-v06.mp4"
CUES = EPISODE / "subtitles-dialogue-v01.json"
RENDERER = EPISODE / "render_dialogue_subtitles.swift"


def main():
    if OUTPUT.exists():
        raise FileExistsError(f"Output exists; use a new version: {OUTPUT}")
    cues = json.loads(CUES.read_text())
    previous_end = 0.0
    for cue in cues:
        assert previous_end <= cue["start"] < cue["end"] <= 10.08
        previous_end = cue["end"]

    with tempfile.TemporaryDirectory(prefix="xiaohei-dialogue-") as temporary:
        art = Path(temporary)
        env = dict(os.environ, CLANG_MODULE_CACHE_PATH=str(art / "clang"), SWIFT_MODULECACHE_PATH=str(art / "swift"))
        subprocess.run(["swift", str(RENDERER), str(CUES), str(art)], check=True, env=env)
        args = ["ffmpeg", "-v", "error", "-n", "-i", str(SOURCE)]
        for cue in cues:
            args.extend(["-loop", "1", "-framerate", "24", "-i", str(art / f"{cue['id']}.png")])
        filters = []
        for index, cue in enumerate(cues, 1):
            prior = "0:v" if index == 1 else f"v{index - 1}"
            filters.append(
                f"[{prior}][{index}:v]overlay=x=0:y=0:"
                f"enable='gte(t,{cue['start']})*lt(t,{cue['end']})':eof_action=pass[v{index}]"
            )
        filters.append(f"[v{len(cues)}]format=yuv420p[out]")
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
