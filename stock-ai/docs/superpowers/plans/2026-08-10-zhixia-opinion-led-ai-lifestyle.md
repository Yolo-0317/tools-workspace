# Zhixia Opinion-Led AI Lifestyle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Zhixia into an opinion-led AI lifestyle editor with a 70/20/10 content model, scored topic cards, topic-first mixed image posts, per-image watermark rules, and publication-only sequence accounting.

**Architecture:** Add one editorial module for topic-card validation and rolling mix calculations, and one ledger module for pending drafts and verified published posts. Keep WeChat draft transport in the existing newspic modules; extend its image-source contract so each image declares its narrative role and whether it may receive the Zhixia watermark. The workflow remains draft-only until a human publishes in WeChat, after which a separate read-only sync command assigns `ZX-*` numbers.

**Tech Stack:** Python 3.11, argparse, dataclasses, JSON files, Pillow, requests-based existing WeChat client, pytest.

## Global Constraints

- User-visible copy, CLI output, and documentation must not contain emoji.
- `virtual_lifestyle` content uses rolling groups of 10 valid published posts: 7 `A`, 2 `A+C`, 1 `C`.
- Drafts, previews, draft updates, and unpublished posts never increment the `ZX-*` sequence.
- Ordinary `A` and `A+C` posts default to exactly one `character` image; explicit story/wardrobe exceptions must be recorded in the topic card.
- Third-party report images never receive the `栀夏 · ZHI XIA` watermark.
- Weibo and Baidu are discovery sources only; report images require a traceable original page.
- The tooling creates or updates drafts only. It must not call `freepublish_submit` or mass-send APIs.
- No `.env`, access tokens, personal data, positions, or runtime publication ledgers are committed.
- All code changes use TDD and end with the most relevant tests plus `git diff --check`.

---

## File Structure

- Create `stock-ai/scripts/tools/wechat_mp_virtual_editorial.py`: topic-card schema, score validation, freshness checks, and rolling 70/20/10 helpers.
- Create `stock-ai/scripts/tools/wechat_mp_virtual_ledger.py`: pending-draft record, verified publication matching, idempotent `ZX-*` assignment, invalid-post handling, and round summaries.
- Create `stock-ai/scripts/tools/wechat_mp_virtual_lifestyle_sync.py`: read-only CLI that fetches published records and updates the local ledger.
- Modify `stock-ai/scripts/tools/wechat_mp_newspic.py`: structured image-source loading, mixed-image policy validation, and per-image watermark decisions.
- Modify `stock-ai/scripts/tools/wechat_mp_newspic_draft.py`: require a valid topic card for `virtual_lifestyle`, pass the content policy into image validation, and record a verified pending draft.
- Create `stock-ai/tests/unit/test_wechat_mp_virtual_editorial.py`: editorial scoring, freshness, and mix tests.
- Create `stock-ai/tests/unit/test_wechat_mp_virtual_ledger.py`: publication-only counting and idempotency tests.
- Modify `stock-ai/tests/unit/test_wechat_mp_newspic.py`: image metadata and per-image watermark tests.
- Modify `.cursor/skills/wechat-mp-virtual-lifestyle/SKILL.md`, `references/persona.md`, `references/story-bible.md`, `references/operations-benchmarks.md`, `.cursor/skills/wechat-mp-drafts/SKILL.md`, and `newspic-sop.md`: align the operational instructions with the approved spec.
- Runtime only, do not commit: `stock-ai/data/wechat_mp_virtual_lifestyle_pending.json`, `stock-ai/data/wechat_mp_virtual_lifestyle_history.json`, current topic-card JSON, copy, and generated images.

---

