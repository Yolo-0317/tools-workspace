# Zhixia Film Sharing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add popular-film, classic-film, film-list and AI-film posts to Zhixia's newspic workflow while enforcing the approved 50/40/10 whole-account mix, film-specific copy rules, traceable image sources and publication-only counting.

**Architecture:** Keep the existing `virtual_lifestyle` draft transport and publication ledger. Expand the editorial module with eight content lanes and a non-sequential remaining-lanes gate, add a focused film editorial module for film-only rules, then pass `content_lane` through newspic validation, the CLI and the publication ledger. Draft creation remains separate from the read-only publication sync and never publishes automatically.

**Tech Stack:** Python 3.11, pytest, Pillow, JSON topic cards, WeChat draft/freepublish APIs already wrapped by the project.

## Global Constraints

- User-visible copy and reports contain no emoji.
- Film content is 50%, life and other hotspots are 40%, and system logs are 10% per ten valid published posts.
- Per ten posts, lanes must total `popular_film=2`, `classic_single=1`, `classic_list=1`, `ai_film=1`, `nonfilm_hotspot=2`, `zhixia_daily=1`, `ai_human=1`, `system_log=1`.
- Drafts, previews, failed updates, unpublished posts and `status=invalid` posts never increment lane counts.
- Published order remains flexible: the gate accepts any lane with remaining quota and rejects only a filled lane unless an override reason is recorded.
- Popular films and non-film hotspots require facts rechecked within six hours; classic single/list content is evergreen.
- Hot film posts use 4–6 images and 180–320 characters; classic singles use 5–7 images and 250–450 characters; classic lists use 6–9 images and 300–600 characters; AI-film posts use 4–6 images and 180–320 characters.
- Film posts do not require a Zhixia character image. At most one optional author image may appear, and it must use an explainable capture mode.
- Official posters, official stills and media report images never receive the Zhixia watermark.
- Body copy never exposes prompts, selection scores, retrieval steps, generation rules or internal reasoning.
- Body copy never invents real viewing, cinema attendance, interviews, purchases or emotional reactions for Zhixia.
- No code path imports or calls `freepublish_submit`.
- Do not commit `.env`, credentials, pending/history JSON, generated runtime output or personal assets.

---

## File Structure

- Modify `stock-ai/scripts/tools/wechat_mp_virtual_editorial.py`: shared topic-card fields, eight content lanes, lane quotas, remaining-lanes calculation and evergreen/time-sensitive routing.
- Create `stock-ai/scripts/tools/wechat_mp_virtual_film.py`: film topic-card fields, film title/copy/spoiler/image-count validation and process-language rejection.
- Modify `stock-ai/scripts/tools/wechat_mp_newspic.py`: film image ranges, optional author images, official-film source types and content-lane propagation into draft upsert.
- Modify `stock-ai/scripts/tools/wechat_mp_newspic_draft.py`: content-lane gate, film validation, dry-run output and transport arguments.
- Modify `stock-ai/scripts/tools/wechat_mp_virtual_ledger.py`: persist `content_lane`, film metadata and publication-only lane counts.
- Modify existing unit tests and create `stock-ai/tests/unit/test_wechat_mp_virtual_film.py`.
- Update `.cursor/skills/wechat-mp-virtual-lifestyle/SKILL.md` and its persona/story references with the approved film workflow.

---

### Task 1: Eight-Lane Editorial Mix and Topic Cards

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_virtual_editorial.py:13-184`
- Modify: `stock-ai/tests/unit/test_wechat_mp_virtual_editorial.py`

**Interfaces:**
- Produces: `CONTENT_LANES`, `LANE_TARGETS`, `LANE_CONTENT_TYPES`, `TIME_SENSITIVE_LANES`.
- Produces: `content_lane_counts(posts: Iterable[Mapping[str, Any]]) -> dict[str, int]`.
- Produces: `available_content_lanes(posts: Iterable[Mapping[str, Any]]) -> list[str]`.
- Changes: `validate_topic_card(card: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]` returns normalized `content_lane` and validates that its `content_type` matches `LANE_CONTENT_TYPES[content_lane]`.
- Keeps: `content_mix_counts(posts: Iterable[Mapping[str, Any]]) -> dict[str, int]` as a compatibility summary over A / B / A+C / C.

- [ ] **Step 1: Write failing tests for lane quotas and flexible order**

Add tests equivalent to:

```python
def test_available_content_lanes_accepts_any_unfilled_lane() -> None:
    posts = [{"content_lane": "popular_film", "status": "published"}]

    available = available_content_lanes(posts)

    assert "popular_film" in available
    assert "classic_single" in available
    assert "system_log" in available


