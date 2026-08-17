# Single-Drama Promotion Draft Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual-only `short_drama_feature` WeChat draft kind that selects one revenue-ranked drama, verifies its plot against public sources, writes a 1,200–1,800-character suspense-led recommendation, and inserts exactly that drama's attributed component.

**Architecture:** Keep commercial ranking and component identity in `wechat_mp_short_drama.py`; add a focused research module that produces a source-bound fact ledger and a focused article module that produces and audits the recommendation copy. Route the new kind through the existing content/draft/slot pipeline, but bypass automatic post-hoc drama selection by attaching the already researched drama explicitly.

**Tech Stack:** Python 3, dataclasses, existing DeepSeek/Cursor LLM client, existing public-news research helpers, WeChat draft API, pytest.

## Global Constraints

- The public kind and slot key are exactly `short_drama_feature`.
- The kind is manual-only and must not appear in `DAILY_DRAFT_KINDS` or scheduled batches.
- One article promotes exactly one drama and contains exactly one `data-adtype="short-play"` component.
- Candidate ordering is 50% commission, 30% log-normalized heat, 20% appeal, with existing seven-day usage penalties.
- Research tries at most the commercial top three; no eligible researched candidate means no draft.
- Every accepted drama has at least two corroborating sources, including one official platform/producer source.
- Every plot fact allowed into public copy cites at least two allowed sources; character, relationship, conflict, and reversal fact types must all be present.
- Body length is 1,200–1,800 non-whitespace Chinese characters.
- Dry-run performs no material upload, draft write, slot update, or usage write.
- Do not print cookies, access tokens, attribution tickets, or private component paths.
- Do not add dependencies, automatic publishing, timers, multi-drama roundups, or ordinary CPS fallback.
- Existing working-tree changes are user-owned. Before every commit, inspect `git diff --cached --name-only`; do not include unrelated hunks or files.

---

## File Structure

- Create `scripts/tools/wechat_mp_short_drama_research.py`: source collection, source classification, LLM fact extraction, and deterministic fact-ledger validation.
- Create `scripts/tools/wechat_mp_short_drama_feature_article.py`: candidate fallback orchestration, copy generation, unsupported-claim audit, rendering, and diagnostic report.
- Modify `scripts/tools/wechat_mp_short_drama.py`: expose ranked top-three candidates and attach one explicitly selected drama without re-selection.
- Modify `scripts/tools/wechat_mp_content.py`: register/build the new kind and allow callers to render an article shell without automatic promotion attachment.
- Modify `scripts/tools/wechat_mp_draft.py`: manual CLI routing, dry-run diagnostics, cover choice, independent slot, and existing post-save verification.
- Modify `scripts/tools/wechat_mp_draft_slots.py`: managed-title hints for the independent slot.
- Modify `scripts/tools/wechat_mp_seo.py`, `scripts/tools/wechat_mp_monetization.py`, and `scripts/tools/wechat_mp_traffic_checklist.py`: explicit copy/SEO/engagement mappings for the new kind.
- Create `tests/unit/test_wechat_mp_short_drama_research.py` and `tests/unit/test_wechat_mp_short_drama_feature_article.py`.
- Modify `tests/unit/test_wechat_mp_short_drama.py` and create `tests/unit/test_wechat_mp_short_drama_feature_cli.py` for component and routing regression coverage.
- Modify `.cursor/skills/wechat-mp-drafts/SKILL.md`, `.cursor/skills/wechat-mp-drafts/INDEX.md`, and `.cursor/skills/wechat-mp-drafts/reference.md` only after implementation behavior is stable.

