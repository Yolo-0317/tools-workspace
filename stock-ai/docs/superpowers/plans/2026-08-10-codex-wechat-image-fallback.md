# Codex WeChat Image Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make hotspot long-form and newspic draft workflows fetch same-topic report images first, emit Codex ImageGen requests for only the missing slots, and resume automatically after generated files are saved.

**Architecture:** A focused `wechat_mp_codex_images` module wraps the existing discussion-image fetcher and owns the generated-image request/source-manifest protocol. The hotspot builder invokes it before the existing cover/body figure gates, while the newspic CLI adds a topic-driven automatic mode and keeps its explicit image mode compatible.

**Tech Stack:** Python 3.11, Pillow, argparse, dataclasses, existing WeChat MP discussion research/figure modules, pytest.

## Global Constraints

- User-visible output and public copy contain no emoji.
- Report images are always preferred; generated originals fill only missing slots.
- Python does not call Composer, OpenAI APIs, or any image model.
- Codex ImageGen output must not fabricate a news scene, identity, institution mark, casualty number, or unverified detail.
- Existing `--images --image-sources` newspic mode remains supported.
- No `.env`, credentials, generated images, article drafts, or personal source data are committed.

---

### Task 1: Define the Codex image request and topic asset preparer

**Files:**
- Create: `scripts/tools/wechat_mp_codex_images.py`
- Create: `tests/unit/test_wechat_mp_codex_images.py`

**Interfaces:**
- Produces: `CodexImageGenerationRequired(request_path: Path, missing_count: int)`.
- Produces: `PreparedTopicImages(image_paths: tuple[Path, ...], sources_path: Path)`.
- Produces: `prepare_newspic_topic_images(*, topic: str, research_urls: Iterable[str] = (), target_count: int = 6) -> PreparedTopicImages`.
- Produces: `prepare_hotspot_topic_images(topic: dict[str, Any], *, body_count: int = 3) -> None`.

- [ ] **Step 1: Write the failing request and newspic preparation tests**

```python
def test_prepare_newspic_requests_only_missing_original_slots(tmp_path, monkeypatch):
    report = tmp_path / "topic" / "still-01.jpg"
    _valid_image(report)
    monkeypatch.setattr(images_mod, "INLINE_DISCUSSION_ROOT", tmp_path)
    monkeypatch.setattr(images_mod, "ensure_discussion_figures", lambda topic, max_images: [
        {"rel": "discussion/topic/still-01.jpg", "cap": "图源：公开报道（引用）"}
    ])
    monkeypatch.setattr(images_mod, "_load_report_meta", lambda out_dir: {
        "still-01.jpg": {"page_url": "https://example.com/a", "page_title": "报道 A"}
    })

    with pytest.raises(CodexImageGenerationRequired) as caught:
        prepare_newspic_topic_images(topic="事件", target_count=3)

    request = json.loads(caught.value.request_path.read_text(encoding="utf-8"))
    assert request["report_image_count"] == 1
    assert [Path(slot["output_path"]).name for slot in request["slots"]] == [
        "manual-01.jpg", "manual-02.jpg"
    ]
```

