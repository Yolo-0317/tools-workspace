# Zhixia Film Plot Anchors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make single-film Zhixia image posts derive their observations from verified plot scenes instead of interchangeable movie themes.

**Architecture:** Extend the existing film topic-card validator with a small, explicit writing-mode and plot-anchor schema, then make copy validation require anchor evidence in the body. Keep the generic newspic CLI unchanged because it already routes film cards and copy through `wechat_mp_virtual_film.py`; update the writing skill and the existing film design so human drafting follows the same contract.

**Tech Stack:** Python 3, pytest, JSON topic cards, Markdown skill documentation.

## Global Constraints

- Single-film posts default to `scene_focus`; `character_arc` is opt-in and `trailer_observation` is mandatory for `announced` and `presale` films.
- `scene_focus` needs two distinct anchors, `character_arc` needs two anchors with distinct stages, and `trailer_observation` needs one official-material anchor.
- Plot and its direct causal chain should occupy about 60% of the copy; analysis should occupy about 40%. This remains a human editorial check, not a character-count heuristic.
- The first plot anchor must appear within the first two non-empty paragraphs.
- The replacement-film test remains a human editorial gate.
- Existing title, image-count, length, spoiler, fake-viewing, hype, image-rights, and AI-disclosure rules remain active.
- `classic_list` keeps its existing behavior and does not require single-film plot anchors.
- Existing published posts and ledger records are not migrated.
- Preserve unrelated working-tree changes and stage only files named by each task.

---

### Task 1: Topic-card plot-anchor schema

**Files:**
- Modify: `stock-ai/tests/unit/test_wechat_mp_virtual_film.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_virtual_film.py`

**Interfaces:**
- Consumes: `validate_film_topic_card(card: Mapping[str, Any]) -> dict[str, Any]`
- Produces: normalized `film_writing_mode: str` and `plot_anchors: list[dict[str, str]]`

- [ ] **Step 1: Add valid anchor fixtures to the test card helper**

Add a helper that returns two concrete scene anchors and make `film_card()` include:

```python
"film_writing_mode": "scene_focus",
"plot_anchors": plot_anchors(),
```

Each anchor contains `scene`, `character`, `action`, `counterpart_or_pressure`, `consequence`, `source_url`, and `stage`; the two anchors use distinct action and consequence phrases.

- [ ] **Step 2: Write failing topic-card tests**

Add focused tests proving that:

```python
def test_scene_focus_requires_two_plot_anchors() -> None: ...
def test_plot_anchor_requires_action_consequence_and_https_source() -> None: ...
def test_character_arc_requires_distinct_stages() -> None: ...
def test_announced_film_requires_trailer_observation() -> None: ...
def test_classic_list_does_not_require_single_film_anchors() -> None: ...
```

The first four must assert the relevant `ValueError` message; the list test removes both new fields and must still normalize successfully.

- [ ] **Step 3: Run the new tests and verify RED**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest tests/unit/test_wechat_mp_virtual_film.py -q
```

Expected: the new validation tests fail because writing modes and plot anchors are not yet required.

- [ ] **Step 4: Implement the minimal schema validation**

In `wechat_mp_virtual_film.py` add:

```python
FILM_WRITING_MODES = ("scene_focus", "character_arc", "trailer_observation")
PLOT_ANCHOR_FIELDS = (
    "scene",
    "character",
    "action",
    "counterpart_or_pressure",
    "consequence",
    "source_url",
    "stage",
)
```

Add `_normalize_plot_anchors(card, writing_mode)` that strips every value, rejects missing fields, requires `source_url.startswith("https://")`, enforces mode-specific counts, and checks distinct `stage` values for `character_arc`. In `validate_film_topic_card`, skip this schema only for `classic_list`; otherwise require the explicit fields, reject `announced` or `presale` unless the mode is `trailer_observation`, and reject `trailer_observation` for `evergreen` content.

- [ ] **Step 5: Run the unit file and verify GREEN**

Run the same pytest command. Expected: all tests in `test_wechat_mp_virtual_film.py` pass.

### Task 2: Copy-to-anchor evidence gate

**Files:**
- Modify: `stock-ai/tests/unit/test_wechat_mp_virtual_film.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_virtual_film.py`

**Interfaces:**
- Consumes: normalized `plot_anchors` from Task 1
- Produces: `validate_film_copy(...) -> str` that rejects copy detached from its selected scenes

- [ ] **Step 1: Make existing valid-copy fixtures include anchor evidence**

Change `valid_copy()` so ordinary valid bodies contain the two fixture action/consequence phrases before padding. Tests that intentionally pass raw repeated text must set `content_lane="classic_list"` or supply explicit anchor evidence, so they continue testing only their named behavior.

- [ ] **Step 2: Write failing copy-gate tests**

Add:

```python
def test_scene_focus_copy_requires_two_anchor_evidence_hits() -> None: ...
def test_first_anchor_must_appear_in_first_two_paragraphs() -> None: ...
def test_trailer_observation_rejects_result_language() -> None: ...
def test_copy_with_two_plot_anchors_passes() -> None: ...
```

Use real Chinese action and consequence phrases in both card and copy. The result-language case contains `最终` or `结局证明` and uses `release_status="announced"`.

- [ ] **Step 3: Run the copy tests and verify RED**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest tests/unit/test_wechat_mp_virtual_film.py -q
```

