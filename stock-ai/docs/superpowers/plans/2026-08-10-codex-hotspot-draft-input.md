# Codex Hotspot Draft Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--codex-draft` hotspot input that reads a validated local JSON artifact, skips Composer, and reuses the existing long-form cleanup, quality, figure, compliance, and WeChat draft pipeline.

**Architecture:** A focused loader module owns the JSON contract and produces an immutable `CodexHotspotDraft`. The article builder accepts that object as an optional alternate source and otherwise preserves the existing generated path. The CLI validates option combinations before building, then passes the object and its slot through the existing publish flow.

**Tech Stack:** Python 3.11, `argparse`, frozen `dataclass`, existing WeChat MP modules, pytest.

## Global Constraints

- User-visible output and public copy contain no emoji.
- `--codex-draft` only supports exactly one `hotspot` kind.
- Codex input never calls Composer, another LLM, or a template fallback.
- Codex input must pass existing hotspot body, figure, and public-compliance gates.
- Existing commands without `--codex-draft` retain current behavior.
- Do not commit `.env`, credentials, source-account data, or generated private article artifacts.

---

### Task 1: Codex JSON contract and loader

**Files:**
- Create: `scripts/tools/wechat_mp_codex_hotspot.py`
- Create: `tests/unit/test_wechat_mp_codex_hotspot.py`

**Interfaces:**
- Produces: `CodexHotspotDraft(title: str, digest: str, body: str, topic: str, research_urls: tuple[str, ...], slot_key: str)`.
- Produces: `load_codex_hotspot_draft(path: Path) -> CodexHotspotDraft`.
- Produces: `CodexHotspotDraft.as_discussion_topic() -> dict[str, object]`.

- [ ] **Step 1: Write failing loader tests**

```python
def test_load_codex_hotspot_draft_reads_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "draft.json"
    path.write_text(json.dumps({
        "title": "一件具体事件为什么引发争议？",
        "digest": "摘要",
        "body": "正文第一段。\n\n正文第二段。",
        "topic": "具体事件",
        "research_urls": ["https://example.com/report"],
        "slot_key": "hotspot_afternoon",
    }, ensure_ascii=False), encoding="utf-8")
    draft = load_codex_hotspot_draft(path)
    assert draft.topic == "具体事件"
    assert draft.research_urls == ("https://example.com/report",)

@pytest.mark.parametrize("field", ["title", "digest", "body", "topic"])
def test_load_codex_hotspot_draft_rejects_missing_required_field(tmp_path: Path, field: str) -> None:
    payload = {"title": "标题", "digest": "摘要", "body": "正文", "topic": "事件"}
    payload.pop(field)
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match=field):
        load_codex_hotspot_draft(path)
```

- [ ] **Step 2: Run loader tests and verify RED**

Run: `uv run pytest tests/unit/test_wechat_mp_codex_hotspot.py -q`

Expected: collection fails because `scripts.tools.wechat_mp_codex_hotspot` does not exist.

- [ ] **Step 3: Implement the minimal immutable loader**

```python
@dataclass(frozen=True)
class CodexHotspotDraft:
    title: str
    digest: str
    body: str
    topic: str
    research_urls: tuple[str, ...] = ()
    slot_key: str = ""

    def as_discussion_topic(self) -> dict[str, object]:
        slug = re.sub(r"[^\w\-]+", "-", self.topic[:28]).strip("-").lower() or "hotspot"
        return {
            "title_zh": self.topic,
            "trend_title": self.topic,
            "cover_slug": slug,
            "from_trend": True,
            "research_urls": list(self.research_urls),
        }

def load_codex_hotspot_draft(path: Path) -> CodexHotspotDraft:
    # Read UTF-8 JSON, require an object and four non-empty strings,
    # validate research_urls as strings and optional slot_key as a string.
```

- [ ] **Step 4: Run loader tests and verify GREEN**

Run: `uv run pytest tests/unit/test_wechat_mp_codex_hotspot.py -q`

Expected: all loader tests pass.

### Task 2: Build a hotspot article from Codex without Composer

**Files:**
- Modify: `scripts/tools/wechat_mp_hotspot_article.py`
- Modify: `scripts/tools/wechat_mp_content.py`
- Modify: `tests/unit/test_wechat_mp_codex_hotspot.py`

**Interfaces:**
- Produces: `validate_codex_hotspot_body(body: str, *, topic: str) -> str`, returning polished body or raising `ValueError` with existing reject reasons.
- Changes: `build_hotspot_article(*, edition: str | None = None, codex_draft: CodexHotspotDraft | None = None) -> dict[str, str]`.
- Changes: `build_article(..., codex_draft: CodexHotspotDraft | None = None) -> dict[str, str]`, forwarding it only for hotspot aliases.

- [ ] **Step 1: Write a failing builder test**

```python
def test_build_hotspot_article_uses_codex_body_without_generator(monkeypatch) -> None:
    draft = CodexHotspotDraft(
        title="具体事件为什么引发争议？",
        digest="摘要",
        body=_valid_hotspot_body(),
        topic="具体事件",
    )
    monkeypatch.setattr(hotspot_mod, "generate_hotspot_body", lambda **_: pytest.fail("generator called"))
    monkeypatch.setattr(content_mod, "hotspot_social_layout_enabled", lambda: False, raising=False)
    article = content_mod.build_hotspot_article(codex_draft=draft)
    assert article["title"] == draft.title
    assert draft.body.split("\n\n", 1)[0] in article["body_text"]
```

