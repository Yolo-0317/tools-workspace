import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class YunzhongjunRecitationManifestTest(unittest.TestCase):
    def test_voice_and_subtitle_contract(self):
        episode = ROOT / "episodes" / "jiuge-yunzhongjun-15s"
        voice = json.loads(
            (episode / "voice-lines.json").read_text(encoding="utf-8")
        )
        subtitle = json.loads(
            (episode / "subtitle-plan.json").read_text(encoding="utf-8")
        )

        self.assertEqual(voice["episode"], "jiuge-yunzhongjun-15s")
        self.assertEqual(voice["format"], "one-poem-story")
        self.assertEqual(voice["audio_slug"], "jiuge-yunzhongjun-15s-slow-v01")
        self.assertEqual(
            [line["text"] for line in voice["lines"]],
            ["灵皇皇兮，既降。", "猋，远举兮，云中。"],
        )
        self.assertEqual(
            [line["start_ms"] for line in voice["lines"]],
            [1000, 7700],
        )
        self.assertEqual([line["speech_rate"] for line in voice["lines"]], [-50, -50])
        self.assertEqual([line["revision"] for line in voice["lines"]], [3, 4])

        self.assertEqual(
            [(item["text"], item["side"]) for item in subtitle],
            [("灵皇皇兮既降", "right"), ("猋远举兮云中", "left")],
        )
        self.assertEqual(subtitle[0]["attribution"], "屈原《九歌·云中君》节选")
        self.assertNotIn("attribution", subtitle[1])
        self.assertEqual(
            [(item["start"], item["end"]) for item in subtitle],
            [(1.0, 6.2), (7.7, 13.5)],
        )


if __name__ == "__main__":
    unittest.main()
