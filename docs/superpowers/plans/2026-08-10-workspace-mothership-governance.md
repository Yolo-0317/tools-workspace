# Tools Workspace Mothership Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, read-only governance layer that registers all 17 projects, routes tasks to minimal context, provides a searchable Wiki, and validates repository metadata without changing business runtimes.

**Architecture:** A canonical JSON project registry feeds deterministic Python standard-library query and preflight tools. A small Markdown Wiki adds reviewed cross-project knowledge, while a single validator checks registry, Wiki, README coverage, and tracked sensitive paths. The global Memory rule becomes a short router and preserves its historical body in a non-auto-loaded workspace Memory file.

**Tech Stack:** Python 3 standard library (`argparse`, `datetime`, `json`, `pathlib`, `subprocess`, `unittest`), Markdown, restricted YAML-style Front Matter, JSON.

## Global Constraints

- Do not modify any subproject business logic, service configuration, launchd definition, Docker Compose file, Caddy configuration, or production state.
- Do not move or delete `hp-readalong` or `emquant-sim`; represent them as `legacy` and `offline` only.
- Do not add runtime dependencies, a database, vector search, embeddings, RAG, or a persistent service.
- Governance commands are read-only; they never run registered verification, startup, deployment, or production commands.
- Do not commit `.env`, certificates, subscription links, holdings, or personal Memory content outside the existing tracked Memory migration.
- Preserve every existing entry from `.cursor/rules/project-memory.mdc` when splitting the router from historical workspace Memory.
- User-visible content and repository documentation must not use emoji.
- Existing unrelated working-tree changes must not be staged or edited.

---

### Task 1: Canonical Project Registry and Human Entry Points

**Files:**
- Create: `project-registry/projects.json`
- Create: `project-registry/README.md`
- Create: `scripts/workspace_registry.py`
- Create: `tests/workspace_governance/__init__.py`
- Create: `tests/workspace_governance/test_workspace_registry.py`
- Modify: `README.md`
- Create: `docs/SERVICES.md`

**Interfaces:**
- Produces: `load_registry(path: Path | None = None) -> dict[str, Any]`
- Produces: `validate_registry(payload: dict[str, Any], workspace_root: Path) -> list[str]`
- Produces: `get_project(payload: dict[str, Any], project_id: str) -> dict[str, Any]`
- Command: `python3 scripts/workspace_registry.py --list --format json`
- Command: `python3 scripts/workspace_registry.py --project stock-ai --format text`

- [ ] **Step 1: Write registry failure tests**

```python
class WorkspaceRegistryTest(unittest.TestCase):
    def test_real_registry_contains_exactly_the_17_top_level_projects(self) -> None:
        payload = load_registry()
        self.assertEqual(
            {item["id"] for item in payload["projects"]},
            {
                "a-share-short-term-trading", "cosyvoice-mac", "emquant-sim",
                "english-buddy", "harryputter", "home-hub", "hp-readalong",
                "ollama-hermes", "openrouter-chat", "sidestore-infra",
                "sillytavern-mac", "stock-ai", "stock-mysql", "substore-clash",
                "wechat-cursor-acp", "xiaozhi-atoms3r", "xiaozhi-mac-server",
            },
        )

    def test_validator_rejects_duplicate_id_unknown_lifecycle_and_dependency(self) -> None:
        payload = {"schema_version": 1, "projects": [valid_project("one"), valid_project("one")]}
        payload["projects"][0]["lifecycle"] = "unknown"
        payload["projects"][0]["depends_on"] = ["missing"]
        errors = validate_registry(payload, self.workspace)
        self.assertTrue(any("duplicate project id" in error for error in errors))
        self.assertTrue(any("unknown lifecycle" in error for error in errors))
        self.assertTrue(any("unknown dependency" in error for error in errors))
```

- [ ] **Step 2: Run the focused tests and confirm red**

Run: `python3 -m unittest tests.workspace_governance.test_workspace_registry -v`

Expected: import failure because `scripts/workspace_registry.py` does not exist.

- [ ] **Step 3: Implement strict registry loading and validation**

Implement `scripts/workspace_registry.py` with these constants and rules:

