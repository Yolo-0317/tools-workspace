# Hotspot Cover Body Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow a hotspot article's verified cover image to be reused in the body only when the per-topic manifest explicitly enables it.

**Architecture:** Extend `cover_source.json` with the optional boolean `reuse_in_body`, read both cover preferences through one small helper, and keep the existing verified-image selection pipeline unchanged otherwise. The default remains cover exclusion; when enabled, the selected cover becomes the first body candidate and still counts toward the existing `max_body <= 3` limit.

**Tech Stack:** Python 3, `dataclasses`, `pathlib`, JSON, Pillow, pytest, Markdown Skill documentation.

## Global Constraints

- `reuse_in_body` is optional and defaults to `false` for missing, invalid, or non-boolean values.
- A reused cover counts toward the body limit of `0–3` images.
- `max_body=0` always returns no body images.
- Douyin remains the first image source; only search-result cards and visible cover images may be read, without opening or playing videos.
- Use only traceable real images, allow fewer than three body images, and never generate images to fill gaps.
- Do not change article production, publishing APIs, or existing drafts.
- User-visible copy and reports must not contain emoji.

---

### Task 1: Add manifest-controlled cover reuse with TDD

**Files:**
- Modify: `stock-ai/tests/unit/test_wechat_mp_hotspot_image_policy.py:35-202`
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_image_policy.py:194-239`

**Interfaces:**
- Consumes: `cover_source.json` with existing `source_filename: str` and optional `reuse_in_body: bool`.
- Produces: `_load_cover_preferences(out_dir: Path) -> tuple[str, bool]`; `validate_verified_hotspot_images(...)` keeps its public signature and returns the selected cover in `body_figures` only when reuse is enabled.

- [ ] **Step 1: Add a test helper that writes cover preferences**

Add beside the existing image fixture helpers:

```python
def _write_cover_source(
    out_dir: Path,
    *,
    source_filename: str = "still-01.jpg",
    reuse_in_body: object = False,
) -> None:
    (out_dir / "cover_source.json").write_text(
        json.dumps(
            {
                "source_filename": source_filename,
                "reuse_in_body": reuse_in_body,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
```

- [ ] **Step 2: Write failing tests for explicit reuse, limit enforcement, zero limit, and invalid values**

Add tests that reuse the existing Douyin and verified-image fixtures:

```python
def _prepare_verified_images(out_dir: Path, image_count: int = 4) -> None:
    _write_douyin_state(
        out_dir,
        topic="测试热点",
        candidates=[_douyin_candidate()],
    )
    for index in range(1, image_count + 1):
        _write_verified_image(
            out_dir,
            f"still-{index:02d}.jpg",
            source_type=(
                "douyin_cover"
                if index == 1
                else "official_media_webpage_screenshot"
            ),
            page_url=(
                "https://www.douyin.com/video/123"
                if index == 1
                else f"https://example.com/report-{index}"
            ),
        )


def test_explicit_cover_reuse_places_cover_first_in_body(tmp_path: Path) -> None:
    validate = _load_api()
    _prepare_verified_images(tmp_path)
    _write_cover_source(tmp_path, reuse_in_body=True)

    result = validate(tmp_path, expected_topic="测试热点")

    assert [figure.path.name for figure in result.body_figures] == [
        "still-01.jpg",
        "still-02.jpg",
        "still-03.jpg",
    ]


def test_cover_reuse_obeys_requested_body_limit(tmp_path: Path) -> None:
    validate = _load_api()
    _prepare_verified_images(tmp_path)
    _write_cover_source(tmp_path, reuse_in_body=True)

    result = validate(tmp_path, expected_topic="测试热点", max_body=2)

    assert [figure.path.name for figure in result.body_figures] == [
        "still-01.jpg",
        "still-02.jpg",
    ]


def test_cover_reuse_with_zero_body_limit_returns_no_body_images(
    tmp_path: Path,
) -> None:
    validate = _load_api()
    _prepare_verified_images(tmp_path)
    _write_cover_source(tmp_path, reuse_in_body=True)

    result = validate(tmp_path, expected_topic="测试热点", max_body=0)

    assert result.body_figures == ()


@pytest.mark.parametrize("invalid_value", ["true", 1, None, [], {}])
def test_non_boolean_cover_reuse_value_keeps_cover_out_of_body(
    tmp_path: Path,
    invalid_value: object,
) -> None:
    validate = _load_api()
    _prepare_verified_images(tmp_path, image_count=2)
    _write_cover_source(tmp_path, reuse_in_body=invalid_value)

    result = validate(tmp_path, expected_topic="测试热点")

    assert [figure.path.name for figure in result.body_figures] == [
        "still-02.jpg"
    ]
```

Retain the existing parameterized test as coverage for missing configuration and default cover exclusion. Add the malformed JSON case below:

```python
def test_malformed_cover_source_keeps_cover_out_of_body(tmp_path: Path) -> None:
    validate = _load_api()
    _prepare_verified_images(tmp_path, image_count=2)
    (tmp_path / "cover_source.json").write_text("{", encoding="utf-8")

    result = validate(tmp_path, expected_topic="测试热点")

    assert [figure.path.name for figure in result.body_figures] == [
        "still-02.jpg"
    ]
```

- [ ] **Step 3: Run the new tests and confirm the expected failure**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest \
  tests/unit/test_wechat_mp_hotspot_image_policy.py \
  -k "cover_reuse" -q
```

Expected: the explicit-reuse tests fail because the current implementation always excludes `cover.path`; default and invalid-value cases may already pass.

- [ ] **Step 4: Implement strict preference loading and body candidate selection**

Replace `_requested_cover_name` with:

```python
def _load_cover_preferences(out_dir: Path) -> tuple[str, bool]:
    path = out_dir / COVER_SOURCE_FILENAME
    if not path.is_file():
        return "", False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "", False
    if not isinstance(payload, dict):
        return "", False
    requested = str(payload.get("source_filename") or "").strip()
    reuse_in_body = payload.get("reuse_in_body") is True
    return requested, reuse_in_body
```

Then replace the existing block from `requested = ...` through `body = ...` with the complete selection logic below. The `figures` list is already sorted deterministically by filename; because the configured cover may not be the first figure, reuse must always start with the actual selected cover:

```python
requested, reuse_in_body = _load_cover_preferences(root)
cover = by_name.get(requested)
if cover is None and selected_urls:
    cover = next(
        (figure for figure in figures if figure.page_url in selected_urls),
        None,
    )
if cover is None:
    cover = figures[0]
body_candidates = (
    [cover, *(figure for figure in figures if figure.path != cover.path)]
    if reuse_in_body
    else [figure for figure in figures if figure.path != cover.path]
)
body = tuple(body_candidates[:max_body])
```

- [ ] **Step 5: Run the focused file and confirm all tests pass**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest \
  tests/unit/test_wechat_mp_hotspot_image_policy.py -q
```

Expected: all tests in the file pass, including missing configuration, strict boolean handling, malformed JSON fallback, explicit reuse, and body limits.

- [ ] **Step 6: Commit the tested policy change**

```bash
git add \
  stock-ai/scripts/tools/wechat_mp_hotspot_image_policy.py \
  stock-ai/tests/unit/test_wechat_mp_hotspot_image_policy.py
git commit -m "功能：支持热点封面按需复用于正文"
```

---

### Task 2: Align the WeChat Skills with the executable policy

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md:145-151`
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md:114-127`
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md:217-224`

**Interfaces:**
- Consumes: Task 1's `cover_source.json` field `reuse_in_body: bool`.
- Produces: one consistent human-readable rule for Agent decisions, manifest recording, image limits, and final checklist validation.

- [ ] **Step 1: Update the main draft Skill image protocol**

After the current paragraph describing verified images and the `0—3` body limit, add:

```markdown
封面可按需复用于正文，不视为重复冲突；复用后计入正文 0—3 张上限。是否复用由 Agent 根据内容与素材决定，不要求每篇复用。需要复用时在该选题的 `cover_source.json` 中显式写入 `"reuse_in_body": true`；未声明或为 `false` 时仍从正文图片中排除封面。
```

Do not weaken the surrounding Douyin-first, real-image-only, or no-generation rules.

- [ ] **Step 2: Update the hotspot deep-review table and explanation**

Replace the body-image row with:

```markdown
| 正文图 | 0—3 张，按已核验真实图数量注入；封面可由 Agent 根据内容按需复用，复用后计入上限 |
```

Add this row after `留痕`:

```markdown
| 封面复用 | 需要复用时在 `cover_source.json` 显式设置 `"reuse_in_body": true`；未声明或为 `false` 时不复用 |
```

Change the quantity rule so “重复帧” remains prohibited while intentional cover reuse is not treated as duplication:

```markdown
| 数量原则 | 有几张用几张，正文允许少图；除显式复用封面外，不得使用搬运图、重复帧、无关画面或生成图 |
```

Add after the table:

```markdown
封面复用是单篇稿件的内容判断，不是默认动作。只有封面能够自然承接正文段落、且复用不会降低阅读体验时才启用；不得为增加图片数量机械复用。
```

- [ ] **Step 3: Update the final checklist to distinguish intentional reuse from accidental duplication**

Replace the image checklist line with:

```markdown
- [ ] 至少 1 张可追溯真实封面；正文 0—3 张，均与事件相关；如复用封面，已在 `cover_source.json` 显式声明且计入上限
```

- [ ] **Step 4: Run consistency checks over both Skills**

Run:

```bash
rg -n "reuse_in_body|封面可.*复用|正文 0—3|禁止.*生成|禁止点击、打开或播放视频" \
  .cursor/skills/wechat-mp-drafts/SKILL.md \
  .cursor/skills/wechat-mp-writing/hotspot-deep-review.md
```

Expected: both Skills mention optional cover reuse, the body limit remains `0—3`, the hotspot Skill names `reuse_in_body`, and both still prohibit generated hotspot images and opening/playing Douyin videos.

- [ ] **Step 5: Commit the Skill documentation change**

```bash
git add \
  .cursor/skills/wechat-mp-drafts/SKILL.md \
  .cursor/skills/wechat-mp-writing/hotspot-deep-review.md
git commit -m "文档：统一热点封面正文复用规则"
```

---

### Task 3: Run final regression and scope verification

**Files:**
- Verify: `stock-ai/scripts/tools/wechat_mp_hotspot_image_policy.py`
- Verify: `stock-ai/tests/unit/test_wechat_mp_hotspot_image_policy.py`
- Verify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Verify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`

**Interfaces:**
- Consumes: the executable policy and Skill wording from Tasks 1–2.
- Produces: evidence that the change is backward compatible, internally consistent, and isolated from unrelated working-tree changes.

- [ ] **Step 1: Run the focused policy suite**

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest \
  tests/unit/test_wechat_mp_hotspot_image_policy.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run the related WeChat unit-test group**

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest tests/unit/test_wechat_mp_*.py -q
```

Expected: all collected related tests pass. If an unrelated pre-existing failure appears, record the exact test and error without modifying unrelated code.

- [ ] **Step 3: Check formatting and the exact diff**

```bash
git diff --check
git diff -- \
  stock-ai/scripts/tools/wechat_mp_hotspot_image_policy.py \
  stock-ai/tests/unit/test_wechat_mp_hotspot_image_policy.py \
  .cursor/skills/wechat-mp-drafts/SKILL.md \
  .cursor/skills/wechat-mp-writing/hotspot-deep-review.md
```

Expected: `git diff --check` is clean, and the scoped diff contains only the approved behavior and wording changes. Do not stage or alter unrelated files already present in the dirty worktree.

- [ ] **Step 4: Report completion evidence**

Report the focused and related test counts, the two implementation commit IDs, and the four modified files. State explicitly that existing drafts were not repushed and unrelated working-tree changes were left untouched.