```python
def test_prepare_newspic_combines_reports_and_generated_images(tmp_path, monkeypatch):
    out_dir = tmp_path / "topic"
    _valid_image(out_dir / "still-01.jpg")
    _valid_image(out_dir / "manual-01.jpg")
    monkeypatch.setattr(images_mod, "INLINE_DISCUSSION_ROOT", tmp_path)
    monkeypatch.setattr(images_mod, "ensure_discussion_figures", lambda topic, max_images: [
        {"rel": "discussion/topic/still-01.jpg", "cap": "图源：公开报道（引用）"}
    ])
    monkeypatch.setattr(images_mod, "_load_report_meta", lambda out_dir: {
        "still-01.jpg": {"page_url": "https://example.com/a", "page_title": "报道 A"}
    })

    prepared = prepare_newspic_topic_images(topic="事件", target_count=2)

    assert [path.name for path in prepared.image_paths] == ["still-01.jpg", "manual-01.jpg"]
    sources = json.loads(prepared.sources_path.read_text(encoding="utf-8"))
    assert sources["still-01.jpg"]["source_type"] == "report"
    assert sources["manual-01.jpg"]["source_type"] == "original"
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `uv run pytest tests/unit/test_wechat_mp_codex_images.py -q`

Expected: collection fails because `scripts.tools.wechat_mp_codex_images` does not exist.

- [ ] **Step 3: Implement the minimal protocol and preparer**

Implement a frozen result dataclass, a dedicated exception, stable slug/output-directory resolution through the discussion-figure module, valid-image scanning for `still-*` and `manual-*`, source JSON serialization, and request JSON serialization. Each request slot must include an absolute `output_path`, a topical prompt, and the shared three-item safety rule list.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `uv run pytest tests/unit/test_wechat_mp_codex_images.py -q`

Expected: all protocol and newspic preparation tests pass.

### Task 2: Add hotspot long-form missing-image requests

**Files:**
- Modify: `scripts/tools/wechat_mp_codex_images.py`
- Modify: `scripts/tools/wechat_mp_content.py`
- Modify: `tests/unit/test_wechat_mp_codex_images.py`
- Modify: `tests/unit/test_wechat_mp_codex_hotspot.py`

**Interfaces:**
- `prepare_hotspot_topic_images` fetches reports, confirms one cover plus three body images, and raises `CodexImageGenerationRequired` before article rendering when generated files are needed.
- `build_hotspot_article` calls the preparer only when social-layout figures are enabled.

- [ ] **Step 1: Write the failing hotspot request tests**

```python
def test_prepare_hotspot_requests_cover_and_missing_body_slots(tmp_path, monkeypatch):
    monkeypatch.setattr(images_mod, "INLINE_DISCUSSION_ROOT", tmp_path)
    monkeypatch.setattr(images_mod, "ensure_discussion_figures", lambda topic, max_images: [])
    monkeypatch.setattr(images_mod, "ensure_discussion_body_figures", lambda topic, max_images: [])

    with pytest.raises(CodexImageGenerationRequired) as caught:
        prepare_hotspot_topic_images({"cover_slug": "topic", "trend_title": "事件"}, body_count=3)

    request = json.loads(caught.value.request_path.read_text(encoding="utf-8"))
    assert [Path(slot["output_path"]).name for slot in request["slots"]] == [
        "cover.jpg", "manual-01.jpg", "manual-02.jpg", "manual-03.jpg"
    ]
```

```python
def test_hotspot_builder_prepares_images_before_injection(monkeypatch):
    calls = []
    monkeypatch.setattr(codex_images, "prepare_hotspot_topic_images", lambda topic, body_count=3: calls.append(topic))
    # Stub existing body/cover render helpers and build a valid Codex hotspot draft.
    article = content_mod.build_hotspot_article(codex_draft=_valid_codex_draft())
    assert calls and calls[0]["trend_title"] == _valid_codex_draft().topic
    assert article["kind"] == "hotspot"
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `uv run pytest tests/unit/test_wechat_mp_codex_images.py tests/unit/test_wechat_mp_codex_hotspot.py -q`

Expected: failures show the hotspot preparer and builder hook are missing.

- [ ] **Step 3: Implement the hotspot preparer and builder hook**

Call the report fetcher first. Treat an existing valid `cover.jpg` as the cover; otherwise a usable report still allows the existing cover cropper to create it. Ask Codex for `cover.jpg` only when neither exists. Count existing body figures through `ensure_discussion_body_figures`, reserve sequential unused `manual-NN.jpg` names, write one request for all gaps, and call the preparer immediately before `inject_discussion_figures`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `uv run pytest tests/unit/test_wechat_mp_codex_images.py tests/unit/test_wechat_mp_codex_hotspot.py tests/unit/test_wechat_mp_discussion_figures.py -q`

Expected: all focused long-form image tests pass.

### Task 3: Add topic-driven automatic images to the newspic CLI

**Files:**
- Modify: `scripts/tools/wechat_mp_newspic_draft.py`
- Modify: `tests/unit/test_wechat_mp_newspic.py`

**Interfaces:**
- Produces: `_resolve_newspic_images(args: argparse.Namespace) -> tuple[list[Path], Path]`.
- CLI adds `--topic`, repeatable `--research-url`, `--image-count` constrained to 6 through 9, and a no-upload `--dry-run` validation mode.