```python
LIFECYCLES = {"core", "active", "incubating", "tooling", "legacy", "offline"}
REQUIRED_FIELDS = {
    "id", "path", "domain", "summary", "lifecycle", "entry_docs",
    "depends_on", "serves", "memory_topics", "skills", "verify",
    "runtime", "aliases",
}
```

Validation must accumulate errors instead of failing at the first error; reject missing fields, duplicate IDs, unknown lifecycle values, absent project paths, absent entry docs, unknown dependency/service references, and self-dependencies. CLI exit code is `0` for valid output, `2` for invalid arguments or unknown projects, and `1` for registry validation failure.

- [ ] **Step 4: Populate the 17-project registry**

Use the lifecycle mapping approved in the design:

```text
core: stock-ai, stock-mysql, home-hub, wechat-cursor-acp, sidestore-infra, substore-clash
active: english-buddy, harryputter, xiaozhi-atoms3r, xiaozhi-mac-server
incubating: a-share-short-term-trading
tooling: cosyvoice-mac, ollama-hermes, openrouter-chat, sillytavern-mac
legacy: hp-readalong
offline: emquant-sim
```

Record only paths, ports, commands, aliases, dependencies, Memory topics, and Skills supported by existing repository documents. Use empty arrays when a fact is not documented.

- [ ] **Step 5: Run registry tests and confirm green**

Run: `python3 -m unittest tests.workspace_governance.test_workspace_registry -v`

Expected: all registry unit tests pass and `--list --format json` reports 17 projects.

- [ ] **Step 6: Rewrite root README and add service catalog**

Make `README.md` the workspace entry point with: safety boundary, five-minute routing flow, all 17 projects grouped by domain, dependency overview, governance commands, lifecycle meanings, and links to project docs. Remove service credentials, direct subscription URLs, and stale one-off operational detail.

Create `docs/SERVICES.md` with documented service metadata only. Every row must say it describes repository configuration, not current runtime health.

- [ ] **Step 7: Verify Task 1 and commit**

Run:

```bash
python3 -m unittest tests.workspace_governance.test_workspace_registry -v
python3 scripts/workspace_registry.py --list --format json
git diff --check
```

Expected: tests pass, registry reports 17 projects, and no whitespace errors exist.

Commit:

```bash
git add README.md docs/SERVICES.md project-registry scripts/workspace_registry.py tests/workspace_governance
git commit -m "feat: add workspace project registry"
```

### Task 2: Searchable Wiki and Read-Only Preflight

**Files:**
- Create: `docs/wiki/README.md`
- Create: `docs/wiki/templates/design.md`
- Create: `docs/wiki/templates/knowledge.md`
- Create: `docs/wiki/workspace/knowledge/project-landscape.md`
- Create: `docs/wiki/workspace/knowledge/service-topology.md`
- Create: `scripts/search_workspace_wiki.py`
- Create: `scripts/workspace_preflight.py`
- Create: `tests/workspace_governance/test_search_workspace_wiki.py`
- Create: `tests/workspace_governance/test_workspace_preflight.py`
- Modify: `README.md`
- Modify: `project-registry/README.md`

**Interfaces:**
- Consumes: `load_registry()` and `get_project()` from Task 1
- Produces: `parse_front_matter(path: Path) -> dict[str, Any]`
- Produces: `search_pages(root: Path, query: str, today: date | None = None) -> list[dict[str, Any]]`
- Produces: `build_preflight(project: dict[str, Any], risk: str, task: str, wiki_query: str = "") -> dict[str, Any]`
- Command: `python3 scripts/search_workspace_wiki.py --query "服务地图" --format json`
- Command: `python3 scripts/workspace_preflight.py --project stock-ai --risk normal --task "调整选股" --format json`

- [ ] **Step 1: Write Wiki search failure tests**

```python
class WorkspaceWikiSearchTest(unittest.TestCase):
    def test_alias_search_marks_confirmed_current_page_as_directly_usable(self) -> None:
        results = search_pages(self.wiki_root, "服务地图", today=date(2026, 8, 10))
        self.assertEqual(results[0]["topic"], "workspace-service-topology")
        self.assertFalse(results[0]["needs_source_refresh"])

    def test_draft_and_expired_pages_require_source_refresh(self) -> None:
        draft = search_pages(self.wiki_root, "draft-alias", today=date(2026, 8, 10))[0]
        expired = search_pages(self.wiki_root, "expired-alias", today=date(2026, 8, 10))[0]
        self.assertTrue(draft["needs_source_refresh"])
        self.assertTrue(expired["needs_source_refresh"])
```

