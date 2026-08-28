from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from zhixia_tts_client import (  # noqa: E402
    AudioProbe,
    TTSTemporaryError,
    TTSResult,
)
from zhixia_tts_manifest import (  # noqa: E402
    EpisodeManifest,
    VoiceConfig,
    VoiceLine,
)
from zhixia_tts_pipeline import (  # noqa: E402
    VersionConflict,
    build_generation_plan,
    generate_pending_lines,
)


def manifest() -> EpisodeManifest:
    voices = {
        "ayan": VoiceConfig("ayan", "阿砚", "ayan-speaker", "seed-tts-2.0"),
        "zhixia": VoiceConfig(
            "zhixia", "栀夏", "zhixia-speaker", "seed-tts-2.0"
        ),
    }
    return EpisodeManifest(
        episode="ep04",
        format="one-character-three-poems",
        theme="雨",
        theme_slug="rain",
        audio_slug="ep04-rain",
        lines=(
            VoiceLine("01-opening", "ayan", "今日飞花令，雨。", start_ms=0),
            VoiceLine("02-poem-01", "zhixia", "好雨知时节。", start_ms=1200),
            VoiceLine("03-poem-02", "ayan", "空山新雨后。"),
            VoiceLine("04-poem-03", "zhixia", "渭城朝雨。", gap_before_ms=100),
            VoiceLine("05-outro", "ayan", "第四句，你来接。", gap_before_ms=100),
        ),
        voices=voices,
    )


def fake_probe(path: Path) -> AudioProbe:
    if not path.read_bytes().startswith(b"fake-mp3"):
        raise ValueError("invalid fixture")
    return AudioProbe("mp3", 24000, 1, 1000)