The fixture `_valid_hotspot_body()` contains at least 2,000 Chinese characters, at least five paragraphs, digits, and none of the existing banned phrases.

- [ ] **Step 2: Run the builder test and verify RED**

Run: `uv run pytest tests/unit/test_wechat_mp_codex_hotspot.py::test_build_hotspot_article_uses_codex_body_without_generator -q`

Expected: failure because `build_hotspot_article` does not accept `codex_draft`.

- [ ] **Step 3: Add a public Codex body validator and alternate builder branch**

```python
def validate_codex_hotspot_body(body: str, *, topic: str) -> str:
    polished = _polish_hotspot_llm_body(body)
    bucket = _theme_bucket(topic)
    reasons = _hotspot_body_reject_reasons(polished, bucket=bucket)
    if reasons:
        raise ValueError(f"Codex 热点正文未通过质量门禁：{'、'.join(reasons)}")
    return polished
```

In `build_hotspot_article`, use the Codex title, digest, topic object, and validated body when `codex_draft` is provided. Keep the existing generated branch byte-for-byte equivalent in behavior. Reuse the existing body-cache and social-figure block for both sources.

- [ ] **Step 4: Run focused builder tests and verify GREEN**

Run: `uv run pytest tests/unit/test_wechat_mp_codex_hotspot.py tests/unit/test_wechat_mp_hotspot_article.py tests/unit/test_wechat_mp_discussion_polish.py -q`

Expected: all focused tests pass.

### Task 3: Wire `--codex-draft` into the long-form CLI

**Files:**
- Modify: `scripts/tools/wechat_mp_draft.py`
- Modify: `tests/unit/test_wechat_mp_codex_hotspot.py`

**Interfaces:**
- Changes: `_build_for_kind(..., codex_draft: CodexHotspotDraft | None = None) -> dict[str, str]`.
- Produces: `_validate_codex_draft_kinds(kinds: list[str], path: Path | None) -> None`.

- [ ] **Step 1: Write failing CLI constraint tests**

```python
@pytest.mark.parametrize("kinds", [["news"], ["hotspot", "news"]])
def test_validate_codex_draft_kinds_requires_single_hotspot(kinds: list[str], tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="单篇 hotspot"):
        draft_cli._validate_codex_draft_kinds(kinds, tmp_path / "draft.json")

def test_build_for_kind_passes_codex_draft_to_hotspot(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(draft_cli, "build_article", lambda kind, **kwargs: captured.update(kind=kind, kwargs=kwargs) or {})
    codex = CodexHotspotDraft("标题", "摘要", "正文", "事件")
    draft_cli._build_for_kind("hotspot", edition="close", market_title=None, variant=None, codex_draft=codex)
    assert captured["kwargs"]["codex_draft"] is codex
```

- [ ] **Step 2: Run CLI tests and verify RED**

Run: `uv run pytest tests/unit/test_wechat_mp_codex_hotspot.py -q`

Expected: failure because the CLI helper and argument do not exist.

- [ ] **Step 3: Implement CLI loading and slot propagation**

Add `--codex-draft PATH`. Validate kind combinations immediately after `_resolve_kinds`. Load the JSON once. Pass it only to `hotspot` builds. For this invocation, resolve the slot as existing `WECHAT_MP_HOTSPOT_SLOT_KEY`, then JSON `slot_key`, then existing default; pass the resolved slot to the current upsert call without mutating persistent configuration.

- [ ] **Step 4: Run CLI tests and verify GREEN**

Run: `uv run pytest tests/unit/test_wechat_mp_codex_hotspot.py -q`

Expected: all Codex input and CLI tests pass.

### Task 4: Document and verify the full change

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-writing/hotspot-deep-review.md`
- Create: `tests/fixtures/wechat_mp_codex_hotspot_valid.json`

**Interfaces:**
- Documents the exact JSON contract and dry-run/publish commands.

- [ ] **Step 1: Add the Codex handoff commands to the routed documentation**

Document that `--codex-draft` skips Composer and that the source JSON remains a local ignored artifact. Include all required fields and the single-hotspot restriction.

- [ ] **Step 2: Run focused verification**

Run:

```bash
uv run pytest \
  tests/unit/test_wechat_mp_codex_hotspot.py \
  tests/unit/test_wechat_mp_hotspot_article.py \
  tests/unit/test_wechat_mp_discussion_polish.py \
  tests/unit/test_wechat_mp_newspic.py -q
```

Expected: zero failures.

- [ ] **Step 3: Verify command help and repository hygiene**

Run:

```bash
uv run python -m scripts.tools.wechat_mp_draft --help
git status --short
git diff --check
```

Expected: help includes `--codex-draft`; no `.env`, generated draft, credential, or unrelated file is staged or modified; `git diff --check` is clean.

- [ ] **Step 4: Commit implementation files**

```bash
git add \
  scripts/tools/wechat_mp_codex_hotspot.py \
  scripts/tools/wechat_mp_hotspot_article.py \
  scripts/tools/wechat_mp_content.py \
  scripts/tools/wechat_mp_draft.py \
  tests/unit/test_wechat_mp_codex_hotspot.py \
  .cursor/skills/wechat-mp-drafts/SKILL.md \
  .cursor/skills/wechat-mp-writing/hotspot-deep-review.md
git commit -m "feat: accept codex hotspot draft input"
```
