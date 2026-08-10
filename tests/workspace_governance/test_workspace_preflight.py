from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "workspace_preflight.py"


class WorkspacePreflightCliTest(unittest.TestCase):
    def run_preflight(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments, "--format", "json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_known_project_returns_minimal_context_paths(self) -> None:
        result = self.run_preflight(
            "--project",
            "stock-ai",
            "--risk",
            "normal",
            "--task",
            "调整公众号热点稿输入",
            "--wiki-query",
            "项目空间",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["project"]["id"], "stock-ai")
        self.assertIn("stock-ai/README.md", payload["recommended_context"]["docs"])
        self.assertIn(
            ".cursor/rules/memory-python.mdc",
            payload["recommended_context"]["memory"],
        )
        self.assertTrue(payload["recommended_context"]["wiki_pages"])
        self.assertNotIn("content", json.dumps(payload, ensure_ascii=False).casefold())

    def test_high_risk_requires_human_gates(self) -> None:
        result = self.run_preflight("--project", "sidestore-infra", "--risk", "high")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("explicit_user_confirmation", payload["required_checks"])
        self.assertIn("independent_review", payload["required_checks"])
        self.assertIn("source_of_truth_refresh", payload["required_checks"])

    def test_unknown_project_is_rejected_without_guessing(self) -> None:
        result = self.run_preflight("--project", "stock", "--risk", "low")

        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown project: stock", result.stderr)


if __name__ == "__main__":
    unittest.main()