def test_filled_lane_is_removed_without_forcing_post_order() -> None:
    posts = [
        {"content_lane": "popular_film", "status": "published"},
        {"content_lane": "popular_film", "status": "published"},
    ]

    assert "popular_film" not in available_content_lanes(posts)
    assert "classic_list" in available_content_lanes(posts)


def test_lane_counts_ignore_invalid_and_previous_complete_round() -> None:
    first_round = [
        *[{"content_lane": "popular_film", "status": "published"} for _ in range(2)],
        {"content_lane": "classic_single", "status": "published"},
        {"content_lane": "classic_list", "status": "published"},
        {"content_lane": "ai_film", "status": "published"},
        *[{"content_lane": "nonfilm_hotspot", "status": "published"} for _ in range(2)],
        {"content_lane": "zhixia_daily", "status": "published"},
        {"content_lane": "ai_human", "status": "published"},
        {"content_lane": "system_log", "status": "published"},
    ]
    posts = [
        *first_round,
        {"content_lane": "popular_film", "status": "invalid"},
        {"content_lane": "classic_single", "status": "published"},
    ]

    assert content_lane_counts(posts)["classic_single"] == 1
    assert content_lane_counts(posts)["popular_film"] == 0
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest tests/unit/test_wechat_mp_virtual_editorial.py -q
```

Expected: collection or assertion failure because lane constants/functions do not exist and `content_type=B` is rejected.

- [ ] **Step 3: Implement lane constants and remaining-quota calculation**

Use these exact mappings:

```python
CONTENT_TYPES = ("A", "B", "A+C", "C")
CONTENT_LANES = (
    "popular_film",
    "classic_single",
    "classic_list",
    "ai_film",
    "nonfilm_hotspot",
    "zhixia_daily",
    "ai_human",
    "system_log",
)
LANE_TARGETS = {
    "popular_film": 2,
    "classic_single": 1,
    "classic_list": 1,
    "ai_film": 1,
    "nonfilm_hotspot": 2,
    "zhixia_daily": 1,
    "ai_human": 1,
    "system_log": 1,
}
LANE_CONTENT_TYPES = {
    "popular_film": "A",
    "classic_single": "B",
    "classic_list": "B",
    "ai_film": "A+C",
    "nonfilm_hotspot": "A",
    "zhixia_daily": "B",
    "ai_human": "A+C",
    "system_log": "C",
}
TIME_SENSITIVE_LANES = {"popular_film", "nonfilm_hotspot"}
```

`available_content_lanes()` must return every lane whose current count is below `LANE_TARGETS`, preserving `CONTENT_LANES` order. When a round already has ten valid posts, `_current_round_posts()` starts a new empty round and all lanes are available.

- [ ] **Step 4: Extend topic-card validation without imposing film-only fields**

Add `content_lane` to shared required fields. Reject unknown lanes and reject mismatches such as `content_type=B` with `content_lane=popular_film`. Apply the six-hour check only to `TIME_SENSITIVE_LANES`. Require at least one traceable fact source for all film lanes and time-sensitive lanes; allow empty facts for `zhixia_daily` and `system_log`.

Permit `character_image_policy` values `default_one`, `optional_one` and `story_multiple`; `optional_one` is valid only for film lanes.

- [ ] **Step 5: Run editorial tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_wechat_mp_virtual_editorial.py -q
```

Expected: all tests pass, including updated legacy tests that now include `content_lane`.

- [ ] **Step 6: Commit Task 1**

```bash
git add stock-ai/scripts/tools/wechat_mp_virtual_editorial.py stock-ai/tests/unit/test_wechat_mp_virtual_editorial.py
git commit -m "feat: add Zhixia content lane quotas"
```

---

### Task 2: Film Topic, Copy, Spoiler and Title Gates

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_virtual_film.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_virtual_film.py`

**Interfaces:**
- Consumes: normalized topic cards from `validate_topic_card(card, now=now)`.
- Produces: `FILM_LANES`, `FILM_RULES`, `validate_film_topic_card(card: Mapping[str, Any]) -> dict[str, Any]`.
- Produces: `validate_film_copy(*, title: str, content: str, card: Mapping[str, Any], image_count: int, has_original_images: bool) -> str`.

- [ ] **Step 1: Write failing topic-card tests**

Cover these exact behaviors:

```python
def test_classic_list_requires_three_to_five_film_titles() -> None:
    card = film_card(content_lane="classic_list", film_titles=["一", "二"])
    with pytest.raises(ValueError, match="3-5"):
        validate_film_topic_card(card)


