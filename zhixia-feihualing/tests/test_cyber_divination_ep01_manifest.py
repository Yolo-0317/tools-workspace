import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from zhixia_tts_manifest import build_subtitles, load_episode_manifest, load_voice_config


class CyberDivinationEpisodeManifestTests(unittest.TestCase):
    def test_builds_the_fixed_timeline(self):
        voices = load_voice_config(ROOT / "config" / "voices.json")
        manifest = load_episode_manifest(
            ROOT / "episodes/cyber-divination-ep01/voice-lines.json",
            voices,
        )

        self.assertEqual(manifest.episode, "cyber-divination-ep01")
        self.assertEqual(manifest.theme, "山雷颐")
        self.assertEqual(
            [(line.role, line.start_ms) for line in manifest.lines],
            [
                ("ayan", 0),
                ("zhixia", 2200),
                ("zhixia", 3700),
                ("zhixia", 4900),
                ("ayan", 8500),
                ("zhixia", 10100),
            ],
        )

        durations_ms = {
            "01-ayan-question": 2100,
            "02-zhixia-cast": 1000,
            "03-system-hexagram": 1100,
            "04-zhixia-reading": 3500,
            "05-ayan-hope": 1500,
            "06-zhixia-reveal": 1900,
        }
        subtitles = build_subtitles(manifest, durations_ms)
        self.assertEqual(
            [(item["start"], item["end"]) for item in subtitles],
            [
                (0.0, 2.1),
                (2.2, 3.2),
                (3.7, 4.8),
                (4.9, 8.4),
                (8.5, 10.0),
                (10.1, 12.0),
            ],
        )

    def test_overlay_plan_separates_classic_text_from_comedy(self):
        cards = json.loads(
            (ROOT / "episodes/cyber-divination-ep01/subtitle-plan.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            [item["kind"] for item in cards],
            [
                "dialogue",
                "dialogue",
                "hexagram",
                "dialogue",
                "dialogue",
                "dialogue",
                "disclaimer",
                "title",
            ],
        )
        self.assertEqual(
            cards[2],
            {
                "id": "03-system-hexagram",
                "kind": "hexagram",
                "text": "山雷颐",
                "secondary": "颐，贞吉。观颐，自求口实。",
                "attribution": "《周易·颐》",
            },
        )
        self.assertEqual(cards[0]["text"], "最后一块，能吃吗？")
        self.assertEqual(cards[1]["text"], "起卦。")
        self.assertEqual(cards[3]["text"], "颐，贞吉。观颐，自求口实。")
        self.assertEqual(cards[4]["text"], "卦说能吃？")
        self.assertEqual(
            cards[6]["text"], "传统文化趣味演绎，请勿作为现实决策依据"
        )
        self.assertEqual(cards[7]["text"], "栀夏赛博起卦")


if __name__ == "__main__":
    unittest.main()
