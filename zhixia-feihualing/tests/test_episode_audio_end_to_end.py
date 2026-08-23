from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from generate_episode_audio import run_cli  # noqa: E402
from zhixia_tts_client import TTSResult  # noqa: E402
from zhixia_tts_manifest import load_episode_manifest, load_voice_config  # noqa: E402
from zhixia_tts_pipeline import build_generation_plan  # noqa: E402


PROTECTED_PATHS = (
    PROJECT_DIR / "assets" / "audio" / "ep01-flower",
    PROJECT_DIR / "assets" / "audio" / "ep02-wind",
    PROJECT_DIR / "assets" / "audio" / "ep3-moon",
    PROJECT_DIR / "episodes" / "ep01" / "subtitles-flower.json",
    PROJECT_DIR / "episodes" / "ep02" / "subtitles-wind.json",
    PROJECT_DIR / "episodes" / "ep03" / "subtitles-moon.json",
)


def snapshot(paths: tuple[Path, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in paths:
        files = sorted(path.rglob("*")) if path.is_dir() else [path]
        for file_path in files:
            if file_path.is_file():
                relative = file_path.relative_to(PROJECT_DIR).as_posix()
                result[relative] = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return result


def create_project(root: Path) -> None:
    (root / "config").mkdir(parents=True)
    episode_dir = root / "episodes" / "ep04"
    episode_dir.mkdir(parents=True)
    (root / "config" / "voices.json").write_text(
        json.dumps(
            {
                "ayan": {
                    "name": "阿砚",
                    "speaker": "ayan-speaker",
                    "resource_id": "seed-tts-2.0",
                },
                "zhixia": {
                    "name": "栀夏",
                    "speaker": "zhixia-speaker",
                    "resource_id": "seed-tts-2.0",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (episode_dir / "voice-lines.json").write_text(
        json.dumps(
            {
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
                        "start_ms": 600,
                    },
                    {"id": "03-poem-02", "role": "ayan", "text": "空山新雨后。"},
                    {
                        "id": "04-poem-03",
                        "role": "zhixia",
                        "text": "渭城朝雨。",
                        "gap_before_ms": 100,
                    },
                    {
                        "id": "05-outro",
                        "role": "ayan",
                        "text": "第四句，你来接。",
                        "gap_before_ms": 100,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class FakeClient:
    def __init__(self, audio: bytes) -> None:
        self.audio = audio
        self.call_count = 0

    def synthesize(self, request: object) -> TTSResult:
        self.call_count += 1
        return TTSResult(
            audio=self.audio,
            request_id=f"fixture-{self.call_count}",
            message="OK",
        )


class EndToEndTests(unittest.TestCase):
    def test_five_line_generation_is_idempotent_and_preserves_old_episodes(self) -> None:
        before = snapshot(PROTECTED_PATHS)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            create_project(root)
            fixture_path = root / "fixture.mp3"
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=24000:cl=mono",
                    "-t",
                    "0.25",
                    "-b:a",
                    "64k",
                    str(fixture_path),
                ],
                check=True,
            )
            client = FakeClient(fixture_path.read_bytes())
            factory_calls: list[str] = []

            def client_factory(api_key: str) -> FakeClient:
                factory_calls.append(api_key)
                return client

            stdout = io.StringIO()
            stderr = io.StringIO()
            first_code = run_cli(
                ["--episode", "ep04", "--generate"],
                project_root=root,
                client_factory=client_factory,
                input_func=lambda _: "GENERATE ep04",
                stdout=stdout,
                stderr=stderr,
                environ={"VOLCENGINE_SPEECH_API_KEY": "fixture-key"},
            )

            audio_dir = root / "assets" / "audio" / "ep04-rain"
            episode_dir = root / "episodes" / "ep04"
            self.assertEqual(first_code, 0, stderr.getvalue())
            self.assertEqual(client.call_count, 5)
            self.assertEqual(factory_calls, ["fixture-key"])
            self.assertTrue((audio_dir / "01-ayan-opening.mp3").exists())
            self.assertTrue((audio_dir / "05-ayan-outro.mp3").exists())
            self.assertTrue((audio_dir / "audio-metadata.json").exists())
            self.assertTrue((episode_dir / "subtitles-rain.json").exists())

            second_stdout = io.StringIO()
            second_code = run_cli(
                ["--episode", "ep04", "--generate"],
                project_root=root,
                client_factory=lambda _: (_ for _ in ()).throw(
                    AssertionError("ready rerun must not construct client")
                ),
                input_func=lambda _: (_ for _ in ()).throw(
                    AssertionError("ready rerun must not ask for confirmation")
                ),
                stdout=second_stdout,
                stderr=io.StringIO(),
                environ={},
            )

            voices = load_voice_config(root / "config" / "voices.json")
            manifest = load_episode_manifest(
                episode_dir / "voice-lines.json",
                voices,
            )
            second_plan = build_generation_plan(root, manifest)
            self.assertEqual(second_code, 0)
            self.assertEqual(client.call_count, 5)
            self.assertEqual(second_plan.expected_api_calls, 0)
            self.assertIn("预计产生豆包 TTS 调用：0 次", second_stdout.getvalue())

        self.assertEqual(snapshot(PROTECTED_PATHS), before)


if __name__ == "__main__":
    unittest.main()