- [ ] **Step 1: Write failing CLI resolution tests**

```python
def test_resolve_newspic_images_uses_topic_preparer(monkeypatch, tmp_path):
    sources = tmp_path / "image-sources.json"
    images = (tmp_path / "a.jpg", tmp_path / "b.jpg")
    monkeypatch.setattr(newspic_cli, "prepare_newspic_topic_images", lambda **kwargs:
        PreparedTopicImages(image_paths=images, sources_path=sources))
    args = Namespace(topic="事件", research_url=["https://example.com/a"], image_count=6,
                     images=None, image_sources=None)
    resolved, source_path = newspic_cli._resolve_newspic_images(args)
    assert resolved == list(images)
    assert source_path == sources
```

Add parameter validation tests showing `--topic` cannot be combined with `--images`, and manual mode rejects either `--images` or `--image-sources` when its pair is absent.

- [ ] **Step 2: Run CLI tests and verify RED**

Run: `uv run pytest tests/unit/test_wechat_mp_newspic.py -q`

Expected: failure because the resolver and automatic arguments do not exist.

- [ ] **Step 3: Implement automatic and compatible manual modes**

Make `--images` and `--image-sources` optional at parser level, then validate the two modes before any fetch or upload. Catch `CodexImageGenerationRequired`, print the request path and a concise instruction to generate the listed files and rerun, and return exit code 2. Pass the resolved images and generated source path into the unchanged `upsert_newspic_draft` function.

- [ ] **Step 4: Run CLI tests and verify GREEN**

Run: `uv run pytest tests/unit/test_wechat_mp_newspic.py tests/unit/test_wechat_mp_codex_images.py -q`

Expected: all newspic tests pass.

### Task 4: Document the Codex continuation contract and verify both workflows

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/newspic-sop.md`
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`

**Interfaces:**
- Documents the automatic newspic command, exit-code-2 continuation, request JSON, ImageGen save-and-rerun sequence, and legacy manual command.

- [ ] **Step 1: Update the routed Skill documentation**

State explicitly that Python performs web acquisition and Codex performs original generation. Include the automatic newspic command and the rule that Codex must read every request slot, generate only those files, save to each absolute `output_path`, and rerun the exact command.

- [ ] **Step 2: Run the complete focused test suite**

Run:

```bash
uv run pytest \
  tests/unit/test_wechat_mp_codex_images.py \
  tests/unit/test_wechat_mp_codex_hotspot.py \
  tests/unit/test_wechat_mp_discussion_figures.py \
  tests/unit/test_wechat_mp_newspic.py \
  tests/unit/test_wechat_mp_hotspot_article.py \
  tests/unit/test_wechat_mp_discussion_polish.py -q
```

Expected: zero failures.

- [ ] **Step 3: Run compile, CLI, and hygiene verification**

Run:

```bash
uv run python -m compileall -q scripts/tools/wechat_mp_codex_images.py scripts/tools/wechat_mp_newspic_draft.py scripts/tools/wechat_mp_content.py
uv run python -m scripts.tools.wechat_mp_newspic_draft --help
uv run python -m scripts.tools.wechat_mp_draft --help
git diff --check
git status --short
```

Expected: compile and help commands exit 0; help shows `--topic`, `--research-url`, `--image-count`, and `--codex-draft`; no secret or generated media is included in the change.

- [ ] **Step 4: Commit implementation files**

```bash
git add \
  stock-ai/scripts/tools/wechat_mp_codex_images.py \
  stock-ai/scripts/tools/wechat_mp_content.py \
  stock-ai/scripts/tools/wechat_mp_newspic_draft.py \
  stock-ai/tests/unit/test_wechat_mp_codex_images.py \
  stock-ai/tests/unit/test_wechat_mp_codex_hotspot.py \
  stock-ai/tests/unit/test_wechat_mp_newspic.py \
  .cursor/skills/wechat-mp-drafts/newspic-sop.md \
  .cursor/skills/wechat-mp-writing/hotspot-deep-review.md \
  .cursor/skills/wechat-mp-drafts/SKILL.md
git commit -m "feat: automate wechat image fallback"
```
