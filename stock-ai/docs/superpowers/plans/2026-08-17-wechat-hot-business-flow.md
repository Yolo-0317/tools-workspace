# WeChat Hot Business Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manually triggered `hot_business` WeChat article kind that selects a qualifying topic from the current daily hot lists, writes a source-traceable business explainer, and updates an independent draft slot without entering any scheduler or automatic batch.

**Architecture:** Add three focused units: a strict Codex draft contract, a daily-hot-topic scorer/selector, and a business-specific writer. Reuse the existing `hotspot` rendering, originality, figures, cover, compliance, and draft-upsert pipeline through a small `article_kind` generalization; register `hot_business` as a manual-only kind in the CLI and presentation maps.

**Tech Stack:** Python 3.11+, dataclasses, `urllib.parse`, existing WeChat MP LLM/research modules, pytest, existing `wechat_mp_draft` CLI.

## Global Constraints

- The user-facing kind is `hot_business`; its only draft slot is `hot_business`.
- Manual trigger only: do not add `hot_business` to Docker scheduler, launchd, `SCHEDULE_BATCHES`, or `DAILY_DRAFT_KINDS`.
- Default invocation selects from the current Weibo/Baidu-backed hotspot pool; `--topic` skips automatic selection but not research or quality gates.
- Automatic selection requires a total score of at least 70/100 with weights heat 40, business space 30, verifiability 20, ordinary-reader relevance 10.
- Each article requires at least three distinct source domains and at least one primary or authoritative source.
- Every accepted fact has an exact `source_url` present in `research_urls`; rejected claims cannot appear in title, digest, or body.
- Body length after whitespace removal is at least 1920 characters; `original_thesis` is at least 20 characters.
- Reuse current hotspot real-image-first, cover, originality, mobile-layout, compliance, and draft-upsert behavior.
- `--dry-run` must not upload images or call the WeChat draft API.
- Do not change existing `hotspot`, `tv_review`, `newspic`, finance kinds, or current scheduling behavior.
- Preserve all unrelated dirty-worktree changes; every commit stages only the exact files listed in its task.
- `wechat_mp_client.py` and `.cursor/skills/wechat-mp-drafts/SKILL.md` were already modified before this plan; inspect their baseline diffs and stage only newly added `hot_business` hunks with `git add -p`, then verify `git diff --cached` before committing.
- User-visible copy and reports contain no emoji.

---

## File Structure

**Create**

- `stock-ai/scripts/tools/wechat_mp_codex_hot_business.py` — immutable JSON contract, source-domain validation, fact-to-source mapping, rejected-claim gate, and originality adapter.
- `stock-ai/scripts/tools/wechat_mp_hot_business.py` — daily-hot candidate exclusions, four-axis assessment, batch LLM scoring, 70-point gate, and manual-topic resolution.
- `stock-ai/scripts/tools/wechat_mp_hot_business_article.py` — source bundle to structured article prompt, JSON parsing, business draft generation, and business-specific title/body checks.
- `stock-ai/tests/unit/test_wechat_mp_codex_hot_business.py` — contract and fact-boundary tests.
- `stock-ai/tests/unit/test_wechat_mp_hot_business.py` — scoring and topic-selection tests.
- `stock-ai/tests/unit/test_wechat_mp_hot_business_article.py` — writer and shared rendering tests.
- `stock-ai/tests/unit/test_wechat_mp_hot_business_cli.py` — CLI, slot, cover, and manual-only registration tests.

**Modify**

- `stock-ai/scripts/tools/wechat_mp_hotspot_article.py` — expose a public research attachment helper without changing existing hotspot behavior.
- `stock-ai/scripts/tools/wechat_mp_hotspot_body_cache.py` — add a `cache_kind` namespace so `hot_business` never overwrites `hotspot` cache.
- `stock-ai/scripts/tools/wechat_mp_content.py` — generalize `build_hotspot_article` presentation kind and dispatch `build_hot_business_article`.
- `stock-ai/scripts/tools/wechat_mp_draft.py` — parse `--topic`, load the correct Codex contract, run business gates, select the independent slot, and reuse the hotspot cover.
- `stock-ai/scripts/tools/wechat_mp_draft_slots.py` — classify and preserve the new managed draft slot.
- `stock-ai/scripts/tools/wechat_mp_client.py` — map `hot_business` to the existing hotspot/brand cover fallback.
- `stock-ai/scripts/tools/wechat_mp_masthead.py` — give `hot_business` the hotspot-style brand masthead and a business-specific slogan.
- `stock-ai/scripts/tools/wechat_mp_seo.py` — add digest, title, hashtag, and publish-reminder maps for `hot_business`.
- `stock-ai/scripts/tools/wechat_mp_monetization.py` — use hotspot-style traffic polish and follow hook for `hot_business`.
- `stock-ai/scripts/tools/wechat_mp_public.py` — use commentary disclaimer and hotspot reader-data cleanup for `hot_business`.
- `stock-ai/scripts/tools/wechat_mp_traffic_checklist.py` — apply the 2000-character longform checklist to `hot_business`.
- `.cursor/skills/wechat-mp-drafts/SKILL.md` — document the new manual command and slot.
- `.cursor/skills/wechat-mp-drafts/INDEX.md` — route “热点商业” to its manual workflow.

