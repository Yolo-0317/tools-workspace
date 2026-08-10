#!/usr/bin/env python3
"""Search the local tools-workspace Wiki deterministically."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WIKI_ROOT = ROOT / "docs" / "wiki"
REQUIRED_FIELDS = {
    "title",
    "type",
    "topic",
    "aliases",
    "tags",
    "scope",
    "status",
    "owner",
    "source",
    "related_projects",
    "review_at",
}
ARRAY_FIELDS = {"aliases", "tags", "source", "related_projects"}
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _parse_value(raw_value: str, path: Path, key: str) -> str | list[str]:
    value = raw_value.strip()
    if value.startswith("["):
        if not value.endswith("]"):
            raise ValueError(f"{path}: unterminated array for {key}")
        inner = value[1:-1].strip()
        if not inner:
            return []
        values = [item.strip() for item in inner.split(",")]
        if any(not item or item.startswith(("{", "[", "&", "*", "!")) for item in values):
            raise ValueError(f"{path}: unsupported array value for {key}")
        return values
    if not value or value.startswith(("{", "&", "*", "!", "|", ">")):
        raise ValueError(f"{path}: unsupported scalar value for {key}")
    return value


def parse_front_matter(path: Path) -> dict[str, Any]:
    """Parse the restricted flat Front Matter contract used by this Wiki."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"{path}: missing opening front matter delimiter")
    try:
        closing_index = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError(f"{path}: missing closing front matter delimiter") from exc

    metadata: dict[str, Any] = {}
    for line_number, line in enumerate(lines[1:closing_index], start=2):
        if not line.strip():
            continue
        if line[:1].isspace() or ":" not in line:
            raise ValueError(f"{path}:{line_number}: unsupported nested or multiline value")
        key, raw_value = line.split(":", 1)
        if not KEY_PATTERN.fullmatch(key):
            raise ValueError(f"{path}:{line_number}: invalid key: {key}")
        if key in metadata:
            raise ValueError(f"{path}:{line_number}: duplicate key: {key}")
        metadata[key] = _parse_value(raw_value, path, key)

    missing = sorted(REQUIRED_FIELDS - metadata.keys())
    if missing:
        raise ValueError(f"{path}: missing fields: {', '.join(missing)}")
    for field in ARRAY_FIELDS:
        if not isinstance(metadata[field], list):
            raise ValueError(f"{path}: {field} must be an array")
    return metadata


def _summary(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    front_matter_closed = False
    for line in lines[1:]:
        if not front_matter_closed:
            if line == "---":
                front_matter_closed = True
            continue
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def search_pages(
    root: Path, query: str, today: date | None = None
) -> list[dict[str, Any]]:
    """Search topic, title, aliases, and tags without reading external sources."""
    normalized_query = query.strip().casefold()
    if not normalized_query:
        raise ValueError("query must not be empty")
    current_date = today or date.today()
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        if "templates" in relative.parts or path.name == "README.md":
            continue
        metadata = parse_front_matter(path)
        candidates = [
            metadata["topic"],
            metadata["title"],
            *metadata["aliases"],
            *metadata["tags"],
        ]
        normalized_candidates = [str(value).casefold() for value in candidates]
        if normalized_query not in "\n".join(normalized_candidates):
            continue
        rank = 0 if normalized_query in normalized_candidates else 1
        try:
            review_at = date.fromisoformat(str(metadata["review_at"]))
        except ValueError as exc:
            raise ValueError(f"{path}: invalid review_at: {metadata['review_at']}") from exc
        result = {
            **metadata,
            "path": str(relative),
            "summary": _summary(path),
            "needs_source_refresh": metadata["status"] != "confirmed" or review_at < current_date,
        }
        ranked.append((rank, str(metadata["topic"]), result))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--root", type=Path, default=DEFAULT_WIKI_ROOT)
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        results = search_pages(args.root, args.query, args.today)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps({"query": args.query, "results": results}, ensure_ascii=False, indent=2))
    else:
        for result in results:
            refresh = "需要回源" if result["needs_source_refresh"] else "可直接引用"
            print(f"{result['title']} ({result['topic']}) - {refresh}")
            print(f"  {result['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