### Task 1: Topic Card and Editorial Mix Domain

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_virtual_editorial.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_virtual_editorial.py`

**Interfaces:**
- Produces: `load_topic_card(path: Path) -> dict[str, Any]`
- Produces: `validate_topic_card(card: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]`
- Produces: `validate_opinion_copy(content: str, *, has_report_images: bool) -> str`
- Produces: `content_mix_counts(posts: Iterable[Mapping[str, Any]]) -> dict[str, int]`
- Produces: `next_content_type(posts: Iterable[Mapping[str, Any]]) -> str`
- Content types are exactly `A`, `A+C`, and `C`.

- [ ] **Step 1: Write failing tests for required fields and scoring**

```python
def test_validate_topic_card_rejects_low_score() -> None:
    card = valid_card(scores={"timing": 10, "worker_relevance": 15,
                              "zhixia_observation": 14, "visuals": 15,
                              "persona_fit": 10})
    with pytest.raises(ValueError, match="70"):
        validate_topic_card(card, now=NOW)

def test_validate_topic_card_rejects_weak_observation() -> None:
    card = valid_card(scores={"timing": 25, "worker_relevance": 20,
                              "zhixia_observation": 14, "visuals": 15,
                              "persona_fit": 10})
    with pytest.raises(ValueError, match="栀夏观察"):
        validate_topic_card(card, now=NOW)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_wechat_mp_virtual_editorial.py -q`

Expected: collection fails because `wechat_mp_virtual_editorial` does not exist.

- [ ] **Step 3: Implement the topic-card contract**

The normalized card must contain these exact keys:

```python
REQUIRED_FIELDS = (
    "topic", "observed_at", "discovery_platform", "content_type",
    "fact_sources", "contrast", "zhixia_observation", "click_reason",
    "image_plan", "risks", "scores", "character_image_policy",
)
SCORE_FIELDS = (
    "timing", "worker_relevance", "zhixia_observation", "visuals", "persona_fit",
)
CONTENT_TYPES = ("A", "A+C", "C")
CHARACTER_POLICIES = ("default_one", "story_multiple")
```

Validation must recompute the total, require `total >= 70`, require `scores.zhixia_observation >= 15`, require at least one `https://` fact source for `A` and `A+C`, and reject blank strings or an empty image plan. `observed_at` must be timezone-aware. For `A` and `A+C`, reject a card older than six hours; `C` uses current role timing and is exempt from the hotspot age rule.

`validate_opinion_copy` must enforce 180–320 stripped characters. Pure-original posts require the exact substrings `AI 虚拟角色` and `AI 生成示意图`; mixed report/original posts additionally require `报道图来源见文中`.

- [ ] **Step 4: Add failing tests for the rolling mix**

```python
def test_next_content_type_fills_seven_two_one_round() -> None:
    posts = [{"content_type": "A"}] * 7 + [{"content_type": "A+C"}] * 2
    assert next_content_type(posts) == "C"

def test_mix_ignores_invalid_posts() -> None:
    posts = [{"content_type": "A", "status": "published"},
             {"content_type": "C", "status": "invalid"}]
    assert content_mix_counts(posts) == {"A": 1, "A+C": 0, "C": 0}
```

- [ ] **Step 5: Implement deterministic mix helpers and run tests**

Count only records with `status == "published"`, use the current incomplete ten-post round, and fill deficits in priority order `A`, `A+C`, `C`. Run:

`.venv/bin/python -m pytest tests/unit/test_wechat_mp_virtual_editorial.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit the editorial domain**

```bash
git add stock-ai/scripts/tools/wechat_mp_virtual_editorial.py stock-ai/tests/unit/test_wechat_mp_virtual_editorial.py
git commit -m "feat: add Zhixia editorial topic gates"
```

---

### Task 2: Mixed Image Metadata and Per-Image Watermarks

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_newspic.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_newspic.py`

**Interfaces:**
- Produces: `load_newspic_image_sources(path: Path) -> dict[str, dict[str, Any]]`
- Updates: `validate_newspic_image_sources(*, image_paths: Iterable[Path], sources_path: Path, content: str | None = None, draft_profile: str = "newspic", content_type: str = "", character_image_policy: str = "default_one", visual_exception: str = "") -> dict[str, dict[str, Any]]`
- Updates: `prepare_newspic_images(*, image_paths, image_sources, watermark, output_dir) -> list[Path]`

- [ ] **Step 1: Write failing metadata validation tests**