---

### Task 1: Strict Hot-Business Draft Contract

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_codex_hot_business.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_codex_hot_business.py`

**Interfaces:**
- Consumes: `CodexHotspotDraft`, `evaluate_hotspot_longform`, `require_originality`.
- Produces: `HotBusinessFact`, `CodexHotBusinessDraft`, `distinct_source_domain_count(urls)`, `load_codex_hot_business_draft_data(data)`, `load_codex_hot_business_draft(path)`, `validate_hot_business_draft(draft)`, `validate_codex_hot_business_originality(draft, history_posts=...)`.

- [ ] **Step 1: Write failing loader and boundary tests**

```python
@pytest.fixture
def valid_draft() -> CodexHotBusinessDraft:
    urls = (
        "https://brand.example/a",
        "https://media.example/b",
        "https://industry.example/c",
    )
    return CodexHotBusinessDraft(
        title="某品牌降价，成本由谁承担？",
        digest="从渠道和供应链解释这次降价。",
        body="正文" * 1000,
        topic="某品牌降价",
        research_urls=urls,
        original_thesis="这次降价更像渠道重分配，而不是一次简单让利行为。",
        business_question="降价成本由谁承担？",
        facts=(HotBusinessFact("官方宣布降价", urls[0]),),
        inferences=("渠道可能承担一部分成本",),
        rejected_claims=("销量已是全国第一",),
    )


def test_load_hot_business_draft_requires_traceable_facts(tmp_path: Path) -> None:
    source = tmp_path / "draft.json"
    source.write_text(json.dumps({
        "title": "某品牌降价，成本由谁承担？",
        "digest": "从渠道和供应链解释这次降价。",
        "body": "正文" * 1000,
        "topic": "某品牌降价",
        "research_urls": [
            "https://brand.example/a",
            "https://media.example/b",
            "https://industry.example/c",
        ],
        "original_thesis": "这次降价更像渠道重分配，而不是简单让利。",
        "business_question": "降价成本由谁承担？",
        "facts": [{"claim": "官方宣布降价", "source_url": "https://brand.example/a"}],
        "inferences": ["渠道可能承担一部分成本"],
        "rejected_claims": ["销量已是全国第一"],
        "slot_key": "hot_business",
    }), encoding="utf-8")

    draft = load_codex_hot_business_draft(source)
    assert draft.facts[0].claim == "官方宣布降价"
    assert draft.facts[0].source_url == "https://brand.example/a"


def test_rejects_fact_url_outside_research_urls(valid_draft: CodexHotBusinessDraft) -> None:
    broken = replace(
        valid_draft,
        facts=(HotBusinessFact("未经映射的数字", "https://other.example/x"),),
    )
    with pytest.raises(ValueError, match="facts.*research_urls"):
        validate_hot_business_draft(broken)


def test_rejects_rejected_claim_reintroduced_into_body(valid_draft: CodexHotBusinessDraft) -> None:
    broken = replace(valid_draft, body=valid_draft.body + "销量已是全国第一")
    with pytest.raises(ValueError, match="rejected_claims"):
        validate_hot_business_draft(broken)
```

- [ ] **Step 2: Run the new tests and confirm RED**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_codex_hot_business.py -q
```

Expected: collection fails because `scripts.tools.wechat_mp_codex_hot_business` does not exist.

- [ ] **Step 3: Implement the immutable contract and validators**

```python
@dataclass(frozen=True)
class HotBusinessFact:
    claim: str
    source_url: str


@dataclass(frozen=True)
class CodexHotBusinessDraft:
    title: str
    digest: str
    body: str
    topic: str
    research_urls: tuple[str, ...]
    original_thesis: str
    business_question: str
    facts: tuple[HotBusinessFact, ...]
    inferences: tuple[str, ...]
    rejected_claims: tuple[str, ...]
    slot_key: str = "hot_business"

    def as_hotspot_draft(self) -> CodexHotspotDraft:
        return CodexHotspotDraft(
            title=self.title,
            digest=self.digest,
            body=self.body,
            topic=self.topic,
            research_urls=self.research_urls,
            slot_key="hot_business",
            original_thesis=self.original_thesis,
        )
```

