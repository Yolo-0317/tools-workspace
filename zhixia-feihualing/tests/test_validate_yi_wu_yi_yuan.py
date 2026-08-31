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
        module.validate_subtitle_plan(path, 15000, 11500, 3000)


class YiWuYiYuanValidationTests(unittest.TestCase):
    def test_counts_only_hanzi(self) -> None:
        self.assertEqual(module.count_hanzi("愿你此去有路，所盼有期。"), 10)

    def test_current_season_is_valid_and_has_three_32_hanzi_episodes(self) -> None:
        data = valid_season()

        module.validate_season(SEASON_PATH)

        episodes = data["episodes"]
        self.assertEqual(len(episodes), 3)
        for episode in episodes:
            total = sum(
                module.count_hanzi(episode[field])
                for field in ("recipient", "blessing", "poem")
            )
            self.assertEqual(total, 32)

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

    def test_accepts_exact_voice_deadline_and_tail(self) -> None:
        plan = [
            {"id": "01-recipient", "start": 0.0, "end": 2.5},
            {"id": "02-blessing", "start": 2.7, "end": 5.4},
            {"id": "03-poem", "start": 5.7, "end": 11.5},
        ]

        validate_plan_temp(plan)

    def test_rejects_voice_end_after_11500(self) -> None:
        plan = [
            {"id": "01-recipient", "start": 0.0, "end": 2.5},
            {"id": "02-blessing", "start": 2.7, "end": 5.4},
            {"id": "03-poem", "start": 6.0, "end": 11.6},
        ]

        with self.assertRaisesRegex(ValueError, "voice end"):
            validate_plan_temp(plan)

    def test_rejects_overlapping_subtitles(self) -> None:
        plan = [
            {"id": "01-recipient", "start": 0.0, "end": 2.5},
            {"id": "02-blessing", "start": 2.4, "end": 5.4},
            {"id": "03-poem", "start": 5.7, "end": 11.0},
        ]

        with self.assertRaisesRegex(ValueError, "overlaps"):
            validate_plan_temp(plan)


if __name__ == "__main__":
    unittest.main()
