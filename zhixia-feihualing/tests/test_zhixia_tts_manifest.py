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
            "ICL_uranus_zh_female_tianmeihuopo_tob",
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

    def test_manifest_preserves_optional_context_texts(self) -> None:
        data = valid_manifest_data()
        data["lines"][1]["context_texts"] = [  # type: ignore[index]
            "她迎风追上同伴，带笑自然回嘴。",
            "不要朗读，不要播音腔。",
        ]

        manifest = manifest_from_dict(data, voices())

        self.assertEqual(
            manifest.lines[1].context_texts,
            (
                "她迎风追上同伴，带笑自然回嘴。",
                "不要朗读，不要播音腔。",
            ),
        )

    def test_manifest_rejects_blank_context_text(self) -> None:
        data = valid_manifest_data()
        data["lines"][1]["context_texts"] = ["  "]  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "context_texts"):
            manifest_from_dict(data, voices())

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

    def test_four_lines_without_opening_are_accepted(self) -> None:
        data = valid_manifest_data()
        data["lines"] = data["lines"][1:]  # type: ignore[index]

        manifest = manifest_from_dict(data, voices())

        self.assertEqual(len(manifest.lines), 4)
        self.assertEqual(manifest.lines[0].id, "02-poem-01")

    def test_two_poem_lines_without_opening_or_outro_are_accepted(self) -> None:
        data = valid_manifest_data()
        data["format"] = "one-character-two-poems"
        data["episode"] = "ep06"
        data["theme"] = "秋"
        data["theme_slug"] = "autumn"
        data["audio_slug"] = "ep06-autumn"
        data["lines"] = [
            {
                "id": "02-poem-01",
                "role": "zhixia",
                "text": "树树皆秋色，山山唯落晖。",
                "start_ms": 1800,
            },
            {
                "id": "03-poem-02",
                "role": "ayan",
                "text": "秋风生渭水，落叶满长安。",
                "start_ms": 7800,
            },
        ]

        manifest = manifest_from_dict(data, voices())

        self.assertEqual(len(manifest.lines), 2)
        self.assertEqual(manifest.lines[0].start_ms, 1800)
        self.assertEqual(manifest.lines[1].start_ms, 7800)

    def test_two_poem_format_accepts_opening_plus_two_poems(self) -> None:
        data = valid_manifest_data()
        data["format"] = "one-character-two-poems"
        data["lines"] = data["lines"][:3]  # type: ignore[index]

        manifest = manifest_from_dict(data, voices())

        self.assertEqual(manifest.format, "one-character-two-poems")
        self.assertEqual(len(manifest.lines), 3)

    def test_one_poem_story_format_accepts_single_voiceover(self) -> None:
        data = valid_manifest_data()
        data["format"] = "one-poem-story"
        data["episode"] = "qiusi"
        data["theme"] = "秋思"
        data["theme_slug"] = "qiusi"
        data["audio_slug"] = "qiusi"
        data["lines"] = [
            {
                "id": "01-poem-voiceover",
                "role": "ayan",
                "text": "复恐匆匆说不尽，行人临发又开封。",
                "start_ms": 10500,
            }
        ]

        manifest = manifest_from_dict(data, voices())

        self.assertEqual(manifest.format, "one-poem-story")
        self.assertEqual(len(manifest.lines), 1)
        self.assertEqual(manifest.lines[0].role, "ayan")

    def test_one_poem_story_format_accepts_four_voice_lines(self) -> None:
        data = valid_manifest_data()
        data["format"] = "one-poem-story"
        data["episode"] = "chishang"
        data["theme"] = "池上"
        data["theme_slug"] = "chishang"
        data["audio_slug"] = "chishang"
        data["lines"] = data["lines"][:4]  # type: ignore[index]

        manifest = manifest_from_dict(data, voices())

        self.assertEqual(manifest.format, "one-poem-story")
        self.assertEqual(len(manifest.lines), 4)

    def test_one_poem_story_format_rejects_empty_lines(self) -> None:
        data = valid_manifest_data()
        data["format"] = "one-poem-story"
        data["lines"] = []

        with self.assertRaisesRegex(ValueError, "至少包含 1 句"):
            manifest_from_dict(data, voices())

    def test_fewer_than_four_lines_are_rejected(self) -> None:
        data = valid_manifest_data()
        data["lines"] = data["lines"][:3]  # type: ignore[index]

        with self.assertRaisesRegex(ValueError, "4 或 5 句"):
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
