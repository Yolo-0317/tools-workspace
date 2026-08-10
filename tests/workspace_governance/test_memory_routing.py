from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / ".cursor" / "rules" / "project-memory.mdc"
HISTORY = ROOT / ".cursor" / "rules" / "memory-workspace.mdc"


class MemoryRoutingTest(unittest.TestCase):
    def test_global_memory_is_short_and_workspace_history_remains_reachable(self) -> None:
        self.assertTrue(HISTORY.is_file(), "workspace history file is missing")
        router = ROUTER.read_text(encoding="utf-8")
        history = HISTORY.read_text(encoding="utf-8")

        self.assertLess(len(router.encode("utf-8")), 6000)
        self.assertIn("memory-workspace.mdc", router)
        self.assertIn("memory-python.mdc", router)
        self.assertIn("memory-infra.mdc", router)
        self.assertIn("memory-english-buddy.mdc", router)
        self.assertIn("memory-xiaozhi.mdc", router)
        self.assertIn("## 记忆条目（按时间追加）", history)
        self.assertIn("2026-07-31", history)
        self.assertIn("2026-06-07", history)


if __name__ == "__main__":
    unittest.main()
