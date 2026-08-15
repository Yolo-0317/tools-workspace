# Buy-Point Case Revision Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow repaired point-in-time evidence to create a new immutable v5 case revision for the same logical signal window without overwriting or invalidating legacy artifacts.

**Architecture:** Keep `case_identity` as the stable logical window key and add a content-addressed `revision_identity` computed from the normalized serialized report. The case writer uses the stronger revision identity for filenames, while the threshold-shadow loader validates and prefers it but falls back to `case_identity` for legacy v5 files.

**Tech Stack:** Python 3.12, standard-library `hashlib`/`json`, pytest, existing `CaseReview` report and threshold-shadow CLI modules, MySQL through the existing SQLAlchemy runtime for the final read-only regeneration.

## Global Constraints

- Keep `CASE_REPORT_SCHEMA` exactly `buy-point-case-review-v5`; do not create a v6 schema.
- Keep `case_identity` semantics unchanged.
- Define `revision_identity` as the first 16 lowercase hexadecimal characters of SHA-256 over canonical JSON after removing the top-level `revision_identity` field, using sorted keys, compact separators, UTF-8, and `ensure_ascii=False`.
- New JSON and Markdown filenames use `revision_identity`; existing artifacts are never deleted, renamed, or overwritten.
- Legacy v5 JSON without `revision_identity` remains loadable and uses `case_identity` as downstream lineage.
- Do not modify production selection rules, setup or gate thresholds, portfolio state, advisor memory, notifications, schedules, orders, or MySQL data.
- Preserve unrelated dirty worktree changes, especially `stock_ai/buy_point_selection/reference_cninfo.py` and `tests/unit/test_buy_point_reference_cninfo.py`.
- Use test-driven development for every code change and run the complete buy-point unit regression before claiming completion.

---

### Task 1: Add deterministic report revision identities and immutable revision paths

**Files:**
- Modify: `stock_ai/buy_point_selection/case_report.py:40-53`
- Modify: `stock_ai/buy_point_selection/case_report.py:363-667`
- Modify: `stock_ai/buy_point_selection/case_report.py:879-901`
- Test: `tests/unit/test_buy_point_case_report.py`

**Interfaces:**
- Consumes: existing `case_identity(review, schema=CASE_REPORT_SCHEMA) -> str`, normalized dictionaries returned by `case_payload(review)`, and `_write_exclusive_or_verify(path, content)`.
- Produces: `revision_identity(payload: Mapping[str, object]) -> str`; new `case_payload` dictionaries containing `revision_identity`; JSON and Markdown paths whose suffix is that revision identity.

- [ ] **Step 1: Write failing identity and immutable-path tests**

Add `revision_identity` to the imports from `case_report`, then add these tests to `tests/unit/test_buy_point_case_report.py`:

```python
def test_v5_revision_identity_is_deterministic_and_content_sensitive() -> None:
    review = _review(outcomes=())

    first = case_payload(review)
    repeated = case_payload(review)
    repaired = case_payload(replace(review, risk_coverage_complete=True))

    assert first == repeated
    assert first["case_identity"] == repaired["case_identity"]
    assert first["revision_identity"] == repeated["revision_identity"]
    assert first["revision_identity"] != repaired["revision_identity"]
    assert revision_identity(first) == first["revision_identity"]
    assert revision_identity(repaired) == repaired["revision_identity"]


def test_same_window_repaired_evidence_writes_a_distinct_immutable_revision(
    tmp_path,
) -> None:
    original_review = _review(outcomes=())
    repaired_review = replace(original_review, risk_coverage_complete=True)

    original_paths = write_case_revision(original_review, tmp_path)
    original_bytes = tuple(path.read_bytes() for path in original_paths)
    repaired_paths = write_case_revision(repaired_review, tmp_path)

    original_payload = case_payload(original_review)
    repaired_payload = case_payload(repaired_review)
    assert original_paths != repaired_paths
    assert all(
        original_payload["revision_identity"] in path.name
        for path in original_paths
    )
    assert all(
        repaired_payload["revision_identity"] in path.name
        for path in repaired_paths
    )
    assert all(path.exists() for path in (*original_paths, *repaired_paths))
    assert tuple(path.read_bytes() for path in original_paths) == original_bytes

    assert write_case_revision(original_review, tmp_path) == original_paths
    assert tuple(path.read_bytes() for path in original_paths) == original_bytes
```

