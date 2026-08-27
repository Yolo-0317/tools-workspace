# WeChat Originality Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce originality-oriented preflight gates before WeChat draft mutations, then use the gate to produce today's social hotspot longform without publishing it automatically.

**Architecture:** Add one focused, side-effect-free originality module that builds structured reports from content, image metadata, plot anchors, and publication history. Wire it into the virtual-lifestyle newspic CLI and Codex hotspot loader so failures occur before image upload or WeChat API calls. Keep film-longform validation callable independently until a dedicated film-longform publisher is added.

**Tech Stack:** Python 3.12, dataclasses, `difflib`, SHA-256, pytest, existing WeChat draft CLIs.

## Global Constraints

- Film lanes and `nonfilm_hotspot` cannot publish through `virtual_lifestyle` / newspic.
- Zhixia newspics allow only original images, at least 400 cleaned characters, at least three specificity markers across two categories, and no duplicate image content or URL.
- Similarity threshold is `0.78` over published records from the prior 14 days.
- The same film may be published at most once in 30 days.
- Film longforms require at least 1800 cleaned characters and two complete verifiable plot anchors.
- Every failure occurs before image upload and WeChat API mutation.
- This task does not automatically publish or push the article; draft push requires a later explicit user request.

---

### Task 1: Pure originality report engine

**Files:**
- Create: `scripts/tools/wechat_mp_originality.py`
- Create: `tests/unit/test_wechat_mp_originality.py`

**Interfaces:**
- Produces: `OriginalityReport`, `evaluate_zhixia_newspic(...)`, `evaluate_hotspot_longform(...)`, `evaluate_film_longform(...)`, `format_originality_report(...)`.

- [ ] Write failing tests for route rejection, 399/400 character boundary, specificity, original image ratio, duplicate file hashes, duplicate image URLs, 14-day title similarity, 30-day film duplication, hotspot length/sources, and film plot anchors.
- [ ] Run `uv run pytest tests/unit/test_wechat_mp_originality.py -q` and verify failures are caused by the missing module.
- [ ] Implement the immutable report model and pure evaluators with explicit failure codes and no network or file mutation beyond reading supplied files.
- [ ] Re-run the focused tests and verify all pass.

### Task 2: Enforce gates before mutations

**Files:**
- Modify: `scripts/tools/wechat_mp_newspic_draft.py`
- Modify: `scripts/tools/wechat_mp_codex_hotspot.py`
- Modify: `scripts/tools/wechat_mp_draft.py`
- Test: `tests/unit/test_wechat_mp_newspic.py`
- Test: `tests/unit/test_wechat_mp_codex_hotspot.py`

**Interfaces:**
- Consumes: Task 1 evaluators.
- Produces: `validate_codex_hotspot_originality(draft, history=...) -> OriginalityReport` and pre-mutation newspic enforcement.

- [ ] Write failing integration tests proving film/nonfilm-hotspot newspics and low-originality hotspot JSON stop before uploader/client calls.
- [ ] Run the exact failing test nodes and verify expected gate errors.
- [ ] Add the smallest wiring needed to evaluate and print reports before `_preflight_before_mutation` and before hotspot article construction.
- [ ] Re-run focused tests and the complete affected test files.

### Task 3: Low-creation replay and documentation

**Files:**
- Create: `tests/fixtures/wechat_mp_low_creation_replays.json`
- Modify: `.cursor/skills/wechat-mp-virtual-lifestyle/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`

**Interfaces:**
- Consumes: Task 1 report engine.
- Produces: regression fixtures for the six observed risk patterns and updated workflow rules.

- [ ] Add replay fixtures for short text, non-original visuals, repeated film, duplicate image URL, and generic low-specificity copy.
- [ ] Add a parametrized test that rejects every replay for at least one explicit reason.
- [ ] Update routing docs: film goes to longform; Zhixia newspic is original-only; hotspot longform prints an originality report.
- [ ] Run replay tests and `git diff --check`.

### Task 4: Today's hotspot longform under the new gate

**Files:**
- Create: `output/hotspot_codex_<topic>_20260813.json`

**Interfaces:**
- Consumes: official/reputable web sources and Task 2 hotspot gate.
- Produces: one 2000–3200-character social hotspot longform JSON ready for dry-run.

- [ ] Search today's trends and verify one topic through at least three traceable sources, including at least one primary or official source when available.
- [ ] Draft a pure-paragraph article with at least four verifiable facts and a clear original thesis.
- [ ] Run the new originality report and existing hotspot dry-run.
- [ ] Revise until both gates pass; do not remove failures by lowering thresholds.
- [ ] Report the title, length, sources, originality report, and dry-run result. Do not push the draft without a new explicit request.

### Task 5: Final verification

**Files:**
- Verify only.

- [ ] Run `uv run pytest tests/unit/test_wechat_mp_originality.py tests/unit/test_wechat_mp_codex_hotspot.py tests/unit/test_wechat_mp_newspic.py -q`.
- [ ] Run `git diff --check` on modified files.
- [ ] Confirm `data/wechat_mp_draft_slots.json` was not modified by this task and no WeChat mutation command was run.
