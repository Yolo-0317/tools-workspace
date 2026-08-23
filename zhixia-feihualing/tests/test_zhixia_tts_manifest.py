from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from zhixia_tts_manifest import (  # noqa: E402
    VoiceConfig,
    VoiceLine,
    audio_filename,
    build_subtitles,
    load_episode_manifest,
    load_voice_config,
    manifest_from_dict,
)


def voices() -> dict[str, VoiceConfig]:
    return {
        "ayan": VoiceConfig(
            key="ayan",
            name="阿砚",
            speaker="ICL_uranus_zh_female_jiaxiaozi_tob",
            resource_id="seed-tts-2.0",
        ),
        "zhixia": VoiceConfig(
            key="zhixia",
            name="栀夏",
            speaker="ICL_uranus_zh_female_tianmeijiaoqiao_tob",
            resource_id="seed-tts-2.0",
        ),
    }


def valid_manifest_data() -> dict[str, object]:
    return {
        "episode": "ep04",
        "theme": "雨",
        "theme_slug": "rain",
        "audio_slug": "ep04-rain",
        "lines": [
            {
                "id": "01-opening",
                "role": "ayan",
                "text": "今日飞花令，雨。",
                "start_ms": 0,
            },
            {
                "id": "02-poem-01",
                "role": "zhixia",
                "text": "好雨知时节。",
                "start_ms": 2500,
            },
            {"id": "03-poem-02", "role": "ayan", "text": "空山新雨后。"},
            {
                "id": "04-poem-03",
                "role": "zhixia",
                "text": "渭城朝雨。",
                "gap_before_ms": 1800,
            },
            {
                "id": "05-outro",
                "role": "ayan",
                "text": "第四句，你来接。",
                "gap_before_ms": 150,
            },
        ],
    }


class ManifestTests(unittest.TestCase):
    def test_load_voice_config_preserves_fixed_character_mapping(self) -> None:
        loaded = load_voice_config(PROJECT_DIR / "config" / "voices.json")

        self.assertEqual(
            loaded["ayan"].speaker,
            "ICL_uranus_zh_female_jiaxiaozi_tob",
        )
        self.assertEqual(
            loaded["zhixia"].speaker,
            "ICL_uranus_zh_female_tianmeijiaoqiao_tob",
        )
        self.assertEqual(loaded["ayan"].resource_id, "seed-tts-2.0")

    def test_load_episode_manifest_reads_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "voice-lines.json"
            path.write_text(
                json.dumps(valid_manifest_data(), ensure_ascii=False),
                encoding="utf-8",
            )

            manifest = load_episode_manifest(path, voices())

        self.assertEqual(manifest.episode, "ep04")
        self.assertEqual(manifest.lines[1].role, "zhixia")

    def test_build_subtitles_uses_real_durations_and_gap(self) -> None:
        manifest = manifest_from_dict(valid_manifest_data(), voices())

        subtitles = build_subtitles(
            manifest,
            {
                "01-opening": 2000,
                "02-poem-01": 4000,
                "03-poem-02": 3000,
                "04-poem-03": 5000,
                "05-outro": 2500,
            },
        )

        self.assertEqual(subtitles[0]["start"], 0.0)
        self.assertEqual(subtitles[0]["end"], 2.0)
        self.assertEqual(subtitles[1]["start"], 2.5)
        self.assertEqual(subtitles[2]["start"], 6.5)
        self.assertEqual(subtitles[3]["start"], 11.3)
        self.assertEqual(subtitles[4]["start"], 16.45)
        self.assertEqual(subtitles[3]["highlight"], "雨")

    def test_revision_two_adds_suffix(self) -> None:
        line = VoiceLine(
            id="02-poem-01",
            role="zhixia",
            text="好雨知时节。",
            revision=2,
        )

        self.assertEqual(audio_filename(line), "02-zhixia-poem-01-v02.mp3")

    def test_revision_one_uses_standard_filename(self) -> None:
        line = VoiceLine(
            id="01-opening",
            role="ayan",
            text="今日飞花令，雨。",
        )

        self.assertEqual(audio_filename(line), "01-ayan-opening.mp3")

    def test_unknown_role_is_rejected(self) -> None:
        data = valid_manifest_data()
        data["lines"][0]["role"] = "unknown"  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "未知角色"):
            manifest_from_dict(data, voices())

    def test_duplicate_line_id_is_rejected(self) -> None:
        data = valid_manifest_data()
        data["lines"][1]["id"] = "01-opening"  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "重复台词 ID"):
            manifest_from_dict(data, voices())

    def test_empty_text_is_rejected(self) -> None:
        data = valid_manifest_data()
        data["lines"][0]["text"] = "  "  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "台词不能为空"):
            manifest_from_dict(data, voices())

    def test_start_and_gap_are_mutually_exclusive(self) -> None:
        data = valid_manifest_data()
        data["lines"][0]["gap_before_ms"] = 50  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "start_ms.*gap_before_ms"):
            manifest_from_dict(data, voices())

    def test_exactly_five_lines_are_required(self) -> None:
        data = valid_manifest_data()
        data["lines"] = data["lines"][:4]  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "恰好包含 5 句"):
            manifest_from_dict(data, voices())

    def test_negative_gap_is_rejected(self) -> None:
        data = valid_manifest_data()
        data["lines"][2]["gap_before_ms"] = -1  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "非负整数"):
            manifest_from_dict(data, voices())

    def test_missing_duration_is_rejected(self) -> None:
        manifest = manifest_from_dict(valid_manifest_data(), voices())

        with self.assertRaisesRegex(ValueError, "缺少音频时长"):
            build_subtitles(manifest, {"01-opening": 2000})


if __name__ == "__main__":
    unittest.main()
