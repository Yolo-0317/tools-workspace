from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from zhixia_tts_manifest import load_episode_manifest, load_voice_config  # noqa: E402


SEASON_PATH = ROOT / "operations" / "yi-wu-yi-yuan" / "qiancheng-v01.json"
RESTART = "yiwu-yiyuan-qiancheng-01-restart-15s"


class YiWuYiYuanQianchengConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.season = json.loads(SEASON_PATH.read_text(encoding="utf-8"))
        cls.voices = load_voice_config(ROOT / "config" / "voices.json")

    def test_voice_trial_manifest_matches_the_full_length_contract(self) -> None:
        entry = next(
            item
            for item in self.season["episodes"]
            if item["production_status"] == "voice-trial"
        )
        path = ROOT / "episodes" / entry["episode"] / "voice-lines.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        manifest = load_episode_manifest(path, self.voices)

        self.assertEqual(entry["episode"], RESTART)
        self.assertEqual(raw["format"], "one-poem-story")
        self.assertEqual(raw["theme"], "一舞一愿前程季重新出发全程朗诵")
        self.assertEqual(raw["theme_slug"], RESTART)
        self.assertEqual(raw["audio_slug"], f"{RESTART}-voice-v03")
        self.assertEqual(
            [line["id"] for line in raw["lines"]],
            ["01-recipient", "02-situation", "03-blessing", "04-poem"],
        )
        self.assertEqual(
            [line["text"].rstrip("。") for line in raw["lines"]],
            [entry["recipient"], entry["situation"], entry["blessing"], entry["poem"]],
        )
        self.assertEqual({line.role for line in manifest.lines}, {"zhixia"})
        self.assertEqual({line.speech_rate for line in manifest.lines}, {0})
        self.assertEqual(
            [line.gap_before_ms for line in manifest.lines],
            [0, 650, 750, 850],
        )
        self.assertEqual({line.revision for line in manifest.lines}, {3})
        self.assertTrue(all(line.context_texts for line in manifest.lines))

    def test_other_two_episodes_remain_non_production_outlines(self) -> None:
        self.assertEqual(
            [item["production_status"] for item in self.season["episodes"][1:]],
            ["theme-outline", "theme-outline"],
        )

    def test_restart_readme_records_both_failed_trials_and_v03_gate(self) -> None:
        text = (ROOT / "episodes" / RESTART / "README.md").read_text(encoding="utf-8")

        self.assertIn("voice-v01", text)
        self.assertIn("7.441 秒", text)
        self.assertIn("不能用于十五秒成片", text)
        self.assertIn("voice-v02", text)
        self.assertIn("58 个汉字", text)
        self.assertIn("人工验收失败", text)
        self.assertIn("voice-v03", text)
        self.assertIn("52 个汉字", text)
        self.assertIn("650、750、850 毫秒", text)
        self.assertIn("speech_rate=0", text)
        self.assertIn("14.000—14.800 秒", text)


if __name__ == "__main__":
    unittest.main()