### Task 1: Ranked Candidates and Exact-Drama Attachment

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_short_drama.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_short_drama.py`

**Interfaces:**
- Produces: `score_short_drama_feature(drama, *, population, usage_count=0) -> DramaScore`
- Produces: `rank_short_drama_candidates(rows, *, usage_path=USAGE_PATH, now=None, limit=3, exclude_previously_used=False) -> list[tuple[ShortDrama, DramaScore]]`
- Produces: `attach_selected_short_drama(article, *, kind, drama, score, attribution) -> dict[str, Any]`
- Preserves: the existing `pick_short_drama` return type `tuple[ShortDrama, DramaScore]` and behavior for every current kind.

- [ ] **Step 1: Write failing ranking tests**

Add tests proving the helper returns no more than three commercially ranked dramas, applies the existing usage penalty, and excludes any previously used drama when `exclude_previously_used=True`.

```python
def test_rank_feature_candidates_returns_unused_commercial_top_three(tmp_path: Path) -> None:
    rows = [
        drama(drama_id="1", drama_name="高佣逆袭", rate_bp=8000, hot_degree=9000),
        drama(drama_id="2", drama_name="豪门反击", rate_bp=7000, hot_degree=8000),
        drama(drama_id="3", drama_name="职场翻身", rate_bp=6000, hot_degree=7000),
        drama(drama_id="4", drama_name="普通爱情", rate_bp=1000, hot_degree=1000),
    ]
    tmp_path.joinpath("usage.json").write_text(
        json.dumps([{"drama_id": "1", "used_at": NOW.isoformat()}]),
        encoding="utf-8",
    )
    ranked = short_drama.rank_short_drama_candidates(
        rows,
        usage_path=tmp_path / "usage.json",
        now=NOW,
        limit=3,
        exclude_previously_used=True,
    )
    assert [item.drama_id for item, _ in ranked] == ["2", "3", "4"]
```

- [ ] **Step 2: Run the tests and confirm RED**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_short_drama.py -k 'rank_feature_candidates' -q`

Expected: FAIL because `rank_short_drama_candidates` does not exist.

- [ ] **Step 3: Add the feature-specific 50/30/20 scorer and ranked helper**

Do not change the existing 45/35/20 `score_drama` function because that would alter current kinds. Add a feature-specific scorer with the approved 50/30/20 weights, then rank the commercial top three before applying the existing seven-day penalty.

```python
def score_short_drama_feature(
    drama: ShortDrama,
    *,
    population: Sequence[ShortDrama],
    usage_count: int = 0,
) -> DramaScore:
    commission = _minmax(drama.rate_bp, [row.rate_bp for row in population]) * 50
    heat = _minmax(
        math.log1p(max(0, drama.hot_degree)),
        [math.log1p(max(0, row.hot_degree)) for row in population],
    ) * 30
    appeal = float(drama_appeal_points(drama))
    penalty = float(min(max(0, usage_count) * 3, 9))
    return DramaScore(commission, heat, appeal, penalty, commission + heat + appeal - penalty)

def rank_short_drama_candidates(
    rows: Sequence[ShortDrama],
    *,
    usage_path: Path = USAGE_PATH,
    now: datetime | None = None,
    limit: int = 3,
    exclude_previously_used: bool = False,
) -> list[tuple[ShortDrama, DramaScore]]:
    if limit < 1:
        raise ValueError("短剧候选数量必须大于 0")
    current = now or datetime.now(TZ)
    usage = _load_usage(usage_path)
    used_ids = {str(item.get("drama_id") or "") for item in usage}
    candidates = [row for row in rows if not exclude_previously_used or row.drama_id not in used_ids]
    base = {
        row.drama_id: score_short_drama_feature(row, population=candidates)
        for row in candidates
    }
    commercial_top = sorted(
        candidates,
        key=lambda row: (-base[row.drama_id].final_score, -row.rate_bp, -row.hot_degree, row.drama_id),
    )[:limit]
    cutoff = current - timedelta(days=drama_repeat_days())
    recent_counts: dict[str, int] = {}
    for item in usage:
        try:
            used_at = datetime.fromisoformat(str(item.get("used_at") or ""))
        except ValueError:
            continue
        if used_at.tzinfo is None:
            used_at = used_at.replace(tzinfo=TZ)
        drama_id = str(item.get("drama_id") or "")
        if drama_id and used_at >= cutoff:
            recent_counts[drama_id] = recent_counts.get(drama_id, 0) + 1
    rescored = [
        (
            row,
            score_short_drama_feature(
                row,
                population=candidates,
                usage_count=recent_counts.get(row.drama_id, 0),
            ),
        )
        for row in commercial_top
    ]
    return sorted(
        rescored,
        key=lambda pair: (
            -pair[1].final_score,
            -base[pair[0].drama_id].final_score,
            -pair[0].rate_bp,
            -pair[0].hot_degree,
            pair[0].drama_id,
        ),
    )
```

- [ ] **Step 4: Write failing exact-attachment tests**