For `virtual_lifestyle`, require every record to contain `visual_role`, `position_role`, `source_type`, and `allow_zhixia_watermark`. Require `capture_mode` for `character`; require `page_url`, `page_title`, and `source_name` for `report`. Reject report images with `allow_zhixia_watermark=true`.

```python
def test_virtual_report_image_cannot_receive_zhixia_watermark(tmp_path: Path) -> None:
    image = tmp_path / "report.jpg"
    image.write_bytes(b"x")
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({image.name: {
        "source_type": "report", "visual_role": "topic",
        "position_role": "hook", "page_url": "https://example.com/a",
        "page_title": "报道", "source_name": "示例媒体",
        "allow_zhixia_watermark": True,
    }}), encoding="utf-8")
    with pytest.raises(ValueError, match="报道图.*水印"):
        validate_newspic_image_sources(
            image_paths=[image], sources_path=sources,
            content="栀夏是 AI 虚拟角色；图片为 AI 生成示意图。",
            draft_profile="virtual_lifestyle", content_type="A",
        )
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_wechat_mp_newspic.py -q`

Expected: new metadata tests fail because the current validator ignores these fields.

- [ ] **Step 3: Implement the minimal metadata loader and policy validation**

For `default_one`, require exactly one `character` image and at least one `topic` image. For `story_multiple`, require two to four `character` images and a non-empty `visual_exception` in the topic card passed by the caller. Keep generic hotspot validation backward compatible.

- [ ] **Step 4: Write a failing selective-watermark test**

```python
def test_prepare_images_watermarks_only_allowed_originals(tmp_path: Path) -> None:
    prepared = prepare_newspic_images(
        image_paths=[report, topic, character],
        image_sources={
            report.name: {"allow_zhixia_watermark": False},
            topic.name: {"allow_zhixia_watermark": True},
            character.name: {"allow_zhixia_watermark": True},
        },
        watermark="栀夏 · ZHI XIA",
        output_dir=tmp_path / "out",
    )
    assert prepared[0] == report
    assert prepared[1] != topic
    assert prepared[2] != character
```

- [ ] **Step 5: Implement selective watermarking and run regression tests**

Return the original path when watermarking is disabled; create a copied, watermarked file only when it is enabled. Run:

`.venv/bin/python -m pytest tests/unit/test_wechat_mp_newspic.py -q`

Expected: all newspic tests pass.

- [ ] **Step 6: Commit image policy changes**

```bash
git add stock-ai/scripts/tools/wechat_mp_newspic.py stock-ai/tests/unit/test_wechat_mp_newspic.py
git commit -m "feat: validate Zhixia mixed image posts"
```

---

### Task 3: Draft CLI Topic-Card Gate and Pending Record

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_newspic_draft.py`
- Create: `stock-ai/scripts/tools/wechat_mp_virtual_ledger.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_virtual_ledger.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_newspic.py`

**Interfaces:**
- Produces: `record_pending_draft(*, media_id: str, title: str, topic_card: Mapping[str, Any], drafted_at: datetime | None = None) -> dict[str, Any]`
- Produces: `load_virtual_history(path: Path = HISTORY_PATH) -> dict[str, Any]`
- CLI adds `--topic-card PATH`.
- CLI adds `--allow-mix-override REASON` for a recorded, explicit exception.
- CLI must not add `--publish`.

- [ ] **Step 1: Write failing CLI tests**

```python
def test_virtual_lifestyle_requires_topic_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    image1, image2 = tmp_path / "one.jpg", tmp_path / "two.jpg"
    image1.write_bytes(b"x")
    image2.write_bytes(b"x")
    copy_path = tmp_path / "copy.txt"
    copy_path.write_text("栀夏是 AI 虚拟角色；图片为 AI 生成示意图。" + "甲" * 180, encoding="utf-8")
    sources = tmp_path / "sources.json"
    sources.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["wechat_mp_newspic_draft", "--slot",
        "virtual_lifestyle", "--title", "合规标题文字", "--content", str(copy_path),
        "--images", str(image1), str(image2), "--image-sources", str(sources), "--dry-run"])
    assert draft_cli.main() == 1
    assert "--topic-card" in capsys.readouterr().err