Validation must:

- require all scalar strings to be non-empty;
- require `slot_key` to equal `hot_business`;
- require at least three distinct `http`/`https` source domains;
- require at least one fact;
- require each fact URL to exactly match an entry in `research_urls`;
- reject any non-empty rejected claim found after whitespace normalization in title, digest, or body;
- require `original_thesis` length of at least 20 characters;
- delegate originality to the existing hotspot evaluator.

`load_codex_hot_business_draft(path)` reads JSON and delegates all field parsing to `load_codex_hot_business_draft_data(data)`, so the automatic writer can validate an in-memory LLM response through the identical contract.

- [ ] **Step 4: Run contract tests and existing Codex hotspot tests**

Run:

```bash
cd stock-ai
uv run pytest \
  tests/unit/test_wechat_mp_codex_hot_business.py \
  tests/unit/test_wechat_mp_codex_hotspot.py -q
```

Expected: all tests pass; ordinary hotspot JSON remains unchanged.

- [ ] **Step 5: Commit only Task 1 files**

```bash
git add -- \
  stock-ai/scripts/tools/wechat_mp_codex_hot_business.py \
  stock-ai/tests/unit/test_wechat_mp_codex_hot_business.py
git commit -m "feat: validate hot business draft sources"
```

---

### Task 2: Daily-Hot Business Scoring and Selection

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_hot_business.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_hot_business.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_article.py:760-810`

**Interfaces:**
- Consumes: `HotspotTopic`, `pick_hotspot_candidates(items=None)`, `call_wechat_mp_llm`, existing discussion research.
- Produces: `HotBusinessAssessment`, `assess_hot_business_candidates(candidates)`, `pick_hot_business_topic(items=None, topic_hint="")`.

- [ ] **Step 1: Write failing scoring, exclusion, threshold, and manual-topic tests**

```python
def raw_item(title: str) -> dict[str, object]:
    return {"title": title, "summary": title, "attention_score": 800.0}


def topic(title: str) -> HotspotTopic:
    return HotspotTopic(
        item=raw_item(title), bucket="other", score=800.0, section_title=title
    )


def assessment(
    index: int, *, heat: int, business: int, verifiability: int, relevance: int
) -> HotBusinessAssessment:
    return HotBusinessAssessment(
        index=index,
        heat=heat,
        business_space=business,
        verifiability=verifiability,
        reader_relevance=relevance,
        reason="测试评分",
    )


def with_three_domains(item: dict[str, object]) -> dict[str, object]:
    out = dict(item)
    out["web_research"] = [
        {"url": "https://brand.example/a", "title": "官方"},
        {"url": "https://media.example/b", "title": "媒体"},
        {"url": "https://industry.example/c", "title": "行业"},
    ]
    return out


def fail_if_called(*args: object, **kwargs: object) -> None:
    raise AssertionError("manual topic must not call automatic scoring")


def test_pick_hot_business_topic_uses_highest_qualified_score(monkeypatch) -> None:
    candidates = [topic("品牌涨价"), topic("明星恋情")]
    monkeypatch.setattr(mod, "pick_hotspot_candidates", lambda _items=None: candidates)
    monkeypatch.setattr(mod, "attach_hotspot_research", with_three_domains)
    monkeypatch.setattr(mod, "_request_assessments", lambda rows: [
        assessment(0, heat=35, business=28, verifiability=20, relevance=9),
        assessment(1, heat=40, business=4, verifiability=10, relevance=4),
    ])

    picked = pick_hot_business_topic()
    assert picked.topic.item["title"] == "品牌涨价"
    assert picked.assessment.total == 92


def test_no_candidate_at_70_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(mod, "_request_assessments", lambda rows: [
        assessment(0, heat=30, business=10, verifiability=10, relevance=5),
    ])
    with pytest.raises(RuntimeError, match="没有达到 70 分"):
        pick_hot_business_topic(items=[raw_item("普通八卦")])


def test_manual_topic_skips_scoring_but_keeps_research_gate(monkeypatch) -> None:
    monkeypatch.setattr(mod, "_request_assessments", fail_if_called)
    monkeypatch.setattr(mod, "attach_hotspot_research", with_three_domains)
    picked = pick_hot_business_topic(topic_hint="某平台会员涨价")
    assert picked.topic.item["title"] == "某平台会员涨价"
    assert len(picked.research_urls) >= 3
