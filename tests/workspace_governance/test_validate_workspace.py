from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate_workspace.py"


class ValidateWorkspaceTest(unittest.TestCase):
    def run_python(self, source: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-c", source, *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_sensitive_path_detection_uses_paths_without_reading_contents(self) -> None:
        source = """
import json
import sys
sys.path.insert(0, 'scripts')
from validate_workspace import find_sensitive_paths
print(json.dumps(find_sensitive_paths([
    'safe.txt', 'service/.env', 'service/.env.example',
    'certs/server.pem', 'keys/id_ed25519', 'data/report.json'
])))
"""
        result = self.run_python(source)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            ["certs/server.pem", "keys/id_ed25519", "service/.env"],
        )

    def test_wiki_validation_reports_duplicate_topic_and_unknown_project(self) -> None:
        page_template = """---
title: {title}
type: knowledge
topic: duplicate-topic
aliases: [alias]
tags: [workspace]
scope: workspace
status: confirmed
owner: workspace-maintainer
source: [README.md]
related_projects: [{project}]
review_at: 2026-11-10
---

# {title}
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            wiki_root = Path(temp_dir)
            knowledge = wiki_root / "workspace" / "knowledge"
            knowledge.mkdir(parents=True)
            (knowledge / "one.md").write_text(
                page_template.format(title="One", project="known"), encoding="utf-8"
            )
            (knowledge / "two.md").write_text(
                page_template.format(title="Two", project="missing"), encoding="utf-8"
            )
            source = """
from datetime import date
import json
from pathlib import Path
import sys
sys.path.insert(0, 'scripts')
from validate_workspace import validate_wiki
print(json.dumps(validate_wiki(Path(sys.argv[1]), {'known'}, date(2026, 8, 10))))
"""
            result = self.run_python(source, str(wiki_root))

        self.assertEqual(result.returncode, 0, result.stderr)
        errors = json.loads(result.stdout)
        self.assertTrue(any("duplicate wiki topic: duplicate-topic" in error for error in errors))
        self.assertTrue(any("unknown related project: missing" in error for error in errors))

    def test_wiki_validation_rejects_an_empty_source_list(self) -> None:
        page = """---
title: Untraceable Page
type: knowledge
topic: untraceable-page
aliases: [untraceable]
tags: [workspace]
scope: workspace
status: draft
owner: workspace-maintainer
source: []
related_projects: [known]
review_at: 2026-11-10
---

# Untraceable Page
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            wiki_root = Path(temp_dir)
            knowledge = wiki_root / "workspace" / "knowledge"
            knowledge.mkdir(parents=True)
            (knowledge / "page.md").write_text(page, encoding="utf-8")
            source = """
from datetime import date
import json
from pathlib import Path
import sys
sys.path.insert(0, 'scripts')
from validate_workspace import validate_wiki
print(json.dumps(validate_wiki(Path(sys.argv[1]), {'known'}, date(2026, 8, 10))))
"""
            result = self.run_python(source, str(wiki_root))

        self.assertEqual(result.returncode, 0, result.stderr)
        errors = json.loads(result.stdout)
        self.assertTrue(any("source must not be empty" in error for error in errors), errors)

    def test_real_workspace_passes_the_aggregate_validator(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--format", "json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"errors": [], "ok": True})


if __name__ == "__main__":
    unittest.main()