def test_popular_film_requires_release_status_and_s0() -> None:
    card = film_card(
        content_lane="popular_film",
        release_status="released",
        spoiler_level="S1",
    )
    with pytest.raises(ValueError, match="S0"):
        validate_film_topic_card(card)


def test_classic_single_accepts_evergreen_s2() -> None:
    card = film_card(
        content_lane="classic_single",
        release_status="evergreen",
        spoiler_level="S2",
    )
    assert validate_film_topic_card(card)["spoiler_level"] == "S2"
```

Film cards require `film_titles`, `spoiler_level`, `release_status` and `image_rights_status`. Use release values `announced`, `presale`, `released`, `reputation`, `evergreen`. `popular_film` may use the first four and must use S0. `classic_single` and `classic_list` require `evergreen`; lists must use S0. `ai_film` may use any release value and S0/S1/S2.

- [ ] **Step 2: Write failing copy and image-count tests**

Add tests for:

```python
def test_popular_film_requires_four_to_six_images() -> None:
    with pytest.raises(ValueError, match="4-6"):
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content=valid_copy(220),
            card=film_card(content_lane="popular_film"),
            image_count=3,
            has_original_images=False,
        )


@pytest.mark.parametrize("phrase", [
    "作为 AI，我分析了",
    "经过资料检索",
    "根据内容规则",
    "刚从电影院出来",
    "昨晚二刷",
])
def test_copy_rejects_process_language_and_fake_viewing(phrase: str) -> None:
    with pytest.raises(ValueError, match="正文不得"):
        validate_film_copy(
            title="《一部电影》最安静的不是结尾",
            content=phrase + valid_copy(220),
            card=film_card(content_lane="popular_film"),
            image_count=4,
            has_original_images=False,
        )


def test_s2_requires_spoiler_notice_at_start() -> None:
    with pytest.raises(ValueError, match="含结局讨论"):
        validate_film_copy(
            title="《一部旧电影》最难的不是告别",
            content=valid_copy(300),
            card=film_card(content_lane="classic_single", spoiler_level="S2"),
            image_count=5,
            has_original_images=False,
        )
```

- [ ] **Step 3: Run film tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_wechat_mp_virtual_film.py -q
```

Expected: import failure because the film module does not exist.

- [ ] **Step 4: Implement the film rules table and validators**

Use:

```python
FILM_LANES = ("popular_film", "classic_single", "classic_list", "ai_film")
FILM_RULES = {
    "popular_film": {"images": (4, 6), "copy": (180, 320), "titles": (1, 1)},
    "classic_single": {"images": (5, 7), "copy": (250, 450), "titles": (1, 1)},
    "classic_list": {"images": (6, 9), "copy": (300, 600), "titles": (3, 5)},
    "ai_film": {"images": (4, 6), "copy": (180, 320), "titles": (1, 1)},
}
```

For single-film lanes, require the exact film title to appear in the post title. For `classic_list`, require a numeric marker from `3`, `4`, `5`, `三`, `四`, `五` in the title. Reject hype phrases `一生必看`, `封神`, `全网泪崩`, `后劲太大`, `看懂的人都沉默了`.

Require the fixed AI-character disclosure. If `has_original_images=True`, also require `AI 生成示意图`. If S2, the first non-empty line must contain `含结局讨论`.

- [ ] **Step 5: Run film tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_wechat_mp_virtual_film.py -q
```

Expected: all film validator tests pass.

- [ ] **Step 6: Commit Task 2**

```bash
git add stock-ai/scripts/tools/wechat_mp_virtual_film.py stock-ai/tests/unit/test_wechat_mp_virtual_film.py
git commit -m "feat: validate Zhixia film posts"
```

---

### Task 3: Film Image Sources and 4–9 Image Transport

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_newspic.py:30-210,354-414`
- Modify: `stock-ai/tests/unit/test_wechat_mp_newspic.py`

