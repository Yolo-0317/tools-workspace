import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts" / "render_tiangong_fail_top_captions.swift"


class TiangongCaptionRendererTest(unittest.TestCase):
    def test_compact_font_size_keeps_author_note_on_one_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            manifest = work / "captions.json"
            output = work / "cards"
            binary = work / "renderer"
            cache = work / "swift-cache"
            cache.mkdir()
            manifest.write_text(
                json.dumps(
                    [
                        {
                            "id": "author-note",
                            "text": "本来让 AI 说“减肥”，结果两个字直接粘一块儿了",
                            "start": 0.0,
                            "end": 2.0,
                            "kind": "commentary",
                            "fontSize": 30,
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["SWIFT_MODULECACHE_PATH"] = str(cache)
            env["CLANG_MODULE_CACHE_PATH"] = str(cache)
            subprocess.run(
                ["swiftc", str(RENDERER), "-o", str(binary)],
                check=True,
                env=env,
            )
            subprocess.run([str(binary), str(manifest), str(output)], check=True)

            probe = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loop",
                    "1",
                    "-i",
                    str(output / "author-note.png"),
                    "-vf",
                    "alphaextract,cropdetect=limit=0.01:round=1:reset=1",
                    "-f",
                    "null",
                    "-frames:v",
                    "3",
                    "-",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            crops = re.findall(r"crop=\d+:(\d+):\d+:\d+", probe.stderr)
            self.assertTrue(crops)
            self.assertLessEqual(int(crops[-1]), 60)


if __name__ == "__main__":
    unittest.main()