```

- [ ] **Step 2: Run selection tests and confirm RED**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_hot_business.py -q
```

Expected: import failure for the missing selector module.

- [ ] **Step 3: Expose research attachment without changing hotspot callers**

In `wechat_mp_hotspot_article.py`, rename `_attach_hotspot_research` to `attach_hotspot_research`, update `generate_hotspot_body` to call the public name, and keep this compatibility alias for existing imports:

```python
_attach_hotspot_research = attach_hotspot_research
```

- [ ] **Step 4: Implement typed assessment and batch LLM scoring**

```python
@dataclass(frozen=True)
class HotBusinessAssessment:
    index: int
    heat: int
    business_space: int
    verifiability: int
    reader_relevance: int
    reason: str

    @property
    def total(self) -> int:
        return self.heat + self.business_space + self.verifiability + self.reader_relevance


@dataclass(frozen=True)
class SelectedHotBusinessTopic:
    topic: HotspotTopic
    assessment: HotBusinessAssessment | None
    research_urls: tuple[str, ...]
```

`assess_hot_business_candidates` sends one JSON-only LLM request for at most five researched candidates. Clamp each axis to its exact maximum, reject indices outside the batch, and set `verifiability=0` when fewer than three distinct source domains were attached. Apply deterministic hard exclusions before the LLM for disaster casualties, unresolved criminal allegations, and gossip with no brand/platform/product entity.

`pick_hot_business_topic` must:

1. build the existing hotspot candidate pool;
2. keep at most five non-excluded candidates;
3. attach research to each candidate;
4. select the highest total at or above 70;
5. on `topic_hint`, construct or match one manual topic, attach research, require three domains, and skip the score threshold;
6. include scored candidates and rejection reasons in the raised error when none qualify.

- [ ] **Step 5: Run selector and hotspot regression tests**

Run:

```bash
cd stock-ai
uv run pytest \
  tests/unit/test_wechat_mp_hot_business.py \
  tests/unit/test_wechat_mp_hotspot_article.py -q
```

Expected: all tests pass; existing hotspot ranking and generation tests remain green.

- [ ] **Step 6: Commit only Task 2 files**

```bash
git add -- \
  stock-ai/scripts/tools/wechat_mp_hot_business.py \
  stock-ai/scripts/tools/wechat_mp_hotspot_article.py \
  stock-ai/tests/unit/test_wechat_mp_hot_business.py
git commit -m "feat: select business topics from daily trends"
```

---

### Task 3: Structured Business Writer and Shared Longform Rendering

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_hot_business_article.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_hot_business_article.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_hotspot_body_cache.py:15-100`
- Modify: `stock-ai/scripts/tools/wechat_mp_content.py:887-990,1355-1375`

**Interfaces:**
- Consumes: `SelectedHotBusinessTopic`, `CodexHotBusinessDraft`, `build_hotspot_article` shared rendering path.
- Produces: `generate_hot_business_draft(topic_hint="")`, `build_hot_business_article(topic_hint="", codex_draft=None)`.

- [ ] **Step 1: Write failing writer, cache-isolation, and shared-render tests**

```python
def valid_payload() -> dict[str, object]:
    urls = [
        "https://brand.example/a",
        "https://media.example/b",
        "https://industry.example/c",
    ]
    return {
        "title": "某品牌涨价，成本由谁承担？",
        "digest": "从渠道和成本解释这次涨价。",
        "body": "正文" * 1000,
        "topic": "某品牌涨价",
        "research_urls": urls,
        "original_thesis": "这次涨价的关键不是标价变化，而是渠道成本重新分配。",
        "business_question": "这次涨价的成本由谁承担？",
        "facts": [{"claim": "品牌公告调整价格", "source_url": urls[0]}],
        "inferences": ["渠道利润可能重新分配"],
        "rejected_claims": [],
        "slot_key": "hot_business",
    }


def valid_draft() -> CodexHotBusinessDraft:
    return load_codex_hot_business_draft_data(valid_payload())


def selected_topic() -> SelectedHotBusinessTopic:
    urls = tuple(valid_payload()["research_urls"])
    item = {
        "title": "某品牌涨价",
        "web_research": [{"url": url, "title": url} for url in urls],
    }
    return SelectedHotBusinessTopic(
        topic=HotspotTopic(item=item, bucket="other", score=800.0, section_title="某品牌涨价"),
        assessment=HotBusinessAssessment(0, 35, 28, 20, 9, "商业问题明确"),
        research_urls=urls,
    )


