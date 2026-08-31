from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from zhixia_tts_manifest import load_episode_manifest, load_voice_config  # noqa: E402


SEASON_PATH = ROOT / "operations" / "yi-wu-yi-yuan" / "qiancheng-v01.json"
EXPECTED_THEMES = [
    "一舞一愿前程季重新出发",
    "一舞一愿前程季奔赴远方",
    "一舞一愿前程季走出困境",
]


class YiWuYiYuanQianchengConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.season = json.loads(SEASON_PATH.read_text(encoding="utf-8"))
        cls.voices = load_voice_config(ROOT / "config" / "voices.json")

    def test_all_manifests_match_the_season_contract(self) -> None:
        for index, entry in enumerate(self.season["episodes"]):
            with self.subTest(episode=entry["episode"]):
                path = ROOT / "episodes" / entry["episode"] / "voice-lines.json"
                raw = json.loads(path.read_text(encoding="utf-8"))
                manifest = load_episode_manifest(path, self.voices)

                self.assertEqual(raw["format"], "one-poem-story")
                self.assertEqual(raw["theme"], EXPECTED_THEMES[index])
                self.assertEqual(raw["theme_slug"], entry["episode"])
                self.assertEqual(
                    raw["audio_slug"],
                    f"{entry['episode']}-voice-v01",
                )
                self.assertEqual(
                    [line["id"] for line in raw["lines"]],
                    ["01-recipient", "02-blessing", "03-poem"],
                )
                self.assertEqual(
                    [line["text"].rstrip("。") for line in raw["lines"]],
                    [entry["recipient"], entry["blessing"], entry["poem"]],
                )
                self.assertEqual({line.role for line in manifest.lines}, {"zhixia"})
                self.assertEqual({line.speech_rate for line in manifest.lines}, {0})
                self.assertEqual(
                    [line.gap_before_ms for line in manifest.lines],
                    [0, 180, 400],
                )
                self.assertEqual({line.revision for line in manifest.lines}, {1})
                self.assertTrue(all(line.context_texts for line in manifest.lines))

    def test_all_readmes_record_the_non_negotiable_production_limits(self) -> None:
        for entry in self.season["episodes"]:
            with self.subTest(episode=entry["episode"]):
                path = ROOT / "episodes" / entry["episode"] / "README.md"
                text = path.read_text(encoding="utf-8")

                self.assertIn(entry["share_scene"], text)
                self.assertIn("32 个汉字", text)
                self.assertIn("日常栀夏 v04", text)
                self.assertIn("后期豆包 TTS", text)
                self.assertIn("不生成可辨识人声", text)
                self.assertIn("11.500 秒", text)


if __name__ == "__main__":
    unittest.main()
