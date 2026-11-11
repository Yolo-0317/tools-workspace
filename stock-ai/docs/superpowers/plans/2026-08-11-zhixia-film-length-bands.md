# Zhixia Film Length Bands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow short release briefs and longer person-led or issue-led popular-film image posts, then replace the current Kathy draft with a roughly 480-character version.

**Architecture:** Keep existing lane metadata unchanged and make the validator accept one of two explicit length bands for `popular_film`. Select the long band only from image count and text length, avoiding a new topic-card field; all other film lanes keep their existing single range.

**Tech Stack:** Python 3.12, pytest, existing WeChat newspic CLI and draft API client

## Global Constraints

- `popular_film` release briefs remain 180–320 characters with 4–6 images.
- `popular_film` feature posts accept 400–550 characters with 4 images and 550–750 characters with 5–6 images.
- Text lengths 321–399 are invalid; 4-image text above 550 and 5–6-image text above 750 are invalid.
- Other film lanes retain their current image and copy limits.
- The Kathy post remains S0, uses four traceable promotional images, and records `ai_disclosure_mode=platform_publish`.
- The live action is draft replacement only; do not publish.

---

### Task 1: Add popular-film dual-band validation

**Files:**
- Modify: `tests/unit/test_wechat_mp_virtual_film.py`
- Modify: `scripts/tools/wechat_mp_virtual_film.py`

**Interfaces:**
- Consumes: `validate_film_copy(title, content, card, image_count, has_original_images)`.
- Produces: the same function signature with dual-band validation only for `popular_film`.

- [x] **Step 1: Add failing boundary tests**

  Add parametrized passing cases `(4, 180)`, `(4, 320)`, `(4, 400)`, `(4, 550)`, `(5, 550)`, `(6, 750)` and rejecting cases `(4, 321)`, `(4, 399)`, `(4, 551)`, `(5, 549)`, `(6, 751)`. Use `ai_disclosure_mode="platform_publish"` so the test isolates length behavior.

- [x] **Step 2: Run tests and confirm RED**

  Run:

  ```bash
  uv run python -m pytest tests/unit/test_wechat_mp_virtual_film.py -q
  ```

  Expected: feature-band passing cases fail under the old 180–320 rule.

- [x] **Step 3: Implement the minimal dual-band helper**

  Add a private predicate that returns true for 180–320 characters, for 400–550 characters at four images, or for 550–750 characters at five to six images. Call it only when `content_lane == "popular_film"`; preserve the existing `FILM_RULES` path for all other lanes.

- [x] **Step 4: Run focused tests and confirm GREEN**

  Run:

  ```bash
  uv run python -m pytest tests/unit/test_wechat_mp_virtual_film.py tests/unit/test_wechat_mp_virtual_ledger.py -q
  ```

  Expected: all focused tests pass.

### Task 2: Rewrite and upload the Kathy feature draft

**Files:**
- Modify: `assets/wechat_mp/virtual-lifestyle/2026-08-11-年会不能停2绩效化生存/copy.txt`
- Reuse: `assets/wechat_mp/virtual-lifestyle/2026-08-11-年会不能停2绩效化生存/topic-card.json`
- Reuse: `assets/wechat_mp/virtual-lifestyle/2026-08-11-年会不能停2绩效化生存/image-sources.json`
- Update via CLI: `data/wechat_mp_draft_slots.json`
- Update via CLI: `data/wechat_mp_virtual_lifestyle_pending.json`

**Interfaces:**
- Consumes: the new four-image 400–550 validation band and the four selected Kathy/film promotional images.
- Produces: a validated `newspic` draft in slot `virtual_lifestyle`.

- [x] **Step 1: Write the 400–550 character feature copy**

  Build five short paragraphs in the approved order: official Kathy hook; Gao Ye's established strong-woman screen recognition without equating actor and role; gendered evaluation of ambition; the boundary that promotion is not the only answer; Zhixia's final observation. Keep the copy S0 and omit a body AI declaration.

- [x] **Step 2: Run the exact dry-run command**

  Run the existing `wechat_mp_newspic_draft` command with title `《年会不能停2！》高叶演了个想升职的人`, four selected image paths, the current source manifest, topic card, slot `virtual_lifestyle`, and `--dry-run`.

  Expected: exit 0, type A, lane `popular_film`, four images.

- [x] **Step 3: Replace the draft**

  Run the same command without `--dry-run`.

  Expected: `OK [virtual_lifestyle]` with a media ID. This creates or replaces only a draft and does not publish.

- [x] **Step 4: Verify the remote draft**

  Call `fetch_draft_news_item(media_id=...)` and assert title, `article_type="newspic"`, four images, remote/local content lengths, and `ai_disclosure_mode="platform_publish"` all match.