```

Also test that generic `newspic_hotspot` remains usable without a topic card, and that a stale A card fails before any WeChat API call.

Add a mix test with an empty history: an `A+C` topic card must be rejected with a message that the next required type is `A`. The error may be bypassed only by an explicit `--allow-mix-override` flag, whose reason is stored in the pending record.

- [ ] **Step 2: Run the CLI tests and verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_wechat_mp_newspic.py -q`

Expected: virtual CLI accepts the missing topic card or argparse lacks the option.

- [ ] **Step 3: Wire topic-card validation into dry-run and live draft paths**

Load and validate the topic card before resolving/uploading images. Load the publication history, calculate `next_content_type`, and require the card to match unless `--allow-mix-override REASON` is supplied with a non-blank reason. Pass `content_type`, `character_image_policy`, and `visual_exception` to image-source validation. After loading image metadata, call `validate_opinion_copy` with `has_report_images`. Dry-run prints content type, recomputed score, character/topic counts, next required type, and source path without printing credentials.

- [ ] **Step 4: Write failing pending-record tests**

```python
def test_record_pending_draft_does_not_increment_sequence(tmp_path: Path) -> None:
    pending = record_pending_draft(media_id="draft-1", title="标题",
                                   topic_card=valid_card(), drafted_at=NOW)
    assert pending["media_id"] == "draft-1"
    assert not history_path(tmp_path).exists()
```

- [ ] **Step 5: Implement pending storage after verified upsert**

Use `data/wechat_mp_virtual_lifestyle_pending.json` by default. Store `media_id`, `title`, `content_type`, `topic`, `topic_card_sha256`, `drafted_at`, and `mix_override_reason`. Call it only after `upsert_newspic_draft` succeeds, which already performs remote readback.

- [ ] **Step 6: Run focused tests and commit**

Run:

`.venv/bin/python -m pytest tests/unit/test_wechat_mp_newspic.py tests/unit/test_wechat_mp_virtual_ledger.py -q`

Expected: all tests pass.

```bash
git add stock-ai/scripts/tools/wechat_mp_newspic_draft.py stock-ai/scripts/tools/wechat_mp_virtual_ledger.py stock-ai/tests/unit/test_wechat_mp_newspic.py stock-ai/tests/unit/test_wechat_mp_virtual_ledger.py
git commit -m "feat: gate Zhixia drafts with topic cards"
```

---

### Task 4: Publication-Only Ledger Sync

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_virtual_ledger.py`
- Create: `stock-ai/scripts/tools/wechat_mp_virtual_lifestyle_sync.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_virtual_ledger.py`

**Interfaces:**
- Produces: `match_pending_publication(pending, published_items) -> Mapping[str, Any] | None`
- Produces: `record_verified_publication(*, pending, publication, ledger_path: Path = HISTORY_PATH) -> dict[str, Any]`
- Produces CLI output only; it consumes existing `list_all_freepublish()` and never submits publication.

- [ ] **Step 1: Write failing tests for publication matching and idempotency**

```python
def test_verified_publication_assigns_first_number(tmp_path: Path) -> None:
    ledger = record_verified_publication(
        pending=pending(title="标题", content_type="A"),
        publication=published(article_id="article-1", title="标题", update_time=NOW_TS),
        ledger_path=tmp_path / "history.json",
    )
    assert ledger["sequence"] == 1
    assert ledger["posts"][0]["post_no"] == "ZX-001"

def test_same_article_id_is_idempotent(tmp_path: Path) -> None:
    ledger_path = tmp_path / "history.json"
    pending_record = pending(title="标题", content_type="A")
    publication_record = published(
        article_id="article-1", title="标题", update_time=NOW_TS
    )
    first = record_verified_publication(
        pending=pending_record, publication=publication_record, ledger_path=ledger_path
    )
    second = record_verified_publication(
        pending=pending_record, publication=publication_record, ledger_path=ledger_path
    )
    assert second == first
