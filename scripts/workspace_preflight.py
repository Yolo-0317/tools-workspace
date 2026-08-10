#!/usr/bin/env python3
"""Build a read-only workspace task preflight from local governance metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from search_workspace_wiki import search_pages
from workspace_registry import get_project, load_registry, validate_registry


RISK_CHECKS = {
    "low": ["relevant_validation"],
    "normal": ["relevant_validation", "review_diff", "preserve_unrelated_changes"],
    "high": [
        "relevant_validation",
        "review_diff",
        "preserve_unrelated_changes",
        "explicit_user_confirmation",
        "independent_review",
        "source_of_truth_refresh",
    ],
}
MEMORY_PATHS = {
    "stock-ai": ".cursor/rules/memory-python.mdc",
    "wechat-mp": ".cursor/rules/memory-python.mdc",
    "infra": ".cursor/rules/memory-infra.mdc",
    "emquant": ".cursor/rules/memory-emquant.mdc",
    "english-buddy": ".cursor/rules/memory-english-buddy.mdc",
    "xiaozhi": ".cursor/rules/memory-xiaozhi.mdc",
    "harryputter": ".cursor/rules/memory-workspace.mdc",
}


def _skill_path(skill: str) -> str:
    root = ROOT / ".cursor" / "skills" / skill
    routing = root / "ROUTING.md"
    if routing.is_file():
        return str(routing.relative_to(ROOT))
    return str((root / "SKILL.md").relative_to(ROOT))


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def build_preflight(
    project: dict[str, Any], risk: str, task: str = "", wiki_query: str = ""
) -> dict[str, Any]:
    """Return local path recommendations without opening or executing them."""
    memory = _unique(
        [MEMORY_PATHS[topic] for topic in project["memory_topics"] if topic in MEMORY_PATHS]
    )
    skills = _unique([_skill_path(skill) for skill in project["skills"]])
    wiki_pages = (
        search_pages(ROOT / "docs" / "wiki", wiki_query) if wiki_query.strip() else []
    )
    return {
        "project": {
            "id": project["id"],
            "path": project["path"],
            "summary": project["summary"],
            "lifecycle": project["lifecycle"],
            "depends_on": project["depends_on"],
        },
        "task": task,
        "risk": risk,
        "recommended_context": {
            "docs": project["entry_docs"],
            "memory": memory,
            "skills": skills,
            "wiki_pages": wiki_pages,
        },
        "verification_commands": project["verify"],
        "required_checks": RISK_CHECKS[risk],
        "guidance": [
            "Read only the recommended paths needed for the task.",
            "Refresh the source of truth for current or external state.",
            "Commands are suggestions and are never executed by preflight.",
        ],
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"项目: {payload['project']['id']} [{payload['project']['lifecycle']}]",
        f"路径: {payload['project']['path']}",
        f"风险: {payload['risk']}",
    ]
    if payload["task"]:
        lines.append(f"任务: {payload['task']}")
    context = payload["recommended_context"]
    for field in ("docs", "memory", "skills"):
        lines.extend(f"- {field}: {value}" for value in context[field])
    lines.extend(
        f"- wiki: {page['title']} ({page['topic']}), needs refresh: {page['needs_source_refresh']}"
        for page in context["wiki_pages"]
    )
    lines.extend(f"- check: {value}" for value in payload["required_checks"])
    lines.extend(f"- verify manually: {value}" for value in payload["verification_commands"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--risk", choices=tuple(RISK_CHECKS), default="normal")
    parser.add_argument("--task", default="")
    parser.add_argument("--wiki-query", default="")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()

    registry = load_registry()
    registry_errors = validate_registry(registry, ROOT)
    if registry_errors:
        print(json.dumps({"errors": registry_errors}, ensure_ascii=False), file=sys.stderr)
        return 1
    try:
        project = get_project(registry, args.project)
    except KeyError:
        print(f"unknown project: {args.project}", file=sys.stderr)
        return 2
    try:
        payload = build_preflight(project, args.risk, args.task, args.wiki_query)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
