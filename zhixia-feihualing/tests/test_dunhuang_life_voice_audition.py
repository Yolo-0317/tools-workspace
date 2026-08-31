from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from zhixia_tts_manifest import load_episode_manifest, load_voice_config  # noqa: E402


class DunhuangLifeVoiceAuditionTests(unittest.TestCase):
    def test_manifest_builds_four_comparable_natural_rate_requests(self) -> None:
        voices = load_voice_config(ROOT / "config" / "voices.json")
        manifest_path = (
            ROOT / "episodes/dunhuang-life-voice-audition/voice-lines.json"
        )
        self.assertTrue(manifest_path.is_file(), "试听 manifest 必须存在")
        manifest = load_episode_manifest(
            manifest_path,
            voices,
        )
        expected_text = (
            "看山恰似走来迎。仔细看山，山不动，是船行。"
            "有时候，你以为是世界变了。其实，是你终于开始往前走了。"
        )

        self.assertEqual(
            [line.role for line in manifest.lines],
            [
                "zhixia",
                "zhixia-qingchezizi-test",
                "zhixia-zhixingnv-test",
                "zhixia-wenrouxiaoya-test",
            ],
        )
        self.assertEqual({line.text for line in manifest.lines}, {expected_text})
        self.assertEqual({line.speech_rate for line in manifest.lines}, {0})
        self.assertEqual(
            {manifest.voices[line.role].resource_id for line in manifest.lines},
            {"seed-tts-2.0"},
        )
        self.assertEqual(
            manifest.audio_slug,
            "dunhuang-huanxisha-life-voice-audition-v01",
        )


if __name__ == "__main__":
    unittest.main()
