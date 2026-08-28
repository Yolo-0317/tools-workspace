# Zhixia Year End Party 2 Image Post Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an auditable platform-publish AI disclosure mode, assemble a sourced four-image 《年会不能停2！》 post, and write it to the WeChat `virtual_lifestyle` draft slot without publishing.

**Architecture:** Extend the existing film topic-card validator with a default-preserving `ai_disclosure_mode` value and persist that value in the pending ledger. The post package remains data-only under the dated virtual-lifestyle asset directory and is validated through the existing draft CLI before upload.

**Tech Stack:** Python 3.11, pytest, JSON/text content assets, WeChat draft API.

## Global Constraints

- Use `popular_film`, content type `A`, release status `released`, and spoiler level `S0`.
- Use 4 traceable official or media promotional images with `allow_zhixia_watermark=false`.
- Keep the final copy between 220 and 280 Chinese characters.
- Omit the body AI disclosure only when `ai_disclosure_mode` is exactly `platform_publish`.
- Keep the existing body-disclosure requirement as the default for every card without that explicit mode.
- Create or update a draft only; never invoke publication.

---

### Task 1: Add the platform-publish disclosure mode with TDD

**Files:**
- Modify: `tests/unit/test_wechat_mp_virtual_film.py`
- Modify: `tests/unit/test_wechat_mp_virtual_ledger.py`
- Modify: `scripts/tools/wechat_mp_virtual_film.py`
- Modify: `scripts/tools/wechat_mp_virtual_ledger.py`

**Interfaces:**
- Consumes: film topic cards passed to `validate_film_topic_card`, `validate_film_copy`, and `record_pending_draft`.
- Produces: normalized `ai_disclosure_mode: str` with values `body` or `platform_publish`, plus pending-record persistence.

- [ ] **Step 1: Write failing film-copy tests**

```python
def test_platform_publish_mode_allows_copy_without_body_disclosure() -> None:
    content = "甲" * 220
    assert validate_film_copy(
        title="《一部电影》最安静的不是结尾",
        content=content,
        card=film_card(ai_disclosure_mode="platform_publish"),
        image_count=4,
        has_original_images=False,
    ) == content


def test_default_mode_still_requires_body_disclosure() -> None:
    with pytest.raises(ValueError, match="影视正文须披露"):
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content="甲" * 220,
            card=film_card(),
            image_count=4,
            has_original_images=False,
        )
```

- [ ] **Step 2: Run the new film tests and verify the explicit-mode test fails**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_virtual_film.py -q`

Expected: the `platform_publish` case fails with `影视正文须披露栀夏为 AI 虚拟角色且不对应真人经历`.

- [ ] **Step 3: Implement minimal normalization and conditional validation**

```python
AI_DISCLOSURE_MODES = ("body", "platform_publish")

mode = str(card.get("ai_disclosure_mode") or "body").strip()
if mode not in AI_DISCLOSURE_MODES:
    raise ValueError("影视 AI 声明模式须为 body / platform_publish")
normalized["ai_disclosure_mode"] = mode

if normalized_card["ai_disclosure_mode"] == "body" and (
    "栀夏是 AI 虚拟角色" not in normalized_content
    or "不对应真人观影经历" not in normalized_content
):
    raise ValueError("影视正文须披露栀夏为 AI 虚拟角色且不对应真人经历")
```

- [ ] **Step 4: Add a failing pending-ledger persistence test**

```python
def test_pending_record_preserves_platform_publish_disclosure_mode(tmp_path: Path) -> None:
    pending = record_pending_draft(
        media_id="draft-1",
        title="这是一个标题",
        topic_card=_valid_card() | {"ai_disclosure_mode": "platform_publish"},
        topic_card_sha256="abc123",
        drafted_at=NOW,
        pending_path=tmp_path / "pending.json",
    )
    assert pending["ai_disclosure_mode"] == "platform_publish"
```

- [ ] **Step 5: Run the ledger test and verify it fails with a missing key**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_virtual_ledger.py::test_pending_record_preserves_platform_publish_disclosure_mode -q`

Expected: FAIL with `KeyError: 'ai_disclosure_mode'`.

- [ ] **Step 6: Persist the normalized mode in the pending record**

```python
"ai_disclosure_mode": str(
    topic_card.get("ai_disclosure_mode") or "body"
).strip(),
```

- [ ] **Step 7: Run both focused test files**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_virtual_film.py tests/unit/test_wechat_mp_virtual_ledger.py -q`

Expected: all tests pass.

### Task 2: Build the sourced film-post package

**Files:**
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-11-年会不能停2绩效化生存/topic-card.json`
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-11-年会不能停2绩效化生存/copy.txt`
- Create: `assets/wechat_mp/virtual-lifestyle/2026-08-11-年会不能停2绩效化生存/image-sources.json`
- Create: four sourced image files in the same directory.

**Interfaces:**
- Consumes: official or traceable media pages for 《年会不能停2！》.
- Produces: a complete `popular_film` package accepted by the draft CLI.

- [ ] Re-verify the release date, director, principal cast, and public premise within six hours of drafting.
- [ ] Select four official or media promotional images whose original pages and adoption boundaries can be recorded.
- [ ] Write the complete topic card with `ai_disclosure_mode: "platform_publish"`, a score of at least 70, and an observation score of at least 15.
- [ ] Write 220–280 characters of S0 copy around “绩效化生存” without the body AI declaration.
- [ ] Record each image's source, film title, page URL, page title, source name, visual role, position role, and disabled Zhixia watermark.

### Task 3: Validate, upload, and round-trip verify the draft

**Files:**
- Modify: `data/wechat_mp_draft_slots.json`
- Modify: `data/wechat_mp_virtual_lifestyle_pending.json`

**Interfaces:**
- Consumes: the full post package from Task 2.
- Produces: a WeChat `newspic` draft with four images and an auditable pending record.

- [ ] Run the two focused test files again before content validation.
- [ ] Run `wechat_mp_newspic_draft --dry-run` with the exact four images and source manifest.
- [ ] Run the same command without `--dry-run` only after all gates pass.
- [ ] Read back the WeChat draft and assert the exact title, `article_type=newspic`, and `image_count=4`.
- [ ] Read the slot and pending JSON files and assert the matching media ID, title, `popular_film` lane, and `platform_publish` disclosure mode.
- [ ] Confirm that no publication endpoint was invoked.
