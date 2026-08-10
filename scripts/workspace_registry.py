#!/usr/bin/env python3
"""Read the tools-workspace project registry without external dependencies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "project-registry" / "projects.json"
LIFECYCLES = {"core", "active", "incubating", "tooling", "legacy", "offline"}
REQUIRED_FIELDS = {
    "id",
    "path",
    "domain",
    "summary",
    "lifecycle",
    "entry_docs",
    "depends_on",
    "serves",
    "memory_topics",
    "skills",
    "verify",
    "runtime",
    "aliases",
}
LIST_FIELDS = {
    "entry_docs",
    "depends_on",
    "serves",
    "memory_topics",
    "skills",
    "verify",
    "aliases",
}


def load_registry(path: Path | None = None) -> dict[str, Any]:
    """Load the canonical project registry."""
    registry_path = path or DEFAULT_REGISTRY
    return json.loads(registry_path.read_text(encoding="utf-8"))


def _is_safe_relative_path(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def validate_registry(payload: dict[str, Any], workspace_root: Path) -> list[str]:
    """Return every deterministic registry error without changing the workspace."""
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("registry schema_version must be 1")
    projects = payload.get("projects")
    if not isinstance(projects, list):
        return [*errors, "registry projects must be a list"]

    project_ids = [item.get("id") for item in projects if isinstance(item, dict)]
    known_ids = {value for value in project_ids if isinstance(value, str) and value}
    for project_id in sorted(known_ids):
        if project_ids.count(project_id) > 1:
            errors.append(f"duplicate project id: {project_id}")

    for index, project in enumerate(projects):
        if not isinstance(project, dict):
            errors.append(f"project at index {index} must be an object")
            continue
        project_id = project.get("id")
        label = project_id if isinstance(project_id, str) and project_id else f"index {index}"
        missing = sorted(REQUIRED_FIELDS - project.keys())
        for field in missing:
            errors.append(f"{label}: missing field: {field}")
        if missing:
            continue

        for field in ("id", "path", "domain", "summary", "lifecycle"):
            if not isinstance(project[field], str) or not project[field].strip():
                errors.append(f"{label}: {field} must be a non-empty string")
        for field in LIST_FIELDS:
            if not isinstance(project[field], list) or not all(
                isinstance(value, str) for value in project[field]
            ):
                errors.append(f"{label}: {field} must be a string list")

        lifecycle = project["lifecycle"]
        if lifecycle not in LIFECYCLES:
            errors.append(f"{label}: unknown lifecycle: {lifecycle}")

        project_path = project["path"]
        if isinstance(project_path, str) and _is_safe_relative_path(project_path):
            if not (workspace_root / project_path).is_dir():
                errors.append(f"{label}: missing project path: {project_path}")
        else:
            errors.append(f"{label}: unsafe project path: {project_path}")

        if isinstance(project["entry_docs"], list):
            for doc in project["entry_docs"]:
                if not isinstance(doc, str) or not _is_safe_relative_path(doc):
                    errors.append(f"{label}: unsafe entry doc: {doc}")
                elif not (workspace_root / doc).is_file():
                    errors.append(f"{label}: missing entry doc: {doc}")

        if isinstance(project["depends_on"], list):
            for dependency in project["depends_on"]:
                if dependency == project_id:
                    errors.append(f"{label}: self dependency")
                elif dependency not in known_ids:
                    errors.append(f"{label}: unknown dependency: {dependency}")
        if isinstance(project["serves"], list):
            for served in project["serves"]:
                if served not in known_ids:
                    errors.append(f"{label}: unknown served project: {served}")

        runtime = project["runtime"]
        if not isinstance(runtime, dict) or set(runtime) != {"kind", "ports"}:
            errors.append(f"{label}: runtime must contain kind and ports")
        elif not isinstance(runtime["kind"], str) or not isinstance(runtime["ports"], list):
            errors.append(f"{label}: invalid runtime values")
        elif not all(isinstance(port, int) and 0 < port < 65536 for port in runtime["ports"]):
            errors.append(f"{label}: runtime ports must be integers from 1 to 65535")

    return sorted(set(errors))


def get_project(payload: dict[str, Any], project_id: str) -> dict[str, Any]:
    """Return one exact project or raise KeyError."""
    for project in payload.get("projects", []):
        if project.get("id") == project_id:
            return project
    raise KeyError(project_id)


def render_project(project: dict[str, Any]) -> str:
    docs = ", ".join(project["entry_docs"]) or "无"
    dependencies = ", ".join(project["depends_on"]) or "无"
    return "\n".join(
        [
            f"{project['id']} [{project['lifecycle']}]",
            project["summary"],
            f"路径: {project['path']}",
            f"入口文档: {docs}",
            f"依赖: {dependencies}",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--list", action="store_true", help="list all registered projects")
    target.add_argument("--project", help="show one project by exact id")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()

    payload = load_registry()
    errors = validate_registry(payload, ROOT)
    if errors:
        print(json.dumps({"errors": errors}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    projects = payload["projects"]
    if args.list:
        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for project in projects:
                print(render_project(project))
                print()
        return 0

    try:
        project = get_project(payload, args.project)
    except KeyError:
        print(f"unknown project: {args.project}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(project, ensure_ascii=False, indent=2))
    else:
        print(render_project(project))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