class FakeClient:
    def __init__(self, *, fail_once: set[str] | None = None) -> None:
        self.fail_once = set(fail_once or ())
        self.calls: list[str] = []
        self.contexts: dict[str, tuple[str, ...]] = {}

    def synthesize(self, request: object) -> TTSResult:
        uid = request.uid  # type: ignore[attr-defined]
        line_id = uid.removeprefix("ep04-")
        self.calls.append(line_id)
        self.contexts[line_id] = request.context_texts  # type: ignore[attr-defined]
        if line_id in self.fail_once:
            self.fail_once.remove(line_id)
            raise TTSTemporaryError("temporary fixture failure")
        return TTSResult(
            audio=f"fake-mp3:{line_id}".encode(),
            request_id=f"request-{line_id}",
            message="OK",
        )


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.manifest = manifest()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_fresh_plan_reports_all_pending_and_counts_characters(self) -> None:
        plan = build_generation_plan(self.root, self.manifest, probe=fake_probe)

        self.assertEqual(len(plan.ready), 0)
        self.assertEqual([state.line.id for state in plan.pending], [
            "01-opening",
            "02-poem-01",
            "03-poem-02",
            "04-poem-03",
            "05-outro",
        ])
        self.assertEqual(plan.expected_api_calls, 5)
        self.assertEqual(
            plan.total_characters,
            sum(len(line.text) for line in self.manifest.lines),
        )

    def test_matching_ready_lines_are_skipped_without_api_call(self) -> None:
        first_client = FakeClient()
        first_plan = build_generation_plan(self.root, self.manifest, probe=fake_probe)
        generate_pending_lines(first_plan, first_client, probe=fake_probe)
        second_client = FakeClient()

        second_plan = build_generation_plan(self.root, self.manifest, probe=fake_probe)
        result = generate_pending_lines(second_plan, second_client, probe=fake_probe)

        self.assertEqual(second_client.calls, [])
        self.assertEqual(result.expected_api_calls, 0)
        self.assertEqual(len(result.ready), 5)

    def test_context_texts_are_forwarded_to_tts_request(self) -> None:
        lines = list(self.manifest.lines)
        direction = "她迎风追上同伴，带笑自然回嘴。"
        lines[1] = replace(lines[1], context_texts=(direction,))
        context_manifest = replace(self.manifest, lines=tuple(lines))
        client = FakeClient()

        plan = build_generation_plan(self.root, context_manifest, probe=fake_probe)
        generate_pending_lines(plan, client, probe=fake_probe)

        self.assertEqual(client.contexts["02-poem-01"], (direction,))

    def test_changed_context_requires_revision_instead_of_reusing_audio(self) -> None:
        plan = build_generation_plan(self.root, self.manifest, probe=fake_probe)
        generate_pending_lines(plan, FakeClient(), probe=fake_probe)
        changed_lines = list(self.manifest.lines)
        changed_lines[1] = replace(
            changed_lines[1], context_texts=("带笑自然回嘴。",)
        )
        changed_manifest = replace(self.manifest, lines=tuple(changed_lines))

        with self.assertRaisesRegex(VersionConflict, "revision"):
            build_generation_plan(self.root, changed_manifest, probe=fake_probe)

    def test_changed_text_requires_revision_instead_of_overwrite(self) -> None:
        plan = build_generation_plan(self.root, self.manifest, probe=fake_probe)
        generate_pending_lines(plan, FakeClient(), probe=fake_probe)
        changed_lines = list(self.manifest.lines)
        changed_lines[1] = replace(changed_lines[1], text="好雨来得正是时候。")
        changed_manifest = replace(self.manifest, lines=tuple(changed_lines))

        with self.assertRaisesRegex(VersionConflict, "revision"):
            build_generation_plan(self.root, changed_manifest, probe=fake_probe)

    def test_higher_revision_creates_new_file_without_overwriting_old_one(self) -> None:
        plan = build_generation_plan(self.root, self.manifest, probe=fake_probe)
        generate_pending_lines(plan, FakeClient(), probe=fake_probe)
        old_path = self.root / "assets/audio/ep04-rain/02-zhixia-poem-01.mp3"
        old_bytes = old_path.read_bytes()
        changed_lines = list(self.manifest.lines)
        changed_lines[1] = replace(
            changed_lines[1], text="好雨来得正是时候。", revision=2
        )
        changed_manifest = replace(self.manifest, lines=tuple(changed_lines))

        revised_plan = build_generation_plan(self.root, changed_manifest, probe=fake_probe)
        generate_pending_lines(revised_plan, FakeClient(), probe=fake_probe)

        revised_path = self.root / "assets/audio/ep04-rain/02-zhixia-poem-01-v02.mp3"
        self.assertTrue(revised_path.exists())
        self.assertEqual(old_path.read_bytes(), old_bytes)

    def test_resume_generates_only_failed_and_remaining_lines(self) -> None:
        client = FakeClient(fail_once={"03-poem-02"})
        plan = build_generation_plan(self.root, self.manifest, probe=fake_probe)

        with self.assertRaises(TTSTemporaryError):
            generate_pending_lines(plan, client, probe=fake_probe)

        resumed = build_generation_plan(self.root, self.manifest, probe=fake_probe)

        self.assertEqual(
            [state.line.id for state in resumed.pending],
            ["03-poem-02", "04-poem-03", "05-outro"],
        )
        self.assertEqual(
            [state.line.id for state in resumed.ready],
            ["01-opening", "02-poem-01"],
        )

    def test_metadata_keeps_manifest_order_and_redacts_failure_detail(self) -> None:
        client = FakeClient(fail_once={"03-poem-02"})
        plan = build_generation_plan(self.root, self.manifest, probe=fake_probe)

        with self.assertRaises(TTSTemporaryError):
            generate_pending_lines(plan, client, probe=fake_probe)

        metadata_path = self.root / "assets/audio/ep04-rain/audio-metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(
            [item["id"] for item in metadata["lines"]],
            ["01-opening", "02-poem-01", "03-poem-02"],
        )
        self.assertEqual(metadata["lines"][2]["status"], "failed")
        self.assertEqual(metadata["lines"][2]["error"], "TTSTemporaryError")
        self.assertNotIn("temporary fixture failure", metadata_path.read_text())

    def test_subtitles_are_written_only_after_all_lines_are_ready(self) -> None:
        client = FakeClient(fail_once={"03-poem-02"})
        plan = build_generation_plan(self.root, self.manifest, probe=fake_probe)
        subtitle_path = self.root / "episodes/ep04/subtitles-rain.json"

        with self.assertRaises(TTSTemporaryError):
            generate_pending_lines(plan, client, probe=fake_probe)
        self.assertFalse(subtitle_path.exists())

        resumed = build_generation_plan(self.root, self.manifest, probe=fake_probe)
        generate_pending_lines(resumed, client, probe=fake_probe)

        subtitles = json.loads(subtitle_path.read_text(encoding="utf-8"))
        self.assertEqual(len(subtitles), 5)
        self.assertEqual(subtitles[1]["start"], 1.2)
        self.assertEqual(subtitles[1]["end"], 2.2)

    def test_unmanaged_existing_target_is_not_overwritten(self) -> None:
        audio_dir = self.root / "assets/audio/ep04-rain"
        audio_dir.mkdir(parents=True)
        target = audio_dir / "01-ayan-opening.mp3"
        target.write_bytes(b"user-owned")

        with self.assertRaisesRegex(VersionConflict, "unmanaged"):
            build_generation_plan(self.root, self.manifest, probe=fake_probe)

        self.assertEqual(target.read_bytes(), b"user-owned")


if __name__ == "__main__":
    unittest.main()
