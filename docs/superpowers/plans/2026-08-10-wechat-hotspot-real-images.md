# WeChat Hotspot Real Images Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make hotspot drafts prefer traceable, event-matched real news photos from research URLs, Weibo discovery, and Baidu News, while retaining generated illustrations only as a fallback.

**Architecture:** Extend the existing discussion-image pipeline instead of adding a parallel downloader. Normalize source metadata at the boundary, rank verified real photos ahead of generated assets, and make forced refresh bypass the Codex-ready cache without deleting usable fallback files. Existing hotspot repush remains the only mutation path for the live draft.

**Tech Stack:** Python 3, standard-library `urllib`, Pillow, pytest, WeChat Official Account draft API.

## Global Constraints

- User-visible content and reports must not contain emoji.
- Do not commit `.env`, certificates, subscription links, holdings, or personal memory.
- Weibo and Baidu are discovery sources; untraceable reposts must not enter a formal draft automatically.
- Do not bypass login, anti-bot, or copyright restrictions.
- The workflow writes a draft only; publishing remains manual.
- Existing metadata files remain readable.

---

### Task 1: Source metadata and captions

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_discussion_figures.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_discussion_figures.py`

**Interfaces:**
- Consumes: existing `figure_sources.json` dictionaries keyed by local filename.
- Produces: `_normalize_figure_source(info: dict[str, object]) -> dict[str, str]`, `_figure_caption(info: dict[str, object]) -> str`, and enriched entries with `page_url`, `image_url`, `source_name`, `published_at`, `source_type`, `caption`, and `verified`.

- [ ] **Step 1: Write failing tests for compatibility and source-specific captions**

```python
def test_figure_caption_uses_verified_source_name() -> None:
    assert _figure_caption({"source_name": "新民晚报", "verified": "true"}) == "图源：新民晚报现场报道"


def test_legacy_figure_metadata_remains_readable() -> None:
    normalized = _normalize_figure_source({"page_url": "https://example.com/a", "page_title": "报道"})
    assert normalized["page_url"] == "https://example.com/a"
    assert normalized["verified"] == "false"
```

- [ ] **Step 2: Run tests and verify failure because the helpers do not exist**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_discussion_figures.py -k 'figure_caption or legacy_figure_metadata' -q`

Expected: collection fails with missing imports.

- [ ] **Step 3: Implement normalization and caption generation**

Add pure helpers that map legacy metadata to the new schema, preserve unknown fields, and return a generic caption only for legacy or unverified cached material. Update `_load_figure_sources`, `_save_figure_sources`, and `_figure_dicts_from_dir` to use them.

- [ ] **Step 4: Run focused tests**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_discussion_figures.py -k 'figure_caption or legacy_figure_metadata' -q`

Expected: all selected tests pass.

### Task 2: Real-photo source classification, restrictions, and ranking

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_discussion_figures.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_discussion_research.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_discussion_figures.py`

**Interfaces:**
- Consumes: page URL, parsed article title/snippet, page HTML, image URL, topic keywords.
- Produces: `_source_type_for_url(page_url: str) -> str`, `_source_name_for_page(page_url: str, html: str, hit: ResearchHit | None) -> str`, `_page_restricts_reuse(html: str) -> bool`, and enriched search queries from `figure_search_queries(topic)`.

- [ ] **Step 1: Write failing classification and policy tests**

```python
def test_source_type_classifies_weibo_and_baidu_news() -> None:
    assert _source_type_for_url("https://weibo.com/123/abc") == "weibo"
    assert _source_type_for_url("https://baijiahao.baidu.com/s?id=1") == "baidu_news"


def test_explicit_no_repost_notice_blocks_automatic_use() -> None:
    assert _page_restricts_reuse("未经正式授权严禁转载本文，侵权必究")


def test_figure_queries_add_scene_and_date_variants() -> None:
    queries = figure_search_queries({"trend_title": "武康路积水", "event_date": "2026-08-09"})
    assert "武康路积水 现场" in queries
    assert "武康路积水 2026-08-09" in queries
```

- [ ] **Step 2: Run tests and verify the missing behavior fails**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_discussion_figures.py -k 'source_type or no_repost or scene_and_date' -q`

Expected: selected tests fail because classification, restrictions, and query variants are absent.

- [ ] **Step 3: Implement minimal policy helpers and search variants**

Classify only recognized Weibo and Baidu domains, detect explicit reuse bans from fetched HTML, extract a conservative source name from known domains or metadata, and add bounded `现场`, date, and image queries without changing unrelated research behavior.

- [ ] **Step 4: Feed verified metadata into downloaded candidates**

When a candidate passes relevance and reuse checks, persist the actual image URL, source type, source name, parsed publish date when present, caption, and `verified=true`. Skip restricted pages before downloading. Do not mark ordinary-user Weibo pages as verified unless the page exposes a media or government identity.

- [ ] **Step 5: Run focused tests**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_discussion_figures.py -k 'source_type or no_repost or scene_and_date or figure_caption or metadata' -q`

Expected: all selected tests pass.

