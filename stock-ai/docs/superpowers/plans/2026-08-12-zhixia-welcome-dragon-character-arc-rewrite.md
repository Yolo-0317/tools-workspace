# Zhixia Welcome Dragon Character Arc Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generic food-themed Dragon Restaurant draft with an S2 character-arc post grounded in Xu Fu's verified shift from self-preservation to rescuing children.

**Architecture:** Keep the existing five official images and virtual-lifestyle slot. Extend film validation only enough to allow `popular_film` S2 when it explicitly uses `character_arc`, then rewrite the topic card and copy to satisfy the existing plot-anchor, spoiler, length, source, and image gates.

**Tech Stack:** Python 3, pytest, JSON, plain-text WeChat copy.

## Global Constraints

- Title is `《欢迎来龙餐馆》：徐福为何回头`, 15 characters and below the 20-character limit.
- First non-empty line is `含关键剧情讨论`.
- Body is 550–750 characters for five images.
- Copy uses `character_arc` with distinct `beginning`, `turning_point`, and `decision` anchors.
- Plot facts come from the National Film Administration filing and 1905.com; no invented dialogue, death mechanism, rescue route, or ending.
- `ai_disclosure_mode` remains `platform_publish`.
- This run ends at a successful local dry-run and does not push a WeChat draft.

---

### Task 1: Permit explicit popular-film character arcs with spoilers

**Files:**
- Modify: `stock-ai/tests/unit/test_wechat_mp_virtual_film.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_virtual_film.py`

**Interfaces:**
- Consumes: `content_lane`, `film_writing_mode`, `spoiler_level`
- Produces: topic-card validation that permits S1/S2 only for `popular_film` plus `character_arc`

- [ ] Add a failing test that a `popular_film`, `character_arc`, S2 card normalizes successfully.
- [ ] Run the focused test and confirm it fails on the current S0-only rule.
- [ ] Change the spoiler condition so ordinary popular posts still require S0, while explicit character arcs may use S1 or S2.
- [ ] Run the full film-validator unit file and confirm zero failures.

### Task 2: Rewrite topic card and body

**Files:**
- Modify: `stock-ai/output/zhixia-welcome-dragon-restaurant-topic-card.json`
- Modify: `stock-ai/output/zhixia-welcome-dragon-restaurant-copy.txt`

**Interfaces:**
- Consumes: three verified plot anchors and the existing five official image files
- Produces: a 550–750-character S2 draft body and complete character-arc topic card

- [ ] Add the National Film Administration source, set S2 and `character_arc`, and record three anchors with HTTPS sources and distinct stages.
- [ ] Rewrite the body around self-preservation, the friend's death, and rescuing children; keep analysis subordinate to the causal plot line.
- [ ] Check title length, body length, first-line spoiler disclosure, source URLs, and anchor phrases.

### Task 3: Dry-run and verify

**Files:**
- Verify: the topic card, body, existing five images, and `image-sources.json`

**Interfaces:**
- Consumes: the CLI's existing virtual-lifestyle film route
- Produces: successful local validation without network draft mutation

- [ ] Run the focused film and newspic tests.
- [ ] Run `wechat_mp_newspic_draft --slot virtual_lifestyle ... --dry-run` with the existing five images.
- [ ] Run `py_compile` and `git diff --check` on scoped code and documentation files.
- [ ] Report the final title and copy to the user; do not push until separately confirmed.
