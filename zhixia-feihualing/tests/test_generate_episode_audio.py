from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from generate_episode_audio import run_cli  # noqa: E402


def create_project(root: Path) -> None:
    (root / "config").mkdir(parents=True)
    (root / "episodes" / "ep04").mkdir(parents=True)
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
    (root / "episodes" / "ep04" / "voice-lines.json").write_text(
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
                        "start_ms": 2000,
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


class ForbiddenClientFactory:
    def __call__(self, api_key: str) -> object:
        raise AssertionError("preview must not construct a client")


class FailingClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def synthesize(self, request: object) -> object:
        raise RuntimeError(f"fixture failed with {self.api_key}")


class CLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        create_project(self.root)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_command(
        self,
        argv: list[str],
        *,
        input_text: str = "",
        client_factory: object | None = None,
        environ: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        answers = iter(input_text.splitlines())
        code = run_cli(
            argv,
            project_root=self.root,
            client_factory=client_factory or ForbiddenClientFactory(),
            input_func=lambda _: next(answers, ""),
            stdout=stdout,
            stderr=stderr,
            environ=environ or {},
        )
        return code, stdout.getvalue(), stderr.getvalue()

    def test_default_mode_prints_plan_without_constructing_client(self) -> None:
        code, stdout, stderr = self.run_command(["--episode", "ep04"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("预计产生豆包 TTS 调用：5 次", stdout)
        self.assertIn("待生成：5 句", stdout)
        self.assertIn("阿砚：3 句", stdout)
        self.assertIn("栀夏：2 句", stdout)
        self.assertFalse((self.root / "assets").exists())

    def test_generate_requires_exact_confirmation(self) -> None:
        code, stdout, _ = self.run_command(
            ["--episode", "ep04", "--generate"],
            input_text="no\n",
            environ={"VOLCENGINE_SPEECH_API_KEY": "top-secret"},
        )

        self.assertNotEqual(code, 0)
        self.assertIn("已取消", stdout)
        self.assertFalse((self.root / "assets").exists())

    def test_generate_rejects_almost_correct_confirmation(self) -> None:
        code, stdout, _ = self.run_command(
            ["--episode", "ep04", "--generate"],
            input_text="generate ep04\n",
            environ={"VOLCENGINE_SPEECH_API_KEY": "top-secret"},
        )

        self.assertEqual(code, 2)
        self.assertIn("必须完全一致", stdout)

    def test_line_option_previews_only_one_pending_call(self) -> None:
        code, stdout, _ = self.run_command(
            ["--episode", "ep04", "--line", "03-poem-02"]
        )

        self.assertEqual(code, 0)
        self.assertIn("待生成：1 句", stdout)
        self.assertIn("预计产生豆包 TTS 调用：1 次", stdout)
        self.assertIn("03-poem-02", stdout)

    def test_unknown_line_is_rejected_before_client_construction(self) -> None:
        code, _, stderr = self.run_command(
            ["--episode", "ep04", "--line", "99-missing"]
        )

        self.assertEqual(code, 2)
        self.assertIn("清单中不存在", stderr)

    def test_api_key_never_appears_in_output_on_generation_failure(self) -> None:
        code, stdout, stderr = self.run_command(
            ["--episode", "ep04", "--generate"],
            input_text="GENERATE ep04\n",
            client_factory=FailingClient,
            environ={"VOLCENGINE_SPEECH_API_KEY": "top-secret"},
        )

        self.assertEqual(code, 1)
        self.assertIn("生成失败", stderr)
        self.assertNotIn("top-secret", stdout + stderr)

    def test_generate_reads_key_from_project_dotenv(self) -> None:
        (self.root / ".env").write_text(
            "VOLCENGINE_SPEECH_API_KEY=dotenv-secret\n", encoding="utf-8"
        )

        code, stdout, stderr = self.run_command(
            ["--episode", "ep04", "--generate"],
            input_text="GENERATE ep04\n",
            client_factory=FailingClient,
        )

        self.assertEqual(code, 1)
        self.assertNotIn("dotenv-secret", stdout + stderr)

    def test_missing_key_is_reported_only_after_confirmation(self) -> None:
        code, _, stderr = self.run_command(
            ["--episode", "ep04", "--generate"],
            input_text="GENERATE ep04\n",
        )

        self.assertEqual(code, 2)
        self.assertIn("VOLCENGINE_SPEECH_API_KEY", stderr)


if __name__ == "__main__":
    unittest.main()