- [ ] **Step 2: Run Wiki tests and confirm red**

Run: `python3 -m unittest tests.workspace_governance.test_search_workspace_wiki -v`

Expected: import failure because the search module does not exist.

- [ ] **Step 3: Implement restricted Front Matter parsing and deterministic search**

The parser accepts only:

```text
key: scalar text
key: [string one, string two]
```

Reject duplicate keys, nested objects, multiline lists, YAML anchors, custom tags, missing closing `---`, and missing required fields. Search is case-insensitive over `topic`, `title`, `aliases`, and `tags`; exact matches rank before substring matches, then results sort by topic. A page is directly usable only when `status == "confirmed"` and `review_at >= today`.

- [ ] **Step 4: Add Wiki contract, templates, and two confirmed workspace pages**

Both pages use `review_at: 2026-11-10`, cite repository-relative source files, avoid runtime claims, and explain when to re-read the project registry or source README. Templates use non-valid example values under `docs/wiki/templates/` and the searcher skips the templates directory.

- [ ] **Step 5: Write preflight failure tests**

```python
class WorkspacePreflightTest(unittest.TestCase):
    def test_known_project_returns_minimal_context_without_reading_it(self) -> None:
        payload = self.run_preflight("--project", "stock-ai", "--risk", "normal")
        self.assertEqual(payload["project"]["id"], "stock-ai")
        self.assertIn("stock-ai/README.md", payload["recommended_context"]["docs"])
        self.assertNotIn("content", json.dumps(payload))

    def test_high_risk_adds_human_gates_and_unknown_project_fails(self) -> None:
        high = self.run_preflight("--project", "sidestore-infra", "--risk", "high")
        self.assertIn("explicit_user_confirmation", high["required_checks"])
        unknown = self.run_raw("--project", "missing")
        self.assertEqual(unknown.returncode, 2)
```

- [ ] **Step 6: Implement the read-only preflight**

Use exact risk checks:

```python
RISK_CHECKS = {
    "low": ["relevant_validation"],
    "normal": ["relevant_validation", "review_diff", "preserve_unrelated_changes"],
    "high": [
        "relevant_validation", "review_diff", "preserve_unrelated_changes",
        "explicit_user_confirmation", "independent_review", "source_of_truth_refresh",
    ],
}
```

Preflight returns paths and metadata only. It must not open referenced docs, run `verify`, inspect external state, or infer an unknown project from free text.

- [ ] **Step 7: Verify Task 2 and commit**

Run:

```bash
python3 -m unittest tests.workspace_governance.test_search_workspace_wiki -v
python3 -m unittest tests.workspace_governance.test_workspace_preflight -v
python3 scripts/search_workspace_wiki.py --query "服务地图" --format json
python3 scripts/workspace_preflight.py --project stock-ai --risk normal --format json
git diff --check
```

Expected: all focused tests pass; Wiki and preflight output valid JSON; no command changes external state.

Commit:

```bash
git add README.md project-registry/README.md docs/wiki scripts/search_workspace_wiki.py scripts/workspace_preflight.py tests/workspace_governance
git commit -m "feat: add workspace wiki and preflight"
```

### Task 3: Lossless Memory Routing and Aggregate Governance Validation

**Files:**
- Modify: `.cursor/rules/project-memory.mdc`
- Create: `.cursor/rules/memory-workspace.mdc`
- Create: `scripts/validate_workspace.py`
- Create: `tests/workspace_governance/test_validate_workspace.py`
- Create: `tests/workspace_governance/test_memory_routing.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/wiki/README.md`

**Interfaces:**
- Consumes: `validate_registry()` from Task 1 and Front Matter parsing from Task 2
- Produces: `validate_workspace(root: Path) -> list[str]`
- Produces: `validate_wiki(root: Path, project_ids: set[str], today: date) -> list[str]`
- Produces: `tracked_sensitive_paths(root: Path) -> list[str]`
- Command: `python3 scripts/validate_workspace.py --format text`
- Command: `python3 scripts/validate_workspace.py --format json`