```python
def test_attach_selected_short_drama_never_reselects(monkeypatch) -> None:
    chosen = drama(drama_id="2", drama_name="已研究短剧")
    score = short_drama.DramaScore(50, 20, 10, 0, 80)
    monkeypatch.setattr(short_drama, "pick_short_drama", lambda *a, **k: pytest.fail("must not select"))
    out = short_drama.attach_selected_short_drama(
        {"title": "稿件", "content": "<p>" + "正文" * 800 + "</p>"},
        kind="short_drama_feature",
        drama=chosen,
        score=score,
        attribution=attribution(drama_id="2", plan_id=chosen.plan_id),
    )
    assert out["short_drama"]["drama_id"] == "2"
    assert len(short_drama.parse_short_drama_components(out["content"])) == 1
```

- [ ] **Step 5: Run the exact-attachment test and confirm RED**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_short_drama.py -k 'attach_selected' -q`

Expected: FAIL because the new kind and function are absent.

- [ ] **Step 6: Implement exact attachment and refactor automatic attachment to reuse it**

Add `short_drama_feature` to `LONGFORM_KINDS`, keep it out of `SOFT_SHORT_DRAMA_KINDS`, and move component insertion plus public metadata creation into `attach_selected_short_drama`. `attach_short_drama` must continue selecting automatically for existing kinds, then delegate to the new function.

- [ ] **Step 7: Run focused and existing short-drama tests**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_short_drama.py -q`

Expected: all tests pass.

- [ ] **Step 8: Commit only clean task hunks**

Inspect: `git diff -- stock-ai/scripts/tools/wechat_mp_short_drama.py stock-ai/tests/unit/test_wechat_mp_short_drama.py`

If either file contains unrelated pre-existing edits that cannot be isolated safely, do not commit this task yet. Otherwise stage only the task hunks and commit:

```bash
git commit -m "feat: expose ranked short-drama candidates"
```

### Task 2: Source-Bound Drama Research

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_short_drama_research.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_short_drama_research.py`

**Interfaces:**
- Produces: `DramaSource(source_id, url, title, source_name, source_type, official, excerpt)`
- Produces: `DramaFact(fact_id, fact_type, claim, source_ids)`
- Produces: `DramaResearch(drama_id, drama_name, sources, facts, rejected_claims)`
- Produces: `research_short_drama(drama: ShortDrama) -> DramaResearch`
- Produces: `validate_drama_research(research: DramaResearch) -> DramaResearch`

- [ ] **Step 1: Write failing pure-validation tests**

Cover two-source minimum, official-source minimum, allowed source IDs, two-source corroboration for every accepted fact, presence of `character`, `relationship`, `conflict`, and `reversal`, and drama identity matching.

```python
def test_validate_research_requires_two_sources_for_core_plot_fact() -> None:
    research = valid_research()
    bad = replace(
        research,
        facts=(DramaFact("conflict-1", "conflict", "主角遭到解雇", ("platform",)),),
    )
    with pytest.raises(ValueError, match="至少两个来源"):
        validate_drama_research(bad)
```

- [ ] **Step 2: Run validation tests and confirm RED**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_short_drama_research.py -q`

Expected: collection fails because the module does not exist.

- [ ] **Step 3: Implement immutable research models and deterministic validation**

Use `source_type` values `platform`, `producer`, `official_account`, `report`, and `reference`. Treat the short-drama platform metadata as source `platform`; require one additional HTTP(S) source with a different `source_id`.

```python
CORE_FACT_TYPES = frozenset({"character", "relationship", "conflict", "reversal"})

def validate_drama_research(research: DramaResearch) -> DramaResearch:
    if len(research.sources) < 2:
        raise ValueError("短剧研究至少需要两个有效来源")
    if not any(source.official for source in research.sources):
        raise ValueError("短剧研究至少需要一个官方来源")
    allowed = {source.source_id for source in research.sources}
    present_types = {fact.fact_type for fact in research.facts}
    if not CORE_FACT_TYPES <= present_types:
        raise ValueError("剧情事实缺少人物、关系、冲突或反转")
    for fact in research.facts:
        if not set(fact.source_ids) <= allowed:
            raise ValueError("剧情事实引用了未登记来源")
        if len(set(fact.source_ids)) < 2:
            raise ValueError("公开剧情事实至少需要两个来源")
    return research
```

- [ ] **Step 4: Write failing source-collection and LLM parsing tests**

Mock `fetch_discussion_research` and `call_wechat_mp_llm`. Assert that the prompt contains only the platform description plus fetched excerpts, returned source IDs are restricted to the collected set, and fenced or malformed JSON is rejected.