Expected: the three rejection tests fail because copy-to-anchor matching does not exist.

- [ ] **Step 4: Implement minimal evidence matching**

For each anchor, treat `action` and `consequence` as evidence phrases and count the anchor as present when either complete phrase occurs in the normalized copy. Require two distinct anchors for `scene_focus` and `character_arc`, one for `trailer_observation`, and require at least one matching phrase in the first two non-empty paragraphs. Add a small tuple of prohibited result-language phrases for `trailer_observation`, initially `("最终", "结局证明", "到最后")`.

Error messages must separately identify insufficient anchor evidence, late first anchor, and prohibited trailer-result language.

- [ ] **Step 5: Run the unit file and verify GREEN**

Run the same pytest command. Expected: all film unit tests pass.

### Task 3: Editorial rules and existing single-film design

**Files:**
- Modify: `.cursor/skills/wechat-mp-virtual-lifestyle/SKILL.md`
- Modify: `stock-ai/docs/superpowers/specs/2026-08-12-zhixia-welcome-to-dragon-restaurant-film-design.md`

**Interfaces:**
- Consumes: `film_writing_mode` and `plot_anchors` schema from Task 1
- Produces: author-facing instructions matching the executable validator

- [ ] **Step 1: Update the dual-film-column rules**

Add the three writing modes and the default flow:

```text
剧情锚点 → 人物选择 → 关系或处境变化 → 栀夏观察
```

State that the opening reaches a verified scene within two paragraphs, plot plus causality is roughly 60%, images follow scene/action/response/consequence, and replacement-film test failures are rewritten.

- [ ] **Step 2: Update the topic-card field list and execution checklist**

Require `film_writing_mode` and `plot_anchors` for single films, document the seven anchor fields, exempt `classic_list`, and state that `announced` and `presale` must use `trailer_observation`.

- [ ] **Step 3: Correct the Dragon Restaurant design conflict**

Replace “剧情事实所占篇幅不超过全文三分之一” with “剧情及其直接因果约占全文六成”; require two verified anchors from one scene or a connected action-response chain. Remove any wording that allows the article to rely only on character premise and publicity labels.

- [ ] **Step 4: Check documentation consistency**

Run:

```bash
rg -n "三分之一|film_writing_mode|plot_anchors|换片测试|预告观察" \
  .cursor/skills/wechat-mp-virtual-lifestyle/SKILL.md \
  stock-ai/docs/superpowers/specs/2026-08-12-zhixia-welcome-to-dragon-restaurant-film-design.md
```

Expected: no remaining one-third rule; the new schema and editorial gates appear in the skill.

### Task 4: Integration regression and final verification

**Files:**
- Modify only if an integration regression is exposed: `stock-ai/tests/unit/test_wechat_mp_newspic.py`
- Verify: `stock-ai/scripts/tools/wechat_mp_newspic_draft.py`

**Interfaces:**
- Consumes: the unchanged CLI routing through `validate_film_topic_card` and `validate_film_copy`
- Produces: a verified film draft validation path with actionable errors

- [ ] **Step 1: Run focused film and newspic tests**

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_virtual_film.py \
  tests/unit/test_wechat_mp_newspic.py \
  tests/unit/test_wechat_mp_virtual_editorial.py -q
```

Expected: zero failures. If a fixture represents a single-film card, add the new schema to that fixture; do not weaken production validation.

- [ ] **Step 2: Run syntax and diff checks**

```bash
cd stock-ai
.venv/bin/python -m py_compile scripts/tools/wechat_mp_virtual_film.py scripts/tools/wechat_mp_newspic_draft.py
cd ..
git diff --check -- \
  .cursor/skills/wechat-mp-virtual-lifestyle/SKILL.md \
  stock-ai/scripts/tools/wechat_mp_virtual_film.py \
  stock-ai/tests/unit/test_wechat_mp_virtual_film.py \
  stock-ai/docs/superpowers/specs/2026-08-12-zhixia-welcome-to-dragon-restaurant-film-design.md
```

Expected: both commands exit 0 without warnings.

- [ ] **Step 3: Review only the scoped diff**

```bash
git diff -- \
  .cursor/skills/wechat-mp-virtual-lifestyle/SKILL.md \
  stock-ai/scripts/tools/wechat_mp_virtual_film.py \
  stock-ai/tests/unit/test_wechat_mp_virtual_film.py \
  stock-ai/docs/superpowers/specs/2026-08-12-zhixia-welcome-to-dragon-restaurant-film-design.md
```

Confirm that no generic newspic behavior, published ledger data, credentials, image assets, or unrelated working-tree changes are included.

- [ ] **Step 4: Commit only scoped implementation files**

```bash
git add \
  .cursor/skills/wechat-mp-virtual-lifestyle/SKILL.md \
  stock-ai/scripts/tools/wechat_mp_virtual_film.py \
  stock-ai/tests/unit/test_wechat_mp_virtual_film.py \
  stock-ai/docs/superpowers/specs/2026-08-12-zhixia-welcome-to-dragon-restaurant-film-design.md \
  stock-ai/docs/superpowers/plans/2026-08-12-zhixia-film-plot-anchor.md
git commit -m "feat(stock-ai): require plot anchors in film posts"
```