def topic_dict() -> dict[str, object]:
    return {"title_zh": "某品牌涨价", "cover_slug": "brand-price"}


def test_generate_hot_business_draft_returns_validated_json(monkeypatch) -> None:
    monkeypatch.setattr(article_mod, "pick_hot_business_topic", lambda **_: selected_topic())
    monkeypatch.setattr(article_mod, "call_wechat_mp_llm", lambda *_, **__: json.dumps(valid_payload()))
    draft = article_mod.generate_hot_business_draft()
    assert draft.slot_key == "hot_business"
    assert draft.business_question == "这次涨价的成本由谁承担？"


def test_hot_business_cache_does_not_write_hotspot_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cache_mod, "HOTSPOT_CACHE_DIR", tmp_path / "hotspot")
    monkeypatch.setattr(cache_mod, "HOT_BUSINESS_CACHE_DIR", tmp_path / "hot-business")
    cache_mod.save_hotspot_body_cache(
        topic_dict(), body_core="正文", title="标题", digest="摘要",
        slot_key="hot_business", cache_kind="hot_business",
    )
    assert list((tmp_path / "hot-business").glob("*.json"))
    assert not (tmp_path / "hotspot").exists()


def test_build_hot_business_article_uses_hot_business_kind(monkeypatch) -> None:
    monkeypatch.setattr(article_mod, "generate_hot_business_draft", lambda **_: valid_draft())
    article = article_mod.build_hot_business_article()
    assert article["slot_key"] == "hot_business"
    assert article["hot_business_report"]["source_domains"] == 3
```

- [ ] **Step 2: Run article tests and confirm RED**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_hot_business_article.py -q
```

Expected: import failure for the missing writer module.

- [ ] **Step 3: Implement the JSON-only business writer**

`generate_hot_business_draft` must build one prompt containing:

- the selected trend title and assessment reason;
- the complete researched source snippets and allowed URLs;
- the seven-part article structure from the design;
- explicit separation of facts, inferences, and rejected claims;
- the exact `CodexHotBusinessDraft` JSON schema;
- bans on unsupported rankings, stable-performance claims, internal-company intent, investment advice, emoji, Markdown headings, and visible editorial metadata.

Parse a single JSON object, convert it through `load_codex_hot_business_draft_data(data)` (a dictionary entry point added beside the file loader in Task 1), and fail closed on malformed JSON. Do not fall back to a template or ordinary hotspot article.

- [ ] **Step 4: Namespace the existing hotspot cache**

Add:

```python
HOTSPOT_CACHE_DIR = ROOT / "data" / "wechat_mp_hotspot_body_cache"
HOT_BUSINESS_CACHE_DIR = ROOT / "data" / "wechat_mp_hot_business_body_cache"


def cache_dir_for_kind(cache_kind: str) -> Path:
    if cache_kind == "hot_business":
        return HOT_BUSINESS_CACHE_DIR
    if cache_kind == "hotspot":
        return HOTSPOT_CACHE_DIR
    raise ValueError(f"未知热点缓存 kind: {cache_kind}")
```

Add `cache_kind: str = "hotspot"` to save/load helpers. Only `hotspot` writes or reads `LEGACY_CACHE_PATH`; `hot_business` uses its dedicated directory exclusively.

- [ ] **Step 5: Generalize hotspot rendering without duplicating it**

Change the shared builder signature to:

```python
def build_hotspot_article(
    *,
    edition: str | None = None,
    codex_draft: CodexHotspotDraft | None = None,
    article_kind: str = "hotspot",
    upload_figures: bool = True,
) -> dict[str, Any]:
```

Permit only `hotspot` and `hot_business`. Use `article_kind` for cache namespace, `_article_shell`, and `attach_publish_hints`, while continuing to reuse `validate_codex_hotspot_body`, hotspot polish, discussion figures, and cover generation. Forward `upload_figures` into `_article_shell`; local research and image preparation may run during dry-run, but material upload must remain disabled.

Implement:

```python
def build_hot_business_article(
    *,
    topic_hint: str = "",
    codex_draft: CodexHotBusinessDraft | None = None,
    upload_figures: bool = True,
) -> dict[str, Any]:
    draft = codex_draft or generate_hot_business_draft(topic_hint=topic_hint)
    validate_hot_business_draft(draft)
    article = build_hotspot_article(
        codex_draft=draft.as_hotspot_draft(),
        article_kind="hot_business",
        upload_figures=upload_figures,
    )
    article["slot_key"] = "hot_business"
    article["hot_business_report"] = {
        "business_question": draft.business_question,
        "source_domains": distinct_source_domain_count(draft.research_urls),
        "fact_count": len(draft.facts),
        "inference_count": len(draft.inferences),
    }
    return article
```