- [ ] **Step 5: Implement research collection and structured extraction**

Call `fetch_discussion_research` with the exact drama name plus “短剧” and its platform description as the relevance hook. Prepend an official `platform` source built from the drama-list record. Pass compact source objects to the existing LLM client and require this schema:

```json
{
  "drama_id": "1713873",
  "drama_name": "规范剧名",
  "facts": [
    {"fact_id": "character-1", "fact_type": "character", "claim": "可核实描述", "source_ids": ["platform", "source-1"]}
  ],
  "rejected_claims": ["只有单一来源或互相冲突的内容"]
}
```

The parser must reject any returned drama ID mismatch, unknown fact type, unknown source ID, empty claim, or missing core fact types. Do not accept search-result summaries without a fetched page excerpt.

- [ ] **Step 6: Run the research tests**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_short_drama_research.py -q`

Expected: all tests pass.

- [ ] **Step 7: Commit the isolated new files**

```bash
git add stock-ai/scripts/tools/wechat_mp_short_drama_research.py stock-ai/tests/unit/test_wechat_mp_short_drama_research.py
git commit -m "feat: verify short-drama plot sources"
```

### Task 3: Suspense-Led Single-Drama Article

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_short_drama_feature_article.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_short_drama_feature_article.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_content.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_short_drama_feature_article.py`

**Interfaces:**
- Produces: `FeatureParagraph(text, fact_ids)`
- Produces: `FeatureCopy(title, digest, paragraphs, title_fact_ids, digest_fact_ids)`
- Produces: `build_short_drama_feature_article(*, upload_figures=True, now=None) -> dict[str, Any]`
- Modifies: `_article_shell` by adding keyword argument `attach_promotion: bool = True`, with unchanged default behavior.

- [ ] **Step 1: Write failing copy-validation tests**

Test the 1,200–1,800 non-whitespace length, 5–9 prose paragraphs, source-bound title/digest/paragraph fact IDs, no Markdown headings, no unsupported ranking claims, and exact body reconstruction from returned paragraphs.

```python
def test_feature_copy_rejects_unbound_paragraph() -> None:
    copy = valid_copy()
    bad = replace(copy, paragraphs=(*copy.paragraphs, FeatureParagraph("突然又出现一个妹妹。", ())))
    with pytest.raises(ValueError, match="段落必须绑定剧情事实"):
        validate_feature_copy(bad, research=valid_research())
```

- [ ] **Step 2: Run copy tests and confirm RED**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_short_drama_feature_article.py -k 'copy' -q`

Expected: module import fails.

- [ ] **Step 3: Implement copy models, parser, and deterministic gate**

Require every title/digest/paragraph fact ID to exist in the ledger; reject exact normalized occurrences of every `rejected_claim`; reject `#`, bullet-heading syntax, emoji, and unverifiable superlative markers such as “全网第一” and “所有人都在追”. Keep the first reversal before the component and omit complete-ending facts.

- [ ] **Step 4: Write failing candidate-fallback tests**

Mock a three-item ranked list, exact attributions, research, and copy generation. Make the first research call fail and assert the second drama is written and attached; make all three fail and assert a summarized `RuntimeError` without any draft or usage side effect.

```python
def test_builder_falls_back_to_second_researchable_drama(monkeypatch) -> None:
    monkeypatch.setattr(feature, "rank_short_drama_candidates", lambda *a, **k: ranked_three())
    monkeypatch.setattr(feature, "research_short_drama", fail_first_then_return_second())
    article = feature.build_short_drama_feature_article(upload_figures=False, now=NOW)
    assert article["short_drama"]["drama_id"] == "2"
    assert article["short_drama_feature_report"]["attempts"][0]["status"] == "rejected"
```

The builder must load and validity-filter the pool, call `rank_short_drama_candidates(rows, limit=3, exclude_previously_used=True)`, and then process each candidate in order as `ensure_attribution_for_drama` followed by `research_short_drama`. Missing or mismatched attribution rejects that candidate before any research call. It must never call the automatic `pick_short_drama` path.

- [ ] **Step 5: Add the LLM generation and unsupported-claim audit**

Send only the validated fact ledger to the writer. Require strict JSON with `title`, `digest`, `title_fact_ids`, `digest_fact_ids`, and ordered `paragraphs[{text,fact_ids}]`. Then make a second LLM call that compares each exact public paragraph to the same fact ledger and returns `{"unsupported_claims": []}`. Any non-empty result rejects the candidate; the audit cannot add replacement facts.

