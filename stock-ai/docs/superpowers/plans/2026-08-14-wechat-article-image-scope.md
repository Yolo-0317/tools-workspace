# WeChat Article Image Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent portal recommendation images from entering hotspot article bodies, remove the Washington carrier image from the current AI voice draft, and update the existing WeChat draft without publishing.

**Architecture:** Add a small HTML-scope helper in the existing discussion-figure module. It narrows Sina scanning to the article body and preserves the existing NetEase body boundary; image URL, dimensions, naturalness, source, and deduplication gates remain unchanged. The current article then uses its verified event screenshot as cover and the existing original explanatory images in the body.

**Tech Stack:** Python 3.12, pytest, Pillow, existing WeChat draft CLI.

## Global Constraints

- Do not add OCR, visual-model calls, or new dependencies.
- Do not modify unrelated article assets or the user's existing dirty worktree changes.
- WeChat action is draft update only; never publish.
- Fixed WeChat API egress, originality, compliance, and image gates remain fail-closed.

---

### Task 1: Add portal body-scope regression coverage

**Files:**
- Modify: `stock-ai/tests/unit/test_wechat_mp_discussion_figures.py`

**Interfaces:**
- Consumes: `_content_images_from_html(html: str, page_url: str) -> list[str]`
- Produces: regression expectations for Sina body-only extraction

- [ ] **Step 1: Write the failing recommendation-leak test**

```python
def test_sina_article_without_body_image_does_not_use_recommendation_image() -> None:
    html = '''
    <div class="article" id="article"><p>AI 配音侵权正文。</p></div>
    <div id="timeline_pc_tmpl">
      <img src="https://n.sinaimg.cn/sinakd/example-carrier.jpg">
    </div>
    '''
    assert _content_images_from_html(html, "https://k.sina.com.cn/article_example.html") == []
```

- [ ] **Step 2: Write the positive body-image test**

```python
def test_sina_article_uses_body_image_and_excludes_recommendation_image() -> None:
    html = '''
    <div class="article" id="article">
      <img src="https://n.sinaimg.cn/sinakd/voice-event.jpg">
    </div>
    <div id="timeline_pc_tmpl">
      <img src="https://n.sinaimg.cn/sinakd/example-carrier.jpg">
    </div>
    '''
    assert _content_images_from_html(html, "https://k.sina.com.cn/article_example.html") == [
        "https://n.sinaimg.cn/sinakd/voice-event.jpg"
    ]
```

- [ ] **Step 3: Run both tests and verify RED**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_discussion_figures.py -k 'sina_article_' -q`

Expected: both tests fail because the current implementation scans the full page.

### Task 2: Restrict portal image extraction to the article body

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_discussion_figures.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_discussion_figures.py`

**Interfaces:**
- Produces: `_article_image_scan_html(html: str, page_url: str) -> str`
- Consumed by: `_content_images_from_html`

- [ ] **Step 1: Implement the minimal body-scope helper**

```python
def _article_image_scan_html(html: str, page_url: str) -> str:
    low = (page_url or "").lower()
    if "163.com/" in low:
        return existing_netease_body_slice
    if "sina.com.cn/" in low or "sina.cn/" in low:
        return matched_article_inner_html_or_empty
    return html
```

- [ ] **Step 2: Make `_content_images_from_html` scan only the helper result**

Keep all existing URL normalization, event-host, dimensions, and junk-image behavior unchanged.

- [ ] **Step 3: Run the focused tests and verify GREEN**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_discussion_figures.py -k 'sina_article_' -q`

Expected: 2 passed.

- [ ] **Step 4: Run the full discussion-figure unit file**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_discussion_figures.py -q`

Expected: all tests pass.

### Task 3: Replace the bad current-article asset and update the draft

**Files:**
- Quarantine: `stock-ai/assets/wechat_mp/inline-discussion/ai用配音演员声线接广告/still-02.jpg`
- Modify: `stock-ai/assets/wechat_mp/inline-discussion/ai用配音演员声线接广告/figure_sources.json`
- Verify: `stock-ai/output/hotspot_codex_20260814_ai_voice.json`

**Interfaces:**
- Consumes: existing `manual-01.jpg`, `manual-02.jpg`, verified event screenshot, and hotspot JSON
- Produces: updated existing WeChat draft media item

- [ ] **Step 1: Move the carrier image to a recoverable temporary quarantine path**

Move only `still-02.jpg`; do not delete or alter unrelated assets.

- [ ] **Step 2: Remove only the `still-02.jpg` source entry**

Preserve all other metadata and original image files.

- [ ] **Step 3: Run the hotspot dry-run**

Run:

```bash
set -a
source .env
set +a
WECHAT_MP_HOTSPOT_TREND_ENRICH=0 PYTHONPATH=. uv run python -m scripts.tools.wechat_mp_draft --kind hotspot --codex-draft output/hotspot_codex_20260814_ai_voice.json --dry-run
```

Expected: originality report PASS; no carrier URL, `still-02.jpg`, or Washington-carrier content is injected.

- [ ] **Step 4: Update the existing WeChat draft**

Run the same command without `--dry-run`.

Expected: `OK [hotspot] 已更新`, the title remains `AI声线接广告，谁替本人同意了？`, and no publish API is called.

- [ ] **Step 5: Re-run focused verification after the write**

Run the Sina regression tests again and inspect `figure_sources.json`, the topic asset directory, and the CLI output.

Expected: tests pass, bad asset is absent from the active directory, and the draft update succeeds.
