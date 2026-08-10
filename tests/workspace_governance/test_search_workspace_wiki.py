from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "search_workspace_wiki.py"


CONFIRMED_PAGE = """---
title: 项目空间服务拓扑
type: knowledge
topic: workspace-service-topology
aliases: [服务地图, 端口地图]
tags: [workspace, infrastructure]
scope: workspace
status: confirmed
owner: workspace-maintainer
source: [README.md, docs/SERVICES.md]
related_projects: [sidestore-infra, home-hub]
review_at: 2026-11-10
---

# 项目空间服务拓扑
"""


class WorkspaceWikiSearchCliTest(unittest.TestCase):
    def run_search(self, page_text: str, query: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            wiki_root = Path(temp_dir)
            page = wiki_root / "workspace" / "knowledge" / "service-topology.md"
            page.parent.mkdir(parents=True)
            page.write_text(page_text, encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--root",
                    str(wiki_root),
                    "--query",
                    query,
                    "--today",
                    "2026-08-10",
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_alias_search_marks_current_confirmed_page_as_directly_usable(self) -> None:
        result = self.run_search(CONFIRMED_PAGE, "服务地图")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["results"][0]["topic"], "workspace-service-topology")
        self.assertFalse(payload["results"][0]["needs_source_refresh"])

    def test_draft_and_expired_pages_require_source_refresh(self) -> None:
        draft_page = CONFIRMED_PAGE.replace("status: confirmed", "status: draft")
        expired_page = CONFIRMED_PAGE.replace("review_at: 2026-11-10", "review_at: 2026-08-09")

        for page_text in (draft_page, expired_page):
            with self.subTest(page_text=page_text):
                result = self.run_search(page_text, "服务地图")
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertTrue(payload["results"][0]["needs_source_refresh"])


if __name__ == "__main__":
    unittest.main()