- [ ] **Step 6: Render without automatic reselection and attach the researched drama**

Add `attach_promotion=True` to `_article_shell`; keep the default so all current callers are unchanged. The feature builder calls `_article_shell(title=copy.title, digest=copy.digest, body_text=copy.body, upload_figures=upload_figures, kind="short_drama_feature", engagement_kind="discussion", attach_promotion=False)`, obtains the already validated attribution, and calls `attach_selected_short_drama`.

Store this safe diagnostic mapping on the article:

```python
article["short_drama_feature_report"] = {
    "attempts": attempts,
    "sources": [{"url": s.url, "source_type": s.source_type, "official": s.official} for s in research.sources],
    "facts": [{"fact_id": f.fact_id, "fact_type": f.fact_type, "claim": f.claim} for f in research.facts],
    "body_chars": len(re.sub(r"\s+", "", copy.body)),
    "fact_gate": "passed",
    "claim_audit": "passed",
}
```

- [ ] **Step 7: Register the builder in content routing**

Add `short_drama_feature` to `DRAFT_KINDS`, not `DAILY_DRAFT_KINDS`, and route `build_article("short_drama_feature", upload_figures=upload_figures)` to the new builder. Add `disclaimer_for_kind("short_drama_feature") == ""` because this is entertainment recommendation copy, not investment material.

- [ ] **Step 8: Run article and content regression tests**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_short_drama_feature_article.py tests/unit/test_wechat_mp_disclaimer_render.py -q`

Expected: all tests pass.

- [ ] **Step 9: Commit only isolated task changes**

Inspect overlapping `wechat_mp_content.py` changes first. Stage only the new feature hunks and new files, then commit:

```bash
git commit -m "feat: build verified single-drama articles"
```

### Task 4: Manual CLI, Independent Slot, and Publishing Metadata

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_draft.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_draft_slots.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_seo.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_monetization.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_traffic_checklist.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_short_drama_feature_cli.py`

**Interfaces:**
- Preserves: `wechat_mp_draft --kind short_drama_feature [--dry-run]`
- Produces: `_resolve_draft_slot_key("short_drama_feature", None) == "short_drama_feature"`
- Produces: a dry-run diagnostic printer that reads only `short_drama_feature_report` and `short_drama` safe fields.

- [ ] **Step 1: Write failing CLI and slot tests**

```python
def test_short_drama_feature_is_manual_and_has_independent_slot() -> None:
    assert "short_drama_feature" in content.DRAFT_KINDS
    assert "short_drama_feature" not in content.DAILY_DRAFT_KINDS
    assert draft._resolve_kinds("all") == list(content.DAILY_DRAFT_KINDS)
    assert draft._resolve_draft_slot_key("short_drama_feature", None) == "short_drama_feature"
```

Add a dry-run test that mocks `_build_for_kind` and asserts output includes candidate score, rejected candidate reason, source URLs, fact count, body length, fact gate, and promotion summary while excluding `wx_ticket`, `cookie`, `token`, and `default_path`.

- [ ] **Step 2: Run CLI tests and confirm RED**

Run: `.venv/bin/pytest tests/unit/test_wechat_mp_short_drama_feature_cli.py -q`

Expected: routing and output assertions fail.

- [ ] **Step 3: Wire manual build, cover, slot, and diagnostics**

Route `_build_for_kind` to `build_article(kind, upload_figures=upload_figures)`. Return `short_drama_feature` from `_resolve_draft_slot_key`, pass that slot to `upsert_draft_article`, and reuse the discussion/TV cover fallback without changing existing cover selection. The normal post-save block already calls `verify_saved_short_drama` and `record_drama_usage`; add no second usage path.

Print the report with fixed safe labels. Do not serialize the full article, attribution object, or exception representation if it can contain request data.

- [ ] **Step 4: Add explicit SEO and engagement mappings**

Add:

```python
DIGEST_SEO_CORE["short_drama_feature"] = ("短剧推荐", "热门短剧")
DIGEST_SEO_PHRASE["short_drama_feature"] = "一部短剧的核心冲突与追剧看点"
TITLE_SEO_KEYWORDS["short_drama_feature"] = ("短剧", "逆袭", "反击", "反转", "追妻", "职场", "家庭")
TITLE_SEO_FRONT_KEYWORDS["short_drama_feature"] = ("短剧",)
HASHTAG_POOL["short_drama_feature"] = {"default": ("短剧", "短剧推荐", "追剧")}
```

