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
                ("zhixia", 2500),
                ("zhixia", 4200),
                ("zhixia", 6800),
                ("ayan", 9800),
                ("zhixia", 11300),
            ],
        )

        durations_ms = {
            "01-ayan-question": 2400,
            "02-zhixia-cast": 1400,
            "03-system-hexagram": 1000,
            "04-zhixia-reading": 2700,
            "05-ayan-hope": 1300,
            "06-zhixia-reveal": 1800,
        }
        subtitles = build_subtitles(manifest, durations_ms)
        self.assertEqual(
            [(item["start"], item["end"]) for item in subtitles],
            [
                (0.0, 2.4),
                (2.5, 3.9),
                (4.2, 5.2),
                (6.8, 9.5),
                (9.8, 11.1),
                (11.3, 13.1),
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
        self.assertEqual(
            cards[6]["text"], "传统文化趣味演绎，请勿作为现实决策依据"
        )
        self.assertEqual(cards[7]["text"], "栀夏赛博起卦")


if __name__ == "__main__":
    unittest.main()