- [ ] **Step 2: Run the new tests and verify the red state**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider \
  tests/unit/test_buy_point_case_report.py::test_v5_revision_identity_is_deterministic_and_content_sensitive \
  tests/unit/test_buy_point_case_report.py::test_same_window_repaired_evidence_writes_a_distinct_immutable_revision
```

Expected: collection fails because `revision_identity` does not exist yet, or the assertions fail because payloads and filenames still expose only `case_identity`. Record the exact failure before editing production code.

- [ ] **Step 3: Add the canonical revision hash helper**

Immediately after `case_identity`, add:

```python
def revision_identity(payload: Mapping[str, object]) -> str:
    normalized = dict(payload)
    normalized.pop("revision_identity", None)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
```

This helper is intentionally idempotent for both an unsealed payload and a payload that already contains the matching identity.

- [ ] **Step 4: Seal `case_payload` after all normalized evidence is assembled**

In `case_payload`, replace the exact `return {` line whose next field is `"schema": CASE_REPORT_SCHEMA` with:

```python
    payload: dict[str, object] = {
```

Leave every line inside that existing dictionary unchanged. Immediately after its existing closing brace and before `def render_case_markdown`, insert:

```python
    payload["revision_identity"] = revision_identity(payload)
    return payload
```

- [ ] **Step 5: Use the sealed payload once for both the path and JSON content**

Update `write_case_revision` so hashing and serialization share one payload:

```python
    payload = case_payload(review)
    revision = str(payload["revision_identity"])
    stem = (
        f"{signal_dates[0]:%Y%m%d}_{signal_dates[-1]:%Y%m%d}_"
        f"cutoff-{review.outcome_cutoff:%Y%m%d}_{revision}"
    )
    json_path = target / f"{stem}.json"
    markdown_path = target / f"{stem}.md"
    json_content = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
```

Keep `_write_exclusive_or_verify` unchanged so identical reruns verify existing bytes and different revisions coexist.

- [ ] **Step 6: Run the focused report tests and verify green**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider \
  tests/unit/test_buy_point_case_report.py
```

Expected: all case-report tests pass, including the existing later-cutoff identity test and the two new same-window revision tests.

- [ ] **Step 7: Review and commit Task 1 only**

Run:

```bash
git diff --check -- \
  stock_ai/buy_point_selection/case_report.py \
  tests/unit/test_buy_point_case_report.py
git diff -- \
  stock_ai/buy_point_selection/case_report.py \
  tests/unit/test_buy_point_case_report.py
```

Verify no selection thresholds or unrelated files are present, then commit:

```bash
git add stock_ai/buy_point_selection/case_report.py \
  tests/unit/test_buy_point_case_report.py
git commit -m "feat(stock-ai): version buy-point case revisions"
```

---

### Task 2: Validate strong v5 lineage while preserving legacy fallback

**Files:**
- Modify: `scripts/analysis/review_buy_point_threshold_shadows.py:15-48`
- Modify: `scripts/analysis/review_buy_point_threshold_shadows.py:164-204`
- Test: `tests/unit/test_review_buy_point_threshold_shadows_cli.py`

**Interfaces:**
- Consumes: `revision_identity(payload: Mapping[str, object]) -> str` from Task 1 and existing `load_v5_recall_lineage(path, expected_dates, cutoff) -> V5RecallLineage`.
- Produces: strict validation for present revision identities; `V5RecallLineage.case_identity` containing the strongest available lineage key; unchanged behavior for legacy v5 artifacts without the new field.

- [ ] **Step 1: Add failing tests for preferred lineage, tamper rejection, and malformed IDs**

Import `revision_identity` from `stock_ai.buy_point_selection.case_report`, then add:

```python
def test_v5_lineage_prefers_a_valid_revision_identity(tmp_path: Path) -> None:
    payload = _v5_payload()
    payload["revision_identity"] = revision_identity(payload)
    path = _write_payload(tmp_path / "case.json", payload)

    lineage = load_v5_recall_lineage(path, SIGNAL_DATES, CUTOFF)

    assert lineage.case_identity == payload["revision_identity"]


def test_v5_lineage_rejects_tampered_revision_content(tmp_path: Path) -> None:
    payload = _v5_payload()
    payload["revision_identity"] = revision_identity(payload)
    payload["risk_coverage_complete"] = True
    path = _write_payload(tmp_path / "case.json", payload)

    with pytest.raises(ValueError, match="revision identity mismatch"):
        load_v5_recall_lineage(path, SIGNAL_DATES, CUTOFF)


def test_v5_lineage_rejects_malformed_revision_identity(tmp_path: Path) -> None:
    payload = _v5_payload()
    payload["revision_identity"] = "ABC123"
    path = _write_payload(tmp_path / "case.json", payload)

    with pytest.raises(ValueError, match="revision identity malformed"):
        load_v5_recall_lineage(path, SIGNAL_DATES, CUTOFF)
```

Do not add `revision_identity` to `_v5_payload`; the existing `test_v5_lineage_requires_exact_reconciled_zero_share_rows` remains the explicit legacy-fallback proof and must continue asserting `lineage.case_identity == "v5-case"`.

- [ ] **Step 2: Run the three new tests and verify the red state**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py::test_v5_lineage_prefers_a_valid_revision_identity \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py::test_v5_lineage_rejects_tampered_revision_content \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py::test_v5_lineage_rejects_malformed_revision_identity
```

Expected: the preferred-lineage assertion fails and neither malformed nor tampered payload is rejected by the current loader.

- [ ] **Step 3: Import the report-owned canonical hash helper**

Add this import with the other `stock_ai.buy_point_selection` imports:

```python
from stock_ai.buy_point_selection.case_report import revision_identity
```

- [ ] **Step 4: Validate and select the lineage identity before returning**

After the safe-schema and exact-window checks, insert:

```python
    artifact_revision = payload.get("revision_identity")
    lineage_identity = str(payload["case_identity"])
    if artifact_revision is not None:
        if (
            not isinstance(artifact_revision, str)
            or len(artifact_revision) != 16
            or any(value not in "0123456789abcdef" for value in artifact_revision)
        ):
            raise ValueError("v5 revision identity malformed")
        if revision_identity(payload) != artifact_revision:
            raise ValueError("v5 revision identity mismatch")
        lineage_identity = artifact_revision
```

Keep every existing safety, window, winner-row, reconciliation, and zero-share validation unchanged. Change only the final constructor argument:

```python
    return V5RecallLineage(
        lineage_identity,
        keys,
        bool(payload.get("risk_coverage_complete", False)),
    )
```

- [ ] **Step 5: Run all threshold-shadow CLI tests and verify green**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py
```

Expected: all tests pass; the existing no-revision fixture proves legacy fallback, and the new tests prove strict validation and preferred revision lineage.

- [ ] **Step 6: Run the cross-module focused regression**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider \
  tests/unit/test_buy_point_case_report.py \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py
```

Expected: both producer and consumer suites pass together.

- [ ] **Step 7: Review and commit Task 2 only**

Run:

```bash
git diff --check -- \
  scripts/analysis/review_buy_point_threshold_shadows.py \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py
git diff -- \
  scripts/analysis/review_buy_point_threshold_shadows.py \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py
```

Verify no unrelated worktree paths are staged, then commit:

```bash
git add scripts/analysis/review_buy_point_threshold_shadows.py \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py
git commit -m "fix(stock-ai): validate buy-point case revision lineage"
```

---

### Task 3: Run full regression and regenerate the corrected July 20–24 revision

**Files:**
- Verify only: all `tests/unit/test_(review_)?buy_point*.py` files.
- Generate ignored artifacts only: `output/research/buy_point_cases/20260720_20260724_cutoff-20260731_*.json`
- Generate ignored artifacts only: `output/research/buy_point_cases/20260720_20260724_cutoff-20260731_*.md`

**Interfaces:**
- Consumes: committed report producer and v5 lineage loader, existing legacy artifact `20260720_20260724_cutoff-20260731_da99d57b7b78fc3e.json`, `.env` credentials kept out of logs, and LAN MySQL at `192.168.1.13:3306`.
- Produces: a complete test result, a distinct corrected ignored revision with the same `case_identity`, a valid `revision_identity`, and evidence that the legacy bytes were not changed.

- [ ] **Step 1: Run the complete buy-point unit regression**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q -p no:cacheprovider \
  $(rg --files tests/unit | rg '/test_(review_)?buy_point.*\.py$')
```

Expected: all buy-point tests pass. If unrelated dirty CNINFO tests fail, stop and report the exact pre-existing overlap instead of editing those files within this task.

- [ ] **Step 2: Record the immutable legacy artifact hash and metadata**

Run:

```bash
shasum -a 256 \
  output/research/buy_point_cases/20260720_20260724_cutoff-20260731_da99d57b7b78fc3e.json
PYTHONPATH=. .venv/bin/python -c '
import json
from pathlib import Path
path = Path("output/research/buy_point_cases/20260720_20260724_cutoff-20260731_da99d57b7b78fc3e.json")
payload = json.loads(path.read_text())
print({
    "case_identity": payload["case_identity"],
    "has_revision_identity": "revision_identity" in payload,
    "risk_coverage_complete": payload["risk_coverage_complete"],
})
'
```

Expected: capture the SHA-256 value, legacy `case_identity`, absence of `revision_identity`, and the old incomplete-risk flag without modifying the file.

- [ ] **Step 3: Regenerate one corrected revision against the LAN database**

Build a task-specific URL by parsing `.env` and replacing only host and port; do not print the URL:

```bash
BUY_POINT_CASE_REVISION_MYSQL_URL="$(.venv/bin/python -c "import os; from dotenv import load_dotenv; from sqlalchemy.engine import make_url; load_dotenv('.env'); print(make_url(os.environ['MYSQL_URL']).set(host='192.168.1.13', port=3306).render_as_string(hide_password=False))")"
MYSQL_URL="$BUY_POINT_CASE_REVISION_MYSQL_URL" PYTHONPATH=. .venv/bin/python \
  scripts/analysis/review_buy_point_case.py \
  --signal-start 2026-07-20 \
  --signal-end 2026-07-24 \
  --outcome-cutoff 2026-07-31
unset BUY_POINT_CASE_REVISION_MYSQL_URL
```

Expected: the CLI prints a new JSON/Markdown pair with a suffix different from `da99d57b7b78fc3e`; it must not report `File exists` unless an identical corrected revision already exists and verifies byte-for-byte.

- [ ] **Step 4: Validate coexistence, content identity, and downstream lineage**

Pass the newly printed JSON path as the single argument to this read-only validation:

```bash
PYTHONPATH=. .venv/bin/python -c '
import json, sys
from datetime import date
from pathlib import Path
from scripts.analysis.review_buy_point_threshold_shadows import load_v5_recall_lineage
old_path = Path("output/research/buy_point_cases/20260720_20260724_cutoff-20260731_da99d57b7b78fc3e.json")
new_path = Path(sys.argv[1])
old = json.loads(old_path.read_text())
new = json.loads(new_path.read_text())
lineage = load_v5_recall_lineage(
    new_path,
    tuple(date(2026, 7, day) for day in range(20, 25)),
    date(2026, 7, 31),
)
assert old_path != new_path
assert old["case_identity"] == new["case_identity"]
assert new_path.stem.endswith(new["revision_identity"])
assert new["risk_coverage_complete"] is True
assert lineage.case_identity == new["revision_identity"]
print({
    "old_case_identity": old["case_identity"],
    "new_revision_identity": new["revision_identity"],
    "risk_coverage_complete": new["risk_coverage_complete"],
    "winner_pairs": new["daily_recall_metrics"]["winner_pairs"],
})
' NEW_JSON_PATH
```

Replace `NEW_JSON_PATH` with the exact path printed in Step 3. Expected: all assertions pass and only non-sensitive artifact metadata is printed.

- [ ] **Step 5: Prove the legacy bytes and scoped source tree remain unchanged**

Run the legacy hash command again and compare it with Step 2:

```bash
shasum -a 256 \
  output/research/buy_point_cases/20260720_20260724_cutoff-20260731_da99d57b7b78fc3e.json
git diff --check -- \
  stock_ai/buy_point_selection/case_report.py \
  scripts/analysis/review_buy_point_threshold_shadows.py \
  tests/unit/test_buy_point_case_report.py \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py
git status --short -- \
  stock_ai/buy_point_selection/case_report.py \
  scripts/analysis/review_buy_point_threshold_shadows.py \
  tests/unit/test_buy_point_case_report.py \
  tests/unit/test_review_buy_point_threshold_shadows_cli.py
```

Expected: the old SHA-256 exactly matches Step 2; the four committed code/test paths are clean. Generated case reports remain ignored and are not staged or committed.

- [ ] **Step 6: Report the verified outcome and stop before downstream research**

Report the focused and full test counts, both implementation commit hashes, old and new artifact paths, matching logical `case_identity`, distinct `revision_identity`, risk coverage status, and unchanged legacy SHA-256. Do not automatically rerun threshold, gate, or structure-stop research; the user decides the next manual stage.
