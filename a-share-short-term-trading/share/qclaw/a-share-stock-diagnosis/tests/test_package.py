from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile


SKILL_ROOT = Path(__file__).resolve().parents[1]
PACKAGER = SKILL_ROOT / "scripts" / "package_skill.py"


class PackageSkillTests(unittest.TestCase):
    def test_packager_creates_deterministic_scoped_archive(self) -> None:
        with TemporaryDirectory() as directory:
            output_one = Path(directory) / "one.zip"
            output_two = Path(directory) / "two.zip"
            digests = []
            for output in (output_one, output_two):
                completed = subprocess.run(
                    [sys.executable, str(PACKAGER), "--output", str(output)],
                    cwd=SKILL_ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                digests.append(completed.stdout.strip())
                self.assertEqual(
                    completed.stdout.strip(), hashlib.sha256(output.read_bytes()).hexdigest()
                )

            self.assertEqual(digests[0], digests[1])
            with ZipFile(output_one) as archive:
                names = archive.namelist()
            self.assertIn("a-share-stock-diagnosis/SKILL.md", names)
            self.assertIn("a-share-stock-diagnosis/scripts/diagnose.py", names)
            self.assertFalse(any("__pycache__" in name for name in names))
            self.assertFalse(any(name.endswith(".env") for name in names))
            self.assertFalse(any(name.endswith(".zip") for name in names))


if __name__ == "__main__":
    unittest.main()