Dispatch `kind == "hot_business"` from `build_article` without adding it to `DAILY_DRAFT_KINDS`.

- [ ] **Step 6: Run writer, cache, content, and existing hotspot tests**

Run:

```bash
cd stock-ai
uv run pytest \
  tests/unit/test_wechat_mp_hot_business_article.py \
  tests/unit/test_wechat_mp_codex_hot_business.py \
  tests/unit/test_wechat_mp_codex_hotspot.py \
  tests/unit/test_wechat_mp_disclaimer_render.py -q
```

Expected: all tests pass; cache paths and ordinary hotspot output remain isolated.

- [ ] **Step 7: Commit only Task 3 files**

```bash
git add -- \
  stock-ai/scripts/tools/wechat_mp_hot_business_article.py \
  stock-ai/scripts/tools/wechat_mp_hotspot_body_cache.py \
  stock-ai/scripts/tools/wechat_mp_content.py \
  stock-ai/tests/unit/test_wechat_mp_hot_business_article.py
git commit -m "feat: build hot business longform articles"
```

---

### Task 4: Manual CLI, Independent Slot, and Presentation Registration

**Files:**
- Create: `stock-ai/tests/unit/test_wechat_mp_hot_business_cli.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_draft.py:45-400`
- Modify: `stock-ai/scripts/tools/wechat_mp_draft_slots.py:32-175`
- Modify: `stock-ai/scripts/tools/wechat_mp_client.py:1048-1090,1366-1410`
- Modify: `stock-ai/scripts/tools/wechat_mp_masthead.py:35-55,239-270`
- Modify: `stock-ai/scripts/tools/wechat_mp_seo.py:20-145,500-565`
- Modify: `stock-ai/scripts/tools/wechat_mp_monetization.py:35-180,437-470`
- Modify: `stock-ai/scripts/tools/wechat_mp_public.py:317-510`
- Modify: `stock-ai/scripts/tools/wechat_mp_traffic_checklist.py:175-330`

**Interfaces:**
- Consumes: `build_article(kind="hot_business", topic_hint=..., codex_draft=...)`, `load_codex_hot_business_draft`.
- Produces: `wechat_mp_draft --kind hot_business [--topic TEXT] [--codex-draft PATH] [--dry-run]` and managed slot `hot_business`.

- [ ] **Step 1: Write failing CLI and registration tests**

```python
def valid_business_draft() -> CodexHotBusinessDraft:
    return load_codex_hot_business_draft_data({
        "title": "某品牌涨价，成本由谁承担？",
        "digest": "从渠道和成本解释这次涨价。",
        "body": "正文" * 1000,
        "topic": "某品牌涨价",
        "research_urls": [
            "https://brand.example/a",
            "https://media.example/b",
            "https://industry.example/c",
        ],
        "original_thesis": "这次涨价的关键不是标价变化，而是渠道成本重新分配。",
        "business_question": "这次涨价的成本由谁承担？",
        "facts": [{"claim": "品牌公告调整价格", "source_url": "https://brand.example/a"}],
        "inferences": ["渠道利润可能重新分配"],
        "rejected_claims": [],
        "slot_key": "hot_business",
    })


def test_hot_business_is_manual_only() -> None:
    assert "hot_business" in content_mod.DRAFT_KINDS
    assert "hot_business" not in content_mod.DAILY_DRAFT_KINDS
    assert all(
        "hot_business" not in tuple(config.get("kinds") or ())
        for config in batch_mod.SCHEDULE_BATCHES.values()
    )


def test_topic_flag_only_accepts_single_hot_business() -> None:
    draft_cli._validate_topic_kinds(["hot_business"], "品牌涨价")
    with pytest.raises(ValueError, match="--topic"):
        draft_cli._validate_topic_kinds(["hotspot"], "品牌涨价")


def test_hot_business_uses_independent_slot(monkeypatch) -> None:
    draft = valid_business_draft()
    assert draft_cli._resolve_draft_slot_key("hot_business", draft) == "hot_business"


def test_hot_business_dry_run_disables_figure_upload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_build_article(kind: str, **kwargs: object) -> dict[str, str]:
        captured.update(kwargs)
        return {"title": "标题", "digest": "摘要", "body_text": "正文", "content": "正文"}

    monkeypatch.setattr(draft_cli, "build_article", fake_build_article)
    draft_cli._build_for_kind(
        "hot_business",
        edition=None,
        market_title=None,
        variant=None,
        topic_hint="品牌涨价",
        codex_draft=None,
        upload_figures=False,
    )
    assert captured["upload_figures"] is False


def test_hot_business_cover_reuses_discussion_cover(monkeypatch) -> None:
    topic = {"title_zh": "品牌涨价", "cover_slug": "brand-price"}
    monkeypatch.setattr(hotspot_mod, "get_last_built_hotspot_topic", lambda: topic)
    monkeypatch.setattr(cover_mod, "pick_discussion_draft_thumb", lambda _: ("thumb", None))
    cover_kind, thumb, error = draft_cli._pick_cover_for_kind(
        kind="hot_business", cover_kind="hotspot"
    )
    assert (cover_kind, thumb, error) == ("discussion", "thumb", None)
```

