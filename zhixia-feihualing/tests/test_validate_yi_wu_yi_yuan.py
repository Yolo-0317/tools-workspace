from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEASON_PATH = ROOT / "operations" / "yi-wu-yi-yuan" / "qiancheng-v01.json"
VALIDATOR_PATH = ROOT / "scripts" / "validate_yi_wu_yi_yuan.py"
SPEC = importlib.util.spec_from_file_location("validate_yi_wu_yi_yuan", VALIDATOR_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def valid_season() -> dict[str, object]:
    return json.loads(SEASON_PATH.read_text(encoding="utf-8"))


def validate_temp(data: dict[str, object]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "season.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        module.validate_season(path)


def validate_plan_temp(plan: list[dict[str, object]]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "subtitle-plan.json"
        path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        try:
            module.validate_subtitle_plan(path, 15000, 200, 14000, 14800, 500)
        except TypeError as exc:
            raise AssertionError("full-length subtitle interface is missing") from exc


def full_length_plan() -> list[dict[str, object]]:
    return [
        {"id": "01-recipient", "start": 0.0, "end": 1.5},
        {"id": "02-situation", "start": 1.68, "end": 5.4},
        {"id": "03-blessing", "start": 5.64, "end": 10.1},
        {"id": "04-poem", "start": 10.45, "end": 14.6},
    ]


class YiWuYiYuanValidationTests(unittest.TestCase):
    def test_counts_only_hanzi(self) -> None:
        self.assertEqual(module.count_hanzi("愿你此去有路，所盼有期。"), 10)

    def test_restart_is_the_only_full_length_voice_trial(self) -> None:
        data = valid_season()

        module.validate_season(SEASON_PATH)

        self.assertEqual(
            data.get("recitation"),
            {
                "target_hanzi_min": 55,
                "target_hanzi_max": 60,
                "voice_start_max_ms": 200,
                "voice_end_min_ms": 14000,
                "voice_end_target_max_ms": 14800,
                "duration_ms": 15000,
                "max_gap_ms": 500,
                "speech_rate": 0,
            },
        )
        trials = [
            item
            for item in data["episodes"]
            if item.get("production_status") == "voice-trial"
        ]
        self.assertEqual(
            [item["episode"] for item in trials],
            ["yiwu-yiyuan-qiancheng-01-restart-15s"],
        )
        entry = trials[0]
        self.assertEqual(
            [entry["recipient"], entry["situation"], entry["blessing"], entry["poem"]],
            [
                "送给重新出发的你",
                "也许这一程并不轻松，也许前方还有风浪",
                "愿你此去有路，所盼有期；走过的每一步，都算数",
                "长风破浪会有时，直挂云帆济沧海",
            ],
        )
        self.assertEqual(
            sum(
                module.count_hanzi(entry[field])
                for field in ("recipient", "situation", "blessing", "poem")
            ),
            58,
        )
        self.assertEqual(
            [item.get("production_status") for item in data["episodes"][1:]],
            ["theme-outline", "theme-outline"],
        )

    def test_rejects_voice_trial_shorter_than_55_hanzi(self) -> None:
        data = valid_season()
        data["episodes"][0]["situation"] = "前路有风浪"

        with self.assertRaisesRegex(ValueError, "voice-trial.*55"):
            validate_temp(data)

    def test_rejects_overlong_recipient(self) -> None:
        data = valid_season()
        data["episodes"][0]["recipient"] = "送给每一个正在重新出发的朋友"

        with self.assertRaisesRegex(ValueError, "recipient.*10"):
            validate_temp(data)

    def test_rejects_banned_phrase(self) -> None:
        data = valid_season()
        data["episodes"][0]["blessing"] = "接住好运"

        with self.assertRaisesRegex(ValueError, "banned phrase"):
            validate_temp(data)

    def test_rejects_duplicate_recipient(self) -> None:
        data = valid_season()
        data["episodes"][1]["recipient"] = data["episodes"][0]["recipient"]

        with self.assertRaisesRegex(ValueError, "recipient.*unique"):
            validate_temp(data)

    def test_rejects_attribution_without_title(self) -> None:
        data = valid_season()
        data["episodes"][0]["attribution"] = "唐·李白"

        with self.assertRaisesRegex(ValueError, "attribution"):
            validate_temp(data)

    def test_accepts_full_length_timeline_inside_target_window(self) -> None:
        validate_plan_temp(full_length_plan())

    def test_rejects_voice_start_after_200_ms(self) -> None:
        plan = full_length_plan()
        plan[0]["start"] = 0.201

        with self.assertRaisesRegex(ValueError, "voice start"):
            validate_plan_temp(plan)

    def test_rejects_voice_end_before_14000_ms(self) -> None:
        plan = full_length_plan()
        plan[-1]["end"] = 13.999

        with self.assertRaisesRegex(ValueError, "voice end"):
            validate_plan_temp(plan)

    def test_accepts_voice_end_after_target_but_before_video_end(self) -> None:
        plan = full_length_plan()
        plan[-1]["end"] = 14.9

        validate_plan_temp(plan)

    def test_rejects_voice_end_after_video(self) -> None:
        plan = full_length_plan()
        plan[-1]["end"] = 15.001

        with self.assertRaisesRegex(ValueError, "voice end"):
            validate_plan_temp(plan)

    def test_rejects_gap_over_500_ms(self) -> None:
        plan = full_length_plan()
        plan[2]["start"] = 5.901

        with self.assertRaisesRegex(ValueError, "gap"):
            validate_plan_temp(plan)

    def test_rejects_overlapping_subtitles(self) -> None:
        plan = full_length_plan()
        plan[1]["start"] = 1.4

        with self.assertRaisesRegex(ValueError, "overlaps"):
            validate_plan_temp(plan)


if __name__ == "__main__":
    unittest.main()