- [ ] **Step 1: Write aggregate validation and Memory-routing failure tests**

```python
class MemoryRoutingTest(unittest.TestCase):
    def test_global_memory_is_a_short_router_and_history_is_preserved(self) -> None:
        router = (ROOT / ".cursor/rules/project-memory.mdc").read_text(encoding="utf-8")
        history = (ROOT / ".cursor/rules/memory-workspace.mdc").read_text(encoding="utf-8")
        self.assertLess(len(router.encode("utf-8")), 6000)
        self.assertIn("memory-workspace.mdc", router)
        self.assertIn("2026-07-31", history)

class ValidateWorkspaceTest(unittest.TestCase):
    def test_real_workspace_passes_all_governance_checks(self) -> None:
        self.assertEqual(validate_workspace(ROOT), [])

    def test_sensitive_tracked_paths_are_reported(self) -> None:
        paths = ["safe.txt", "service/.env", "certs/server.pem"]
        self.assertEqual(find_sensitive_paths(paths), ["certs/server.pem", "service/.env"])
```

- [ ] **Step 2: Run Task 3 tests and confirm red**

Run:

```bash
python3 -m unittest tests.workspace_governance.test_memory_routing -v
python3 -m unittest tests.workspace_governance.test_validate_workspace -v
```

Expected: failures because the split Memory file and aggregate validator do not exist.

- [ ] **Step 3: Split Memory without losing content**

Keep the existing front matter and topic index in `project-memory.mdc`, update its project overview to all 17 projects, and replace detailed chronological entries with a pointer to `.cursor/rules/memory-workspace.mdc`. Move those entries verbatim into `memory-workspace.mdc` under front matter with `alwaysApply: false`. Do not rewrite or summarize historical entries during the move.

The router must retain direct mappings for `memory-python.mdc`, `memory-infra.mdc`, `memory-emquant.mdc`, `memory-english-buddy.mdc`, `memory-xiaozhi.mdc`, and `memory-workspace.mdc`.

- [ ] **Step 4: Implement aggregate validator**

Validation includes:

```python
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".mobileprovision"}
SENSITIVE_NAMES = {".env", ".env.secrets", "id_rsa", "id_ed25519"}
```

Allow tracked example files matching `.env.example` or `.env.*.example`. Obtain tracked paths using `git ls-files` with `subprocess.run(..., check=True, capture_output=True, text=True)`; never read file contents. Aggregate registry errors, Wiki contract errors, README coverage gaps, invalid project references, and sensitive tracked paths into deterministic sorted output.

- [ ] **Step 5: Update routing instructions**

Update `AGENTS.md` and root README so agents use this sequence:

```text
project registry / preflight
  -> project entry docs
  -> at most one relevant Memory
  -> one matching Skill or routing page
  -> source-of-truth refresh only when freshness or risk requires it
```

Preserve the existing requirements about no emoji, design before new features, relevant verification, and sensitive data.

- [ ] **Step 6: Run full governance verification**

Run:

```bash
python3 -m unittest discover -s tests/workspace_governance -v
python3 scripts/validate_workspace.py --format text
python3 scripts/workspace_registry.py --list --format json
python3 scripts/search_workspace_wiki.py --query "项目空间" --format json
python3 scripts/workspace_preflight.py --project stock-ai --risk normal --format json
git diff --check
```

Expected: all governance tests pass, aggregate validator reports zero errors, registry reports 17 projects, Wiki search returns the project landscape, and preflight returns only local metadata.

- [ ] **Step 7: Review scope and commit**

Run:

```bash
git status --short
git diff --name-only
git diff --stat
```

Expected: only governance files from the three tasks are included; no business code, service configuration, credentials, or unrelated changes appear.

Commit:

```bash
git add AGENTS.md README.md .cursor/rules/project-memory.mdc .cursor/rules/memory-workspace.mdc docs/wiki scripts/validate_workspace.py tests/workspace_governance
git commit -m "feat: add workspace governance validation"
```