- [ ] **Step 2: Run CLI tests and confirm RED**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_hot_business_cli.py -q
```

Expected: failures because the kind, argument, and presentation maps are absent.

- [ ] **Step 3: Add manual-only CLI routing**

Add `--topic` to `wechat_mp_draft.py` and validate it only with `kinds == ["hot_business"]`. Allow `--codex-draft` with exactly one of `hotspot` or `hot_business`, selecting the matching loader. Extend `_build_for_kind` and `build_article` with `topic_hint`, `upload_figures`, and the correct typed draft. The dry-run loop must pass `upload_figures=False`; the formal draft loop passes `True`.

For `hot_business`:

- ignore `--edition`;
- run `validate_codex_hot_business_originality` for supplied or generated structured drafts;
- use `slot_key="hot_business"` unconditionally;
- treat the cover as hotspot/discussion cover;
- print score/source/fact reports during `--dry-run` without exposing rejected claims in article content.

- [ ] **Step 4: Register slot, cover, masthead, SEO, and quality aliases**

Make the following exact behavioral mappings:

```python
HOT_BUSINESS_PRESENTATION_KIND = "hotspot"
HOT_BUSINESS_SLOT_KEY = "hot_business"
```

- `wechat_mp_draft_slots._KIND_TITLE_HINTS["hot_business"]`: `("背后的生意", "成本由谁承担", "真正想卖", "热点商业")`.
- `wechat_mp_client`: same primary/fallback cover as `hotspot`.
- `wechat_mp_masthead.KIND_SLOGANS["hot_business"]`: `"热点背后的生意，先把账算清楚"`; use the same brand banner branch as `hotspot`.
- `wechat_mp_seo`: digest core `("热点商业", "商业观察")`, phrase `"从热点看公司、生意与利益关系"`, title keywords `("品牌", "公司", "生意", "成本", "渠道", "商业")`, hashtags `("热点商业", "商业观察", "品牌故事")`, and the hotspot manual publish steps.
- `wechat_mp_monetization`: same follow hook and traffic-polish family as `hotspot`, with business vocabulary `("品牌", "公司", "产品", "成本", "渠道", "竞争")`.
- `wechat_mp_public`: commentary disclaimer and hotspot-style reader-data cleanup.
- `wechat_mp_content.render_article_content_html`: run `reflow_hotspot_body` for both `hotspot` and `hot_business`.
- `wechat_mp_traffic_checklist`: same longform minimum and discussion checks as `hotspot`.

- [ ] **Step 5: Run focused CLI and presentation regressions**

Run:

```bash
cd stock-ai
uv run pytest \
  tests/unit/test_wechat_mp_hot_business_cli.py \
  tests/unit/test_wechat_mp_thumb_kind.py \
  tests/unit/test_wechat_mp_monetization.py \
  tests/unit/test_wechat_mp_sousou_eval.py \
  tests/unit/test_wechat_mp_disclaimer_render.py -q
```

Expected: all tests pass and `hot_business` remains absent from automatic batches.

- [ ] **Step 6: Commit only Task 4 files**

```bash
git add -- \
  stock-ai/scripts/tools/wechat_mp_draft.py \
  stock-ai/scripts/tools/wechat_mp_draft_slots.py \
  stock-ai/scripts/tools/wechat_mp_masthead.py \
  stock-ai/scripts/tools/wechat_mp_seo.py \
  stock-ai/scripts/tools/wechat_mp_monetization.py \
  stock-ai/scripts/tools/wechat_mp_public.py \
  stock-ai/scripts/tools/wechat_mp_traffic_checklist.py \
  stock-ai/tests/unit/test_wechat_mp_hot_business_cli.py
