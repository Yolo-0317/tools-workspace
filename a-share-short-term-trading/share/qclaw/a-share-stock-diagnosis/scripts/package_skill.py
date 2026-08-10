#!/usr/bin/env python3
"""Create a deterministic, secret-free ZIP of this QClaw Skill."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


SKILL_ROOT = Path(__file__).resolve().parents[1]
INCLUDED_ROOTS = (
    SKILL_ROOT / "SKILL.md",
    SKILL_ROOT / "README.md",
    SKILL_ROOT / ".gitignore",
    SKILL_ROOT / "data",
    SKILL_ROOT / "scripts",
    SKILL_ROOT / "a_share_stock_diagnosis",
    SKILL_ROOT / "tests",
)
EXCLUDED_PARTS = frozenset({".git", ".cache", "__pycache__", ".pytest_cache"})
EXCLUDED_SUFFIXES = frozenset({".pyc", ".pyo", ".log", ".zip", ".env"})


def _included_files() -> list[Path]:
    files: list[Path] = []
    for root in INCLUDED_ROOTS:
        candidates = [root] if root.is_file() else root.rglob("*")
        for candidate in candidates:
            relative = candidate.relative_to(SKILL_ROOT)
            if not candidate.is_file():
                continue
            if any(part in EXCLUDED_PARTS for part in relative.parts):
                continue
            if candidate.suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            files.append(candidate)
    return sorted(set(files), key=lambda item: item.relative_to(SKILL_ROOT).as_posix())


def build_archive(output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for source in _included_files():
            relative = source.relative_to(SKILL_ROOT)
            info = ZipInfo(f"a-share-stock-diagnosis/{relative.as_posix()}")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes())
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="打包 QClaw A 股诊断 Skill")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(build_archive(args.output.expanduser().resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
