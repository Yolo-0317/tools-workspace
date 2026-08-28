# Zhixia Morning Stretch and Coffee Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create, validate, and upload one Zhixia morning image-post draft to the WeChat `virtual_lifestyle` slot without publishing it.

**Architecture:** Keep all post-specific source assets in one dated directory under `assets/wechat_mp/virtual-lifestyle/`. Generate one identity-preserved character image and two original topic-detail images, then pass the topic card, copy, images, and source manifest through the existing newspic dry-run and upload pipeline.

**Tech Stack:** Markdown/JSON content assets, built-in ImageGen, Python `wechat_mp_newspic_draft` CLI, WeChat draft API.

## Global Constraints

- Use `zhixia_daily` with content type `B` and the `virtual_lifestyle` slot.
- Use 3 images: exactly 1 Zhixia character image and 2 original topic visuals.
- Keep the copy between 220 and 280 Chinese characters and include the required AI disclosure.
- Do not claim real-world attendance, health effects, product testing, or publication.
- Update the draft slot only after dry-run validation succeeds.

---

### Task 1: Create the post source package

**Files:**
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-11-早上只做十分钟/topic-card.json`
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-11-早上只做十分钟/continuity-card.md`
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-11-早上只做十分钟/copy.txt`

**Interfaces:**
- Consumes: the approved design, persona, wardrobe, and story bible.
- Produces: a valid topic card and final copy for the draft CLI.

- [ ] Write the complete `zhixia_daily` topic card with five scores totaling at least 70.
- [ ] Write the continuity card locking `SU-Y02`, `HA04`, `E01`, `J01`, `B05`, `S04`, and `P05`.
- [ ] Write 220–280 Chinese characters around the observation that a morning need not prove self-discipline.
- [ ] Validate the topic card and copy with the existing editorial helpers.

### Task 2: Generate and inspect the three images

**Files:**
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-11-早上只做十分钟/01-character.png`
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-11-早上只做十分钟/02-stretch-detail.png`
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-11-早上只做十分钟/03-coffee-detail.png`
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-11-早上只做十分钟/image-sources.json`

**Interfaces:**
- Consumes: the continuity card and confirmed character master.
- Produces: three inspected PNG assets plus their provenance and visual roles.

- [ ] Generate `01-character.png` in identity-preserve mode using the confirmed master image.
- [ ] Generate `02-stretch-detail.png` as an original non-character morning yoga detail image.
- [ ] Generate `03-coffee-detail.png` as an original non-character morning street-corner coffee detail image.
- [ ] Inspect every image for continuity, anatomy, artifacts, accidental text, and scene consistency.
- [ ] Record each prompt, `visual_role`, source type, and AI-generation disclosure in `image-sources.json`.

### Task 3: Validate and write the WeChat draft

**Files:**
- Modify: `data/wechat_mp_draft_slots.json`
- Modify: `data/wechat_mp_virtual_lifestyle_pending.json`

**Interfaces:**
- Consumes: `topic-card.json`, `copy.txt`, the three PNG files, and `image-sources.json`.
- Produces: a validated WeChat draft in the `virtual_lifestyle` slot and a pending-publication record.

- [ ] Run `wechat_mp_newspic_draft` with `--dry-run` and the exact source package.
- [ ] Stop and correct the source package if any editorial, image-source, or continuity gate fails.
- [ ] Run the same command without `--dry-run` to create or update the WeChat draft.
- [ ] Re-read the slot and pending JSON files and verify their title, media ID, and timestamps.
- [ ] Confirm that no publish action was invoked.