**Interfaces:**
- Changes: `validate_newspic_input(*, title: str, content: str, image_paths: Iterable[Path], draft_profile: str = "newspic", content_lane: str = "") -> list[Path]`.
- Changes: `validate_newspic_image_sources(*, image_paths: Iterable[Path], sources_path: Path, content: str | None = None, draft_profile: str = "newspic", content_type: str = "", content_lane: str = "", character_image_policy: str = "default_one", visual_exception: str = "") -> dict[str, dict[str, Any]]`.
- Changes: `upsert_newspic_draft(*, slot_key: str, title: str, content: str, image_paths: Iterable[Path], image_sources_path: Path | None = None, author: str = "", force_reupload: bool = False, watermark: str = "", content_lane: str = "", character_image_policy: str = "default_one", visual_exception: str = "") -> tuple[str, str]`.
- Adds accepted source types: `film_official`, `film_media`.

- [ ] **Step 1: Write failing tests for film image ranges**

Create real temporary images and assert:

```python
def test_classic_list_accepts_nine_images(tmp_path: Path) -> None:
    images = make_images(tmp_path, 9)
    assert len(validate_newspic_input(
        title="不想再看逆袭时翻出的4部老片",
        content="甲" * 400,
        image_paths=images,
        draft_profile="virtual_lifestyle",
        content_lane="classic_list",
    )) == 9


def test_popular_film_rejects_seven_images(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="4-6"):
        validate_newspic_input(
            title="《一部电影》最安静的不是结尾",
            content="甲" * 220,
            image_paths=make_images(tmp_path, 7),
            draft_profile="virtual_lifestyle",
            content_lane="popular_film",
        )
```

Non-film virtual posts retain their existing 2–6 image behavior.

- [ ] **Step 2: Write failing source metadata tests**

For `film_official` and `film_media`, require `film_title`, `page_url`, `page_title`, `source_name` and `allow_zhixia_watermark=false`. Assert that a film post with zero character images passes when `character_image_policy=optional_one`, and two character images fail.

```python
def test_official_film_still_cannot_receive_zhixia_watermark(
    tmp_path: Path,
) -> None:
    image = tmp_path / "still.jpg"
    Image.new("RGB", (640, 960), color=(30, 60, 90)).save(image)
    metadata = {
        "still.jpg": {
            "source_type": "film_official",
            "film_title": "一部电影",
            "page_url": "https://example.com/official",
            "page_title": "官方宣传物料",
            "source_name": "影片官方",
            "visual_role": "topic",
            "position_role": "hook",
            "allow_zhixia_watermark": True,
        }
    }
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="不得添加栀夏水印"):
        validate_newspic_image_sources(
            image_paths=[image],
            sources_path=sources,
            content="栀夏是 AI 虚拟角色；本文基于影片公开资料形成。",
            draft_profile="virtual_lifestyle",
            content_type="A",
            content_lane="popular_film",
            character_image_policy="optional_one",
        )
```

- [ ] **Step 3: Run focused newspic tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_wechat_mp_newspic.py -q
```

Expected: failures because `content_lane` is not accepted, film source types are unknown and virtual posts still require a character image.

- [ ] **Step 4: Implement film-aware input and source validation**

Import `FILM_LANES` and `FILM_RULES` lazily or at module level without creating a cycle. When `draft_profile=virtual_lifestyle` and `content_lane` is a film lane, take the image and copy ranges from `FILM_RULES`; otherwise preserve existing virtual ranges.

For film lanes:

- `optional_one` accepts zero or one character image and requires at least one topic image.
- Any character image still requires `capture_mode`.
- `film_official`, `film_media` and `report` images must have `allow_zhixia_watermark=false`.
- Every `film_official` or `film_media` record must contain all five traceability fields.
- Original theme visuals still require `fallback_reason` and trigger AI-generated-image disclosure.

- [ ] **Step 5: Propagate film parameters through draft upsert**

Pass `content_lane`, `character_image_policy` and `visual_exception` into both local validation calls inside `upsert_newspic_draft`. Do not change upload, draft update, remote readback or slot behavior.

- [ ] **Step 6: Run newspic tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_wechat_mp_newspic.py -q
```

Expected: all existing and new tests pass.

- [ ] **Step 7: Commit Task 3**

```bash
git add stock-ai/scripts/tools/wechat_mp_newspic.py stock-ai/tests/unit/test_wechat_mp_newspic.py
git commit -m "feat: support film image-post assets"
```

---