### Task 3: Forced real-photo refresh and generated fallback preservation

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_discussion_figures.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_codex_images.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_discussion_figures.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_codex_images.py`

**Interfaces:**
- Consumes: `WECHAT_MP_DISCUSSION_FIGURES_FORCE`, `codex-images-ready.json`, cached `still-*`, `manual-*`, and `cover.jpg` files.
- Produces: forced refresh that searches even when the Codex-ready marker exists, preserves generated files, and selects verified `still-*` before `manual-*` for body and cover.

- [ ] **Step 1: Write failing ready-marker force test**

```python
def test_force_refetch_bypasses_codex_ready_marker(tmp_path, monkeypatch) -> None:
    out_dir = tmp_path / "topic"
    out_dir.mkdir()
    (out_dir / "codex-images-ready.json").write_text("{}")
    called = []
    monkeypatch.setenv("WECHAT_MP_DISCUSSION_FIGURES_FORCE", "1")
    monkeypatch.setattr(mod, "fetch_discussion_research", lambda *_a, **_k: called.append(True) or [])
    mod.ensure_discussion_figures({"cover_slug": "topic", "trend_title": "事件"}, max_images=3)
    assert called
```

- [ ] **Step 2: Run the test and verify it fails because the marker short-circuits**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_discussion_figures.py::test_force_refetch_bypasses_codex_ready_marker -q`

Expected: failure because `called` remains empty.

- [ ] **Step 3: Implement force-aware ready-marker handling**

Calculate the force flag before the ready-marker branch and bypass only that branch when forced. Keep `manual-*` and generated `cover.jpg` untouched until a verified real photo is selected.

- [ ] **Step 4: Write and pass ordering tests**

Add a test proving a verified `still-01.jpg` appears before `manual-01.jpg`, and a test proving generated fallback remains when no verified still is found. Run:

`cd stock-ai && uv run pytest tests/unit/test_wechat_mp_discussion_figures.py tests/unit/test_wechat_mp_codex_images.py -q`

Expected: both files pass.

### Task 4: Regression verification and documentation alignment

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-drafts/rules-implemented.md`
- Test: `stock-ai/tests/unit/test_wechat_mp_discussion_figures.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_codex_images.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_newspic.py`

**Interfaces:**
- Consumes: the finalized image-source policy.
- Produces: operator documentation stating that verified real photos precede generated images and that force refresh can revisit sources.

- [ ] **Step 1: Update the operator-facing rules**

Document the exact search priority, provenance metadata, restricted-page behavior, and ImageGen fallback boundary. Keep `newspic` behavior unchanged.

- [ ] **Step 2: Run the relevant regression suite**

Run: `cd stock-ai && uv run pytest tests/unit/test_wechat_mp_discussion_figures.py tests/unit/test_wechat_mp_codex_images.py tests/unit/test_wechat_mp_newspic.py -q`

Expected: all tests pass with zero failures.

- [ ] **Step 3: Run syntax and whitespace checks**

Run: `cd stock-ai && uv run python -m py_compile scripts/tools/wechat_mp_discussion_figures.py scripts/tools/wechat_mp_discussion_research.py scripts/tools/wechat_mp_codex_images.py`

Run: `git diff --check`

Expected: both commands exit 0.

### Task 5: Refresh and verify the Wukang Road draft

**Files:**
- Reuse: `stock-ai/output/hotspot_codex_shanghai_rain.json`
- Update generated runtime files under: `stock-ai/assets/wechat_mp/inline-discussion/上海变海上-武康路积水-暴雨排水/`

**Interfaces:**
- Consumes: existing hotspot draft slot `hotspot_afternoon` and its cached body.
- Produces: updated WeChat draft with at least one verified same-event real photo when a lawful, traceable source is available; otherwise preserves the current draft and reports the evidence gap.

- [ ] **Step 1: Run a forced dry-run image refresh**

Run: `cd stock-ai && set -a && source .env && set +a && WECHAT_MP_DISCUSSION_FIGURES_FORCE=1 uv run python -m scripts.tools.wechat_mp_draft --kind hotspot --codex-draft output/hotspot_codex_shanghai_rain.json --dry-run`

Expected: the output identifies downloaded real-photo sources or explicitly reports that no verified photo is available.

- [ ] **Step 2: Inspect selected image and metadata**

Open the selected local image, confirm it depicts Wukang Road flooding from the 2026-08-09 event, and inspect `figure_sources.json` for a traceable source URL, name, date, caption, and `verified=true`.

- [ ] **Step 3: Update the existing draft without rewriting body text**

Run: `cd stock-ai && set -a && source .env && set +a && uv run python -m scripts.tools.wechat_mp_repush_hotspot_figures --slot-key hotspot_afternoon --topic "武康路积水" --force-figures`

Expected: the existing slot is updated, three body images remain, and the command states that Composer was not called.

- [ ] **Step 4: Read the draft back through the WeChat API**

Verify the title is unchanged, `thumb_media_id` is set, the HTML contains three `<img` tags, concrete source captions appear for verified real photos, and no `[[fig:` marker remains.

- [ ] **Step 5: Commit verified implementation files**

```bash
git add stock-ai/scripts/tools/wechat_mp_discussion_figures.py \
  stock-ai/scripts/tools/wechat_mp_discussion_research.py \
  stock-ai/scripts/tools/wechat_mp_codex_images.py \
  stock-ai/tests/unit/test_wechat_mp_discussion_figures.py \
  stock-ai/tests/unit/test_wechat_mp_codex_images.py \
  .cursor/skills/wechat-mp-drafts/SKILL.md \
  .cursor/skills/wechat-mp-drafts/rules-implemented.md \
  docs/superpowers/plans/2026-08-10-wechat-hotspot-real-images.md
git commit -m "feat: prefer verified photos in hotspot drafts"
```