```

Also test no match for a title mismatch or publication older than `drafted_at`, and that invalid records retain numbers but are excluded from mix counts.

- [ ] **Step 2: Run ledger tests and verify RED**

Run: `.venv/bin/python -m pytest tests/unit/test_wechat_mp_virtual_ledger.py -q`

Expected: publication functions are missing.

- [ ] **Step 3: Implement atomic, publication-only ledger updates**

Write JSON through a temporary sibling file and `Path.replace()`. Store `sequence`, `round`, `posts`, `article_id`, `post_no`, `content_type`, `title`, `published_at`, `status`, and the current round's single `experiment_variable`. Refuse a second non-empty experiment variable within the same ten-post round.

- [ ] **Step 4: Implement the read-only sync CLI**

The CLI loads the pending record, calls `list_all_freepublish()`, matches exact title plus publication time at or after `drafted_at`, and appends once. It prints `NO_MATCH` without changing the ledger when the human has not published yet. It must not import or call `freepublish_submit`.

- [ ] **Step 5: Test the CLI with mocked published records**

Run: `.venv/bin/python -m pytest tests/unit/test_wechat_mp_virtual_ledger.py -q`

Expected: all tests pass and a static import assertion confirms `freepublish_submit` is absent.

- [ ] **Step 6: Commit the ledger sync**

```bash
git add stock-ai/scripts/tools/wechat_mp_virtual_ledger.py stock-ai/scripts/tools/wechat_mp_virtual_lifestyle_sync.py stock-ai/tests/unit/test_wechat_mp_virtual_ledger.py
git commit -m "feat: track published Zhixia posts"
```

---

### Task 5: Align Skills and Operator Documentation

**Files:**
- Modify: `.cursor/skills/wechat-mp-virtual-lifestyle/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-virtual-lifestyle/references/persona.md`
- Modify: `.cursor/skills/wechat-mp-virtual-lifestyle/references/story-bible.md`
- Modify: `.cursor/skills/wechat-mp-virtual-lifestyle/references/operations-benchmarks.md`
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-drafts/newspic-sop.md`

**Interfaces:**
- Documents the exact topic-card JSON keys and the commands implemented in Tasks 1–4.
- Routes unqualified “贴图” to `virtual_lifestyle`; explicit news galleries remain generic newspic.

- [ ] **Step 1: Replace outdated method-first and all-character instructions**

Ensure the docs state the approved 70/20/10 model, one-character default, topic-first cover, explainable capture modes, conditional AI disclosure, report-image watermark prohibition, and publication-only counting.

- [ ] **Step 2: Add exact dry-run and sync examples**

```bash
.venv/bin/python -m scripts.tools.wechat_mp_newspic_draft \
  --slot virtual_lifestyle \
  --topic-card output/zhixia-topic-card.json \
  --title "外国人给喝热水起了个新名字" \
  --content output/zhixia-copy.txt \
  --images assets/zhixia/01.png assets/zhixia/02.png assets/zhixia/03.png \
  --image-sources assets/zhixia/image-sources.json \
  --dry-run

.venv/bin/python -m scripts.tools.wechat_mp_virtual_lifestyle_sync
```

- [ ] **Step 3: Check the docs for contradictions and stale wording**

Run:

```bash
rg -n "每条.*方法|前 8|前8|全部.*栀夏|同事随手拍|报道图.*水印" \
  .cursor/skills/wechat-mp-virtual-lifestyle \
  .cursor/skills/wechat-mp-drafts
```

Expected: only explicit prohibitions or historical benchmark discussion remain.

- [ ] **Step 4: Commit documentation alignment**

```bash
git add .cursor/skills/wechat-mp-virtual-lifestyle .cursor/skills/wechat-mp-drafts/SKILL.md .cursor/skills/wechat-mp-drafts/newspic-sop.md
git commit -m "docs: align Zhixia opinion-led workflow"
```

---

### Task 6: Replace the Current Draft with a Fresh Qualified Topic