git add -p -- stock-ai/scripts/tools/wechat_mp_client.py
git diff --cached -- stock-ai/scripts/tools/wechat_mp_client.py
git commit -m "feat: expose manual hot business draft flow"
```

---

### Task 5: Documentation and End-to-End Verification

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-drafts/INDEX.md`
- Modify: `stock-ai/tests/unit/test_wechat_mp_hot_business_cli.py`

**Interfaces:**
- Consumes: the completed `hot_business` CLI.
- Produces: operator-facing command documentation and final verification evidence.

- [ ] **Step 1: Add a command-level acceptance test**

Use an isolated environment and monkeypatch external research, LLM, image, and WeChat calls. Assert that:

```python
result = draft_cli.main()
assert result == 0
assert output.count("=== hot_business ===") == 1
assert "候选评分" in output
assert "来源域" in output
assert wechat_draft_calls == []
assert image_upload_calls == []
```

The test invocation must model:

```text
wechat_mp_draft --kind hot_business --topic 某平台会员涨价 --dry-run
```

- [ ] **Step 2: Run the acceptance test and confirm it fails before documentation changes**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_hot_business_cli.py -q
```

Expected: the new acceptance test fails until the final dry-run report wiring is complete.

- [ ] **Step 3: Complete the dry-run report and update operator docs**

Document both commands:

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_draft --kind hot_business --dry-run
uv run python -m scripts.tools.wechat_mp_draft --kind hot_business --topic "具体热点" --dry-run
```

State explicitly that the flow is manual-only, writes only the `hot_business` slot after `--dry-run` is removed, and fails closed when no candidate reaches 70 or research has fewer than three domains. Add “热点商业” to the INDEX routing tree without changing the normal `hotspot` route.

- [ ] **Step 4: Run the full focused WeChat test set**

Run:

```bash
cd stock-ai
uv run pytest tests/unit/test_wechat_mp_*.py -q
```

Expected: zero failures.

- [ ] **Step 5: Run a real manual dry-run without publishing**

Run:

```bash
cd stock-ai
uv run python -m scripts.tools.wechat_mp_draft --kind hot_business --dry-run
```

Expected: either a complete article preview with score/source/fact report, or a clear fail-closed message listing why no current candidate reached 70. It must not create or update a WeChat draft.

- [ ] **Step 6: Verify no scheduler or batch gained the new kind**

Run:

```bash
cd stock-ai
rg -n "hot_business" \
  docker/scheduler \
  scripts/wechat_mp_*scheduled.sh \
  scripts/tools/wechat_mp_draft_batch.py
```

Expected: no scheduler/scheduled-script match; any match in `wechat_mp_draft_batch.py` is limited to a testable exclusion or comment, never a batch `kinds` entry.

- [ ] **Step 7: Review only task-owned changes**

Run:

```bash
git diff --check
git status --short
git diff -- \
  stock-ai/scripts/tools/wechat_mp_codex_hot_business.py \
  stock-ai/scripts/tools/wechat_mp_hot_business.py \
  stock-ai/scripts/tools/wechat_mp_hot_business_article.py \
  stock-ai/scripts/tools/wechat_mp_hotspot_article.py \
  stock-ai/scripts/tools/wechat_mp_hotspot_body_cache.py \
  stock-ai/scripts/tools/wechat_mp_content.py \
  stock-ai/scripts/tools/wechat_mp_draft.py \
  stock-ai/scripts/tools/wechat_mp_draft_slots.py \
  stock-ai/scripts/tools/wechat_mp_client.py \
  stock-ai/scripts/tools/wechat_mp_masthead.py \
  stock-ai/scripts/tools/wechat_mp_seo.py \
  stock-ai/scripts/tools/wechat_mp_monetization.py \
  stock-ai/scripts/tools/wechat_mp_public.py \
  stock-ai/scripts/tools/wechat_mp_traffic_checklist.py \
  stock-ai/tests/unit/test_wechat_mp_hot_business*.py \
  .cursor/skills/wechat-mp-drafts/SKILL.md \
  .cursor/skills/wechat-mp-drafts/INDEX.md
```

Expected: no whitespace errors; unrelated pre-existing changes remain unstaged and untouched.

- [ ] **Step 8: Commit only documentation and final acceptance wiring**

```bash
git add -- \
  .cursor/skills/wechat-mp-drafts/INDEX.md \
  stock-ai/tests/unit/test_wechat_mp_hot_business_cli.py
git add -p -- .cursor/skills/wechat-mp-drafts/SKILL.md
git diff --cached -- .cursor/skills/wechat-mp-drafts/SKILL.md
git commit -m "docs: document manual hot business workflow"
```
