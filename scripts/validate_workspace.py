#!/usr/bin/env python3
"""Validate tools-workspace governance metadata without changing external state."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from search_workspace_wiki import parse_front_matter
from workspace_registry import load_registry, validate_registry


SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".mobileprovision"}
SENSITIVE_NAMES = {".env", ".env.secrets", "id_rsa", "id_ed25519"}
WIKI_TYPES = {"design", "knowledge"}
WIKI_STATUSES = {"draft", "confirmed", "archived"}
SUPPORT_DIRECTORIES = {"docs", "launchd", "logs", "project-registry", "scripts", "tests"}
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def find_sensitive_paths(paths: list[str]) -> list[str]:
    """Return sensitive tracked path names without opening their contents."""
    sensitive: list[str] = []
    for value in paths:
        path = Path(value)
        if path.name == ".env.example" or (
            path.name.startswith(".env.") and path.name.endswith(".example")
        ):
            continue
        if path.name in SENSITIVE_NAMES or path.suffix.casefold() in SENSITIVE_SUFFIXES:
            sensitive.append(value)
    return sorted(set(sensitive))


def tracked_sensitive_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return find_sensitive_paths([line for line in result.stdout.splitlines() if line])


def _wiki_pages(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*.md"))
        if "templates" not in path.relative_to(root).parts and path.name != "README.md"
    ]


def _validate_internal_links(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    for raw_target in MARKDOWN_LINK_PATTERN.findall(text):
        target = raw_target.strip("<>").split("#", 1)[0]
        if not target or "://" in target or target.startswith(("mailto:", "/")):
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            errors.append(f"{path}: broken internal link: {raw_target}")
    return errors


def validate_wiki(root: Path, project_ids: set[str], today: date) -> list[str]:
    """Validate Wiki contracts, references, dates, topics, and local links."""
    errors: list[str] = []
    topics: list[str] = []
    for path in _wiki_pages(root):
        try:
            metadata = parse_front_matter(path)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        page_type = metadata["type"]
        if page_type not in WIKI_TYPES:
            errors.append(f"{path}: unknown wiki type: {page_type}")
        elif page_type not in path.relative_to(root).parts:
            errors.append(f"{path}: type does not match directory: {page_type}")
        status = metadata["status"]
        if status not in WIKI_STATUSES:
            errors.append(f"{path}: unknown wiki status: {status}")
        if not metadata["source"]:
            errors.append(f"{path}: source must not be empty")
        try:
            date.fromisoformat(str(metadata["review_at"]))
        except ValueError:
            errors.append(f"{path}: invalid review_at: {metadata['review_at']}")
        topic = str(metadata["topic"])
        topics.append(topic)
        for project_id in metadata["related_projects"]:
            if project_id not in project_ids:
                errors.append(f"{path}: unknown related project: {project_id}")
        errors.extend(_validate_internal_links(path))

    for topic, count in sorted(Counter(topics).items()):
        if count > 1:
            errors.append(f"duplicate wiki topic: {topic}")
    return sorted(set(errors))


def _discover_top_level_projects(root: Path) -> set[str]:
    return {
        path.name
        for path in root.iterdir()
        if path.is_dir()
        and not path.name.startswith(".")
        and path.name not in SUPPORT_DIRECTORIES
        and (path / "README.md").is_file()
    }


def _validate_readme_coverage(root: Path, project_ids: set[str]) -> list[str]:
    readme = (root / "README.md").read_text(encoding="utf-8")
    return [
        f"README.md does not cover project: {project_id}"
        for project_id in sorted(project_ids)
        if f"`{project_id}`" not in readme
    ]


def _validate_memory_router(root: Path) -> list[str]:
    errors: list[str] = []
    router_path = root / ".cursor" / "rules" / "project-memory.mdc"
    history_path = root / ".cursor" / "rules" / "memory-workspace.mdc"
    if not router_path.is_file():
        errors.append("missing Memory router: .cursor/rules/project-memory.mdc")
        return errors
    if not history_path.is_file():
        errors.append("missing workspace Memory: .cursor/rules/memory-workspace.mdc")
        return errors
    router = router_path.read_text(encoding="utf-8")
    if len(router.encode("utf-8")) >= 6000:
        errors.append("project-memory.mdc must remain below 6000 bytes")
    for target in (
        "memory-python.mdc",
        "memory-infra.mdc",
        "memory-emquant.mdc",
        "memory-english-buddy.mdc",
        "memory-xiaozhi.mdc",
        "memory-workspace.mdc",
    ):
        if target not in router:
            errors.append(f"Memory router does not reference: {target}")
    return errors


def validate_workspace(root: Path = ROOT) -> list[str]:
    """Aggregate all local governance errors in deterministic order."""
    errors: list[str] = []
    try:
        registry = load_registry(root / "project-registry" / "projects.json")
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot load project registry: {exc}"]
    errors.extend(validate_registry(registry, root))
    project_ids = {
        project["id"]
        for project in registry.get("projects", [])
        if isinstance(project, dict) and isinstance(project.get("id"), str)
    }
    discovered = _discover_top_level_projects(root)
    for project_id in sorted(discovered - project_ids):
        errors.append(f"unregistered top-level project: {project_id}")
    for project_id in sorted(project_ids - discovered):
        errors.append(f"registered project is not discoverable: {project_id}")
    errors.extend(validate_wiki(root / "docs" / "wiki", project_ids, date.today()))
    errors.extend(_validate_readme_coverage(root, project_ids))
    errors.extend(_validate_memory_router(root))
    try:
        sensitive = tracked_sensitive_paths(root)
    except subprocess.CalledProcessError as exc:
        errors.append(f"git ls-files failed: {exc}")
    else:
        errors.extend(f"sensitive path is tracked: {path}" for path in sensitive)
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    errors = validate_workspace(args.root.resolve())
    if args.format == "json":
        print(json.dumps({"errors": errors, "ok": not errors}, ensure_ascii=False, indent=2))
    elif errors:
        print("Workspace governance validation failed:")
        for error in errors:
            print(f"- {error}")
    else:
        print("Workspace governance validation passed.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