**Files:**
- Runtime only: `stock-ai/output/zhixia-topic-card.json`
- Runtime only: `stock-ai/output/zhixia-copy.txt`
- Runtime only: topic asset directory and `image-sources.json`

**Interfaces:**
- Consumes the CLI and policies from Tasks 1–5.
- Produces one remotely verified `virtual_lifestyle` draft and one pending record; it does not publish.

- [ ] **Step 1: Recheck current Weibo/Baidu trends at execution time**

Record the exact observation time. Do not reuse the August 10 Chinamaxxing topic if its card is older than six hours. Score at least three safe candidates and select the highest score at or above 70 with observation score at or above 15.

- [ ] **Step 2: Create the topic card before images**

Use content type recommended by the current incomplete ten-post round. Since no Zhixia post has been published yet, the first valid draft should be `A` unless a genuinely timely `C` system-log event scores higher and the user chooses it.

- [ ] **Step 3: Build a topic-first three-image package**

Use one `hook` topic image, one `evidence` topic image, and one explainable `author` image. Prefer traceable real images; use original topic visuals only when adoption boundaries are unclear. Do not use the rejected clean-office candid image.

- [ ] **Step 4: Run dry-run and inspect all images**

Run the documented CLI with `--dry-run`. Verify title length, 180–320 character copy, recomputed score, exactly one character image, metadata completeness, disclosure, and watermark decisions.

- [ ] **Step 5: Update the existing draft and verify remote readback**

Run the same command without `--dry-run`. Expected output begins with `OK [virtual_lifestyle] updated`; if the existing slot cannot update, creation fallback is acceptable only when remote readback succeeds. Confirm that no publish API was called and the ledger sequence remains zero.

---

### Task 7: Full Verification and Handoff

**Files:**
- Verify all files changed in Tasks 1–6.

- [ ] **Step 1: Run the focused suite**

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_virtual_editorial.py \
  tests/unit/test_wechat_mp_virtual_ledger.py \
  tests/unit/test_wechat_mp_newspic.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run adjacent WeChat regressions**

```bash
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_codex_images.py \
  tests/unit/test_wechat_mp_discussion_figures.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run syntax and whitespace checks**

```bash
.venv/bin/python -m py_compile \
  scripts/tools/wechat_mp_virtual_editorial.py \
  scripts/tools/wechat_mp_virtual_ledger.py \
  scripts/tools/wechat_mp_virtual_lifestyle_sync.py \
  scripts/tools/wechat_mp_newspic.py \
  scripts/tools/wechat_mp_newspic_draft.py
git diff --check
```

Expected: both commands exit zero.

- [ ] **Step 4: Confirm secret and scope hygiene**

Run `git status --short` and inspect every staged path. Confirm `.env`, token caches, runtime history, generated images, unrelated `a-share-short-term-trading` changes, and rejected draft assets are not staged.

- [ ] **Step 5: Confirm all planned changes are already committed**

```bash
git status --short -- \
  stock-ai/scripts/tools/wechat_mp_virtual_editorial.py \
  stock-ai/scripts/tools/wechat_mp_virtual_ledger.py \
  stock-ai/scripts/tools/wechat_mp_virtual_lifestyle_sync.py \
  stock-ai/scripts/tools/wechat_mp_newspic.py \
  stock-ai/scripts/tools/wechat_mp_newspic_draft.py \
  stock-ai/tests/unit/test_wechat_mp_virtual_editorial.py \
  stock-ai/tests/unit/test_wechat_mp_virtual_ledger.py \
  stock-ai/tests/unit/test_wechat_mp_newspic.py \
  .cursor/skills/wechat-mp-virtual-lifestyle \
  .cursor/skills/wechat-mp-drafts
```

Expected: no output. If a planned path remains modified, inspect it, rerun its focused tests, and commit only that exact planned path with the task's commit message.

- [ ] **Step 6: Report the result**

Provide the new draft title, content type, score, three-image role breakdown, remote draft action/media ID, test counts, commit IDs, and explicitly state “draft only, not published; sequence remains 0.”
