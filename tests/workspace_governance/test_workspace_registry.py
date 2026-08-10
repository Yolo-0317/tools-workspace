from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "workspace_registry.py"
sys.path.insert(0, str(ROOT / "scripts"))

import workspace_registry


class WorkspaceRegistryCliTest(unittest.TestCase):
    def test_list_returns_the_17_top_level_projects(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--list", "--format", "json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(
            {item["id"] for item in payload["projects"]},
            {
                "a-share-short-term-trading",
                "cosyvoice-mac",
                "emquant-sim",
                "english-buddy",
                "harryputter",
                "home-hub",
                "hp-readalong",
                "ollama-hermes",
                "openrouter-chat",
                "sidestore-infra",
                "sillytavern-mac",
                "stock-ai",
                "stock-mysql",
                "substore-clash",
                "wechat-cursor-acp",
                "xiaozhi-atoms3r",
                "xiaozhi-mac-server",
            },
        )


class WorkspaceRegistryValidationTest(unittest.TestCase):
    def test_real_registry_is_valid(self) -> None:
        self.assertTrue(hasattr(workspace_registry, "validate_registry"))
        errors = workspace_registry.validate_registry(workspace_registry.load_registry(), ROOT)
        self.assertEqual(errors, [])

    def test_validation_accumulates_structural_and_reference_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project_dir = workspace / "one"
            project_dir.mkdir()
            (project_dir / "README.md").write_text("# one\n", encoding="utf-8")
            project = {
                "id": "one",
                "path": "one",
                "domain": "test",
                "summary": "test project",
                "lifecycle": "unknown",
                "entry_docs": ["one/missing.md"],
                "depends_on": ["one", "missing"],
                "serves": ["missing"],
                "memory_topics": [],
                "skills": [],
                "verify": [],
                "runtime": {"kind": "cli", "ports": []},
                "aliases": [],
            }
            payload = {"schema_version": 1, "projects": [project, dict(project)]}

            self.assertTrue(hasattr(workspace_registry, "validate_registry"))
            errors = workspace_registry.validate_registry(payload, workspace)

        expected_fragments = (
            "duplicate project id: one",
            "one: unknown lifecycle: unknown",
            "one: missing entry doc: one/missing.md",
            "one: self dependency",
            "one: unknown dependency: missing",
            "one: unknown served project: missing",
        )
        for fragment in expected_fragments:
            with self.subTest(fragment=fragment):
                self.assertTrue(any(fragment in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