### Task 4: CLI and Publication Ledger Integration

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_newspic_draft.py:23-205`
- Modify: `stock-ai/scripts/tools/wechat_mp_virtual_ledger.py:41-177`
- Modify: `stock-ai/tests/unit/test_wechat_mp_newspic.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_virtual_ledger.py`

**Interfaces:**
- Consumes: `available_content_lanes`, `FILM_LANES`, `validate_film_topic_card`, `validate_film_copy`.
- Persists: `content_lane`, `film_titles`, `spoiler_level` in pending and published records.
- Dry-run output includes the selected lane and all currently available lanes.

- [ ] **Step 1: Write failing CLI tests for flexible lane selection**

Add a valid `classic_single` card whose `observed_at` is older than six hours. Use five real images with official-film metadata, no character image, and run `--dry-run`.

```python
def test_classic_single_dry_run_accepts_evergreen_card(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    card_path, sources_path, image_paths, copy_path = build_classic_single_case(tmp_path)
    monkeypatch.setattr(draft_cli, "load_virtual_history", lambda: {"posts": []})
    monkeypatch.setattr(
        "sys.argv",
        [
            "wechat_mp_newspic_draft",
            "--slot", "virtual_lifestyle",
            "--topic-card", str(card_path),
            "--title", "《一部旧电影》最难的不是告别",
            "--content", str(copy_path),
            "--images", *[str(path) for path in image_paths],
            "--image-sources", str(sources_path),
            "--dry-run",
        ],
    )

    assert draft_cli.main() == 0
    assert "classic_single" in capsys.readouterr().out
```

Define `build_classic_single_case(tmp_path)` in the same test module. It must create five `640x960` JPEG files, a JSON source map in which every file is `source_type=film_official` with all traceability fields and `allow_zhixia_watermark=false`, a B / `classic_single` topic card with one film title, S1 and `release_status=evergreen`, and a 250–450 character copy file ending in the fixed AI-character disclosure.

Also fill `popular_film` twice in mocked history and assert a third `popular_film` card is rejected while `classic_single` remains accepted. The error must say `当前轮次 popular_film 已满` instead of forcing a single next lane.

- [ ] **Step 2: Write failing ledger persistence tests**

Update pending helpers and assert:

```python
def test_pending_and_publication_preserve_film_lane(tmp_path: Path) -> None:
    pending = record_pending_draft(
        media_id="draft-1",
        title="《一部电影》最安静的不是结尾",
        topic_card=film_card(
            content_lane="popular_film",
            film_titles=["一部电影"],
            spoiler_level="S0",
        ),
        topic_card_sha256="abc123",
        pending_path=tmp_path / "pending.json",
    )
    ledger = record_verified_publication(
        pending=pending,
        publication=published(title=pending["title"]),
        ledger_path=tmp_path / "history.json",
    )

    assert ledger["posts"][0]["content_lane"] == "popular_film"
    assert ledger["posts"][0]["film_titles"] == ["一部电影"]
    assert ledger["posts"][0]["spoiler_level"] == "S0"
```

- [ ] **Step 3: Run CLI and ledger tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_newspic.py \
  tests/unit/test_wechat_mp_virtual_ledger.py -q
```

Expected: classic film dry-run fails, lane-full behavior is missing and ledger records omit film fields.

- [ ] **Step 4: Replace the strict next-type gate with available lanes**

In the CLI:

1. Load and normalize the shared topic card.
2. If its lane is a film lane, call `validate_film_topic_card`.
3. Compute `available_content_lanes(history["posts"])`.
4. Reject only when the selected lane is absent and `--allow-mix-override` is blank.
5. Pass `content_lane`, policy and visual exception to newspic validators and upsert.
6. Use `validate_film_copy` for film lanes; retain `validate_opinion_copy` for non-film lanes.

Dry-run output format:

```text
DRY-RUN [virtual_lifestyle] 通道 classic_single · 类型 B · 评分 84 · 可用 popular_film,classic_single,classic_list,ai_film,nonfilm_hotspot,zhixia_daily,ai_human,system_log · 图片 5 张 · 标题
```

Change the override help text from `7:2:1` to `当前十条内容通道比例`.

- [ ] **Step 5: Persist film metadata only after verified draft upsert**

Extend `record_pending_draft` to store normalized `content_lane`, `film_titles` and `spoiler_level`. Extend `record_verified_publication` to copy the same fields into the numbered post. Require `content_lane` for new pending records. Keep `film_titles=[]` and `spoiler_level=""` for non-film lanes.

The read-only sync module needs no publishing change; its existing call will carry the new pending fields into history.

- [ ] **Step 6: Run CLI and ledger tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_newspic.py \
  tests/unit/test_wechat_mp_virtual_ledger.py -q
```

Expected: all tests pass and the static assertion still proves the sync module does not contain `freepublish_submit`.

- [ ] **Step 7: Commit Task 4**

```bash
git add \
  stock-ai/scripts/tools/wechat_mp_newspic_draft.py \
  stock-ai/scripts/tools/wechat_mp_virtual_ledger.py \
  stock-ai/tests/unit/test_wechat_mp_newspic.py \
  stock-ai/tests/unit/test_wechat_mp_virtual_ledger.py
git commit -m "feat: route Zhixia film drafts"
```

---

### Task 5: Skill Alignment and Full Verification

**Files:**
- Modify: `.cursor/skills/wechat-mp-virtual-lifestyle/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-virtual-lifestyle/references/persona.md`
- Modify: `.cursor/skills/wechat-mp-virtual-lifestyle/references/story-bible.md`
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-drafts/newspic-sop.md`

**Interfaces:**
- Documents: eight exact content lanes, two film columns, copy/image/spoiler ranges, source metadata and dry-run examples.
- Does not create or publish a production draft.

- [ ] **Step 1: Update operator documentation**

Replace the old 7:2:1 language with the exact 2/1/1/1/2/1/1/1 lane targets. Document:

- `下班前刷到一部`: 4–6 images, 180–320 characters, S0.
- `今晚翻一部旧电影` classic single: 5–7 images, 250–450 characters, S1 default.
- Classic list: 6–9 images, 300–600 characters, 3–5 films, S0.
- Film posts may use zero character images.
- Official and media film images require original-page metadata and forbid Zhixia watermark.
- Final copy contains no prompt, retrieval, scoring, generation-rule or internal-reasoning language.

- [ ] **Step 2: Add an exact evergreen dry-run example**

```bash
cd stock-ai
.venv/bin/python -m scripts.tools.wechat_mp_newspic_draft \
  --slot virtual_lifestyle \
  --topic-card output/zhixia-classic-film-card.json \
  --title "《一部旧电影》最难的不是告别" \
  --content output/zhixia-classic-film-copy.txt \
  --images assets/zhixia-film/01.jpg assets/zhixia-film/02.jpg assets/zhixia-film/03.jpg assets/zhixia-film/04.jpg assets/zhixia-film/05.jpg \
  --image-sources assets/zhixia-film/image-sources.json \
  --dry-run
```

- [ ] **Step 3: Scan docs and source for stale rules**

Run:

```bash
rg -n "7:2:1|7 条 A|下一条须为|影视.*必须.*栀夏|剧照.*栀夏水印" \
  .cursor/skills/wechat-mp-virtual-lifestyle \
  .cursor/skills/wechat-mp-drafts \
  stock-ai/scripts/tools/wechat_mp_virtual_*.py \
  stock-ai/scripts/tools/wechat_mp_newspic*.py
```

Expected: no stale active rules; historical design documents are outside the scan.

- [ ] **Step 4: Run the complete focused regression suite**

Run:

```bash
cd stock-ai
.venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_newspic.py \
  tests/unit/test_wechat_mp_virtual_editorial.py \
  tests/unit/test_wechat_mp_virtual_film.py \
  tests/unit/test_wechat_mp_virtual_ledger.py -q
.venv/bin/python -m py_compile \
  scripts/tools/wechat_mp_newspic.py \
  scripts/tools/wechat_mp_newspic_draft.py \
  scripts/tools/wechat_mp_virtual_editorial.py \
  scripts/tools/wechat_mp_virtual_film.py \
  scripts/tools/wechat_mp_virtual_ledger.py \
  scripts/tools/wechat_mp_virtual_lifestyle_sync.py
git diff --check
```

Expected: all tests pass, compilation succeeds and `git diff --check` prints nothing.

- [ ] **Step 5: Verify no publishing or secret-bearing files entered the diff**

Run:

```bash
rg -n "freepublish_submit" stock-ai/scripts/tools/wechat_mp_virtual_lifestyle_sync.py
git status --short
git diff --cached --name-only
```

Expected: the first command has no matches; `.env`, `data/wechat_mp_virtual_lifestyle_pending.json`, history JSON and runtime assets are absent from staged files.

- [ ] **Step 6: Commit Task 5**

```bash
git add \
  .cursor/skills/wechat-mp-virtual-lifestyle/SKILL.md \
  .cursor/skills/wechat-mp-virtual-lifestyle/references/persona.md \
  .cursor/skills/wechat-mp-virtual-lifestyle/references/story-bible.md \
  .cursor/skills/wechat-mp-drafts/SKILL.md \
  .cursor/skills/wechat-mp-drafts/newspic-sop.md
git commit -m "docs: add Zhixia film sharing workflow"
```