Add one new-kind entry wherever monetization vertical words or engagement hooks use exact kind maps. The public CTA must be a single restrained watch prompt and must not claim popularity, scarcity, or guaranteed enjoyment.

- [ ] **Step 5: Add managed-title hints without broad deletion risk**

Register narrow hints such as `短剧推荐`, `这部短剧`, and `看到这里` for classification. Keep the independent slot as the primary identity; do not add broad hints such as `逆袭`, `家庭`, or `爱情` that could classify unrelated drafts.

- [ ] **Step 6: Run CLI, SEO, traffic, and short-drama regression tests**

Run:

```bash
.venv/bin/pytest \
  tests/unit/test_wechat_mp_short_drama_feature_cli.py \
  tests/unit/test_wechat_mp_short_drama.py \
  tests/unit/test_wechat_mp_seo.py \
  tests/unit/test_wechat_mp_traffic_checklist.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit only isolated routing hunks**

Because all five existing files currently have unrelated working-tree changes, review each diff and stage only the new-kind hunks. If hunk isolation is unsafe, leave the implementation uncommitted and report the exact files instead of mixing changes.

### Task 5: End-to-End Verification and Documentation

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-drafts/INDEX.md`
- Modify: `.cursor/skills/wechat-mp-drafts/reference.md`
- Test: all files from Tasks 1–4

**Interfaces:**
- Documents: the exact dry-run and live commands, independent slot, two-source gate, top-three fallback, and post-save usage semantics.

- [ ] **Step 1: Run focused static validation**

Run:

```bash
.venv/bin/python -m py_compile \
  scripts/tools/wechat_mp_short_drama.py \
  scripts/tools/wechat_mp_short_drama_research.py \
  scripts/tools/wechat_mp_short_drama_feature_article.py \
  scripts/tools/wechat_mp_content.py \
  scripts/tools/wechat_mp_draft.py
```

Expected: exit 0 with no output.

- [ ] **Step 2: Run the complete relevant unit suite**

Run:

```bash
.venv/bin/pytest \
  tests/unit/test_wechat_mp_short_drama.py \
  tests/unit/test_wechat_mp_short_drama_research.py \
  tests/unit/test_wechat_mp_short_drama_feature_article.py \
  tests/unit/test_wechat_mp_short_drama_feature_cli.py \
  tests/unit/test_wechat_mp_draft_short_drama.py \
  tests/unit/test_wechat_mp_disclaimer_render.py \
  tests/unit/test_wechat_mp_seo.py \
  tests/unit/test_wechat_mp_traffic_checklist.py \
  -q
```

Expected: all tests pass and zero collection errors.

- [ ] **Step 3: Run the real dry-run**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_draft \
  --kind short_drama_feature \
  --dry-run
```

Expected: one selected drama; zero secret fields; two or more sources including one official source; source-bound character, relationship, conflict, and reversal facts; 1,200–1,800 non-whitespace characters; one planned matching component; no material, draft, slot, or usage write.

- [ ] **Step 4: Update the three routed docs**

Add the new kind to the manual slot table and decision tree, document the exact command, and state that source failure stops the draft. Do not duplicate the whole design or expose environment secrets.

- [ ] **Step 5: Re-run doc and diff checks**

Run:

```bash
rg -n "short_drama_feature|单剧强情节" \
  .cursor/skills/wechat-mp-drafts/SKILL.md \
  .cursor/skills/wechat-mp-drafts/INDEX.md \
  .cursor/skills/wechat-mp-drafts/reference.md
git diff --check
```

Expected: all three docs contain the route, and `git diff --check` exits 0.

- [ ] **Step 6: Review final scope and commit when safe**

Run `git status --short`, inspect every touched-file diff, and ensure no `.env`, attribution cache, short-drama pool, usage history, output artifact, or unrelated user change is staged. Commit only isolated feature hunks; otherwise leave them uncommitted and report that constraint.

- [ ] **Step 7: Optional live “do not publish” acceptance after dry-run approval**

Only after the user reviews the real dry-run, run the same command without `--dry-run`. Verify the saved draft contains exactly one component matching the selected `drama_id`, opens the same drama, and records usage only after successful readback. This step creates an external WeChat draft but never publishes it.
