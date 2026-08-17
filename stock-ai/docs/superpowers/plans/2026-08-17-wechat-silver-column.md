# WeChat Silver Column Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual-only `silver` WeChat article flow for 50—65 year-old readers across relationship, health, and money/fraud topics.

**Architecture:** Introduce an immutable structured draft contract, a local evergreen topic bank with 30-day rotation, and a JSON-only writer that feeds the existing article rendering shell. Register `silver` in the manual CLI, presentation maps, public-safety gates, independent draft slot, and best-effort short-drama promotion without modifying automatic batches.

**Tech Stack:** Python 3.11, pytest, JSON, existing WeChat rendering/SEO/originality/short-drama modules.

## Global Constraints

- The four account directions `silver`, `hot_business`, `hotspot`, and `tv_review` are all manually triggered.
- `silver` must not appear in `DAILY_DRAFT_KINDS` or any `SCHEDULE_BATCHES` entry.
- Public titles must not add `银发栏目`, `五十岁以后`, or another fixed column prefix.
- Public copy addresses 50—65 year-old readers directly and must not use patronizing age stereotypes or age anxiety.
- `health` content must not diagnose, interpret personal test results, or recommend drugs, supplements, or treatment plans.
- `money` content must not recommend financial products, predict returns, or provide personalized investment advice.
- Every structured draft needs three distinct source domains, traceable fact URLs, a 1600—2600 non-whitespace body, and `slot_key="silver"`.
- Short-drama promotion is best effort: one safe component when available, otherwise the article continues.
- Dry-run performs no WeChat material upload, draft write, or short-drama usage recording.
- No new dependency, scheduler, or automatic publishing behavior.

---

### Task 1: Structured Silver Draft Contract and Safety Gates

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_codex_silver.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_codex_silver.py`

**Interfaces:**
- Consumes: existing originality helpers and standard-library `urllib.parse`.
- Produces: `SilverFact`, `CodexSilverDraft`, `load_codex_silver_draft_data(data)`, `load_codex_silver_draft(path)`, `validate_silver_draft(draft)`, `validate_codex_silver_originality(draft, history_posts)`.

- [ ] **Step 1: Write failing contract tests**

Create a valid fixture and tests that reject an invalid lane, body outside 1600—2600 characters, fewer than three domains, a fact URL outside `research_urls`, a rejected claim copied into public text, a health draft without an authoritative health domain, health treatment language, a money draft without an authoritative regulator domain, money product/return advice, and fixed column-title prefixes.

```python
def valid_payload(lane: str = "relation") -> dict[str, object]:
    urls = [
        "https://gov.example/a",
        "https://hospital.example/b",
        "https://media.example/c",
    ]
    return {
        "title": "退休以后，夫妻为什么更容易为小事争执？",
        "digest": "从生活节奏和家庭边界解释退休后的相处变化。",
        "body": "具体生活场景和可执行建议。" * 170,
        "topic": "退休后夫妻相处",
        "lane": lane,
        "research_urls": urls,
        "original_thesis": "退休后的争执往往不是感情变差，而是时间和家庭角色需要重新分配。",
        "reader_problem": "退休后夫妻全天相处，怎样减少反复争执？",
        "facts": [{"claim": "生活节奏改变需要适应", "source_url": urls[0]}],
        "practical_steps": ["约定各自独处时间"],
        "cautions": ["持续冲突可寻求专业帮助"],
        "rejected_claims": [],
        "slot_key": "silver",
    }
```

- [ ] **Step 2: Run tests and verify RED**

```bash
cd stock-ai
PYTHONPATH=. uv run pytest tests/unit/test_wechat_mp_codex_silver.py -q
```

Expected: collection fails because `wechat_mp_codex_silver` does not exist.

- [ ] **Step 3: Implement immutable types and validators**

```python
SILVER_LANES = frozenset({"relation", "health", "money"})
SILVER_SLOT_KEY = "silver"

@dataclass(frozen=True)
class SilverFact:
    claim: str
    source_url: str

@dataclass(frozen=True)
class CodexSilverDraft:
    title: str
    digest: str
    body: str
    topic: str
    lane: str
    research_urls: tuple[str, ...]
    original_thesis: str
    reader_problem: str
    facts: tuple[SilverFact, ...]
    practical_steps: tuple[str, ...]
    cautions: tuple[str, ...]
    rejected_claims: tuple[str, ...]
    slot_key: str = SILVER_SLOT_KEY
```

Use explicit authority-domain suffix sets for health (`gov.cn`, `nhc.gov.cn`, `chinacdc.cn`, recognized hospital/medical sources in the fixture-controlled validator) and money (`gov.cn`, `mohrss.gov.cn`, `mps.gov.cn`, `nfra.gov.cn`, `samr.gov.cn`, `court.gov.cn`). Match suffix boundaries, not substring containment. Reject public titles starting with the banned prefixes and scan normalized public text for banned medical/financial recommendation phrases.

- [ ] **Step 4: Run contract and originality regressions**

```bash
PYTHONPATH=. uv run pytest \
  tests/unit/test_wechat_mp_codex_silver.py \
  tests/unit/test_wechat_mp_codex_hot_business.py \
  tests/unit/test_wechat_mp_codex_hotspot.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit Task 1 files**

```bash
git add -- stock-ai/scripts/tools/wechat_mp_codex_silver.py stock-ai/tests/unit/test_wechat_mp_codex_silver.py
git commit -m "feat: validate structured silver drafts"
```

---

### Task 2: Evergreen Topic Bank and 30-Day Rotation

**Files:**
- Create: `stock-ai/data/wechat_mp_silver_topics.json`
- Create: `stock-ai/scripts/tools/wechat_mp_silver_topics.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_silver_topics.py`

**Interfaces:**
- Produces: `SilverTopic`, `load_silver_topics(path=TOPICS_PATH)`, `pick_silver_topic(lane=None, now=None, usage_path=USAGE_PATH)`, `record_silver_topic_usage(topic, used_at=None, usage_path=USAGE_PATH)`.

- [ ] **Step 1: Write failing behavior tests**

Test a literal temporary topic bank with two entries per lane. Assert lane restriction, default three-lane rotation, exclusion of a topic used within 30 days, reuse after 30 days, malformed lane rejection, and fail-closed behavior when every eligible topic is recent.

```python
def test_pick_silver_topic_respects_lane_and_recent_usage(tmp_path):
    # Write literal JSON fixtures and one usage row 10 days old.
    picked = pick_silver_topic(
        lane="health", now=NOW, topics_path=topics_path, usage_path=usage_path
    )
    assert picked.topic_id == "health-2"
```

- [ ] **Step 2: Run tests and verify RED**

Expected: missing module import.

- [ ] **Step 3: Implement topic records and bank**

`SilverTopic` fields: `topic_id`, `lane`, `title`, `reader_problem`, `search_terms`, `scene_prompt`, `risk_notes`. The bank must contain at least six concrete topics per lane. Selection sorts by least-recently used lane and topic, excludes the last 30 days, and does not use random choice so tests and manual runs are reproducible.

- [ ] **Step 4: Run topic tests and verify GREEN**

```bash
PYTHONPATH=. uv run pytest tests/unit/test_wechat_mp_silver_topics.py -q
```

- [ ] **Step 5: Commit Task 2 files**

```bash
git add -- stock-ai/data/wechat_mp_silver_topics.json stock-ai/scripts/tools/wechat_mp_silver_topics.py stock-ai/tests/unit/test_wechat_mp_silver_topics.py
git commit -m "feat: rotate evergreen silver topics"
```

---

### Task 3: JSON-Only Silver Writer and Article Builder

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_silver_article.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_silver_article.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_content.py`

**Interfaces:**
- Consumes: `pick_silver_topic`, `CodexSilverDraft`, existing `call_wechat_mp_llm`, `_article_shell`, `attach_publish_hints`.
- Produces: `generate_silver_draft(lane=None, topic_hint="")`, `build_silver_article(lane=None, topic_hint="", codex_draft=None, upload_figures=True)`.

- [ ] **Step 1: Write failing writer and builder tests**

Mock only the external LLM response and research provider. Assert the writer passes the response through `load_codex_silver_draft_data`, malformed JSON fails closed, health and money prompts include their exact safety rules, the builder sets `slot_key="silver"`, and `upload_figures=False` reaches `_article_shell`.

```python
def test_build_silver_article_keeps_natural_title(monkeypatch):
    monkeypatch.setattr(article_mod, "generate_silver_draft", lambda **_: valid_draft())
    article = article_mod.build_silver_article(upload_figures=False)
    assert article["title"] == "退休以后，夫妻为什么更容易为小事争执？"
    assert article["slot_key"] == "silver"
    assert article["silver_report"]["lane"] == "relation"
```

- [ ] **Step 2: Run tests and verify RED**

Expected: missing writer module.

- [ ] **Step 3: Implement research and JSON writer**

The prompt must include the selected topic, complete researched snippets, allowed URLs, lane-specific safety block, exact JSON schema, reader-first tone, 1600—2600 character limit, short-paragraph requirement, and bans on fixed prefixes and visible editorial metadata. Parse exactly one JSON object and do not fall back to templates or another article kind.

- [ ] **Step 4: Register `silver` in content dispatch**

Add `silver` to `DRAFT_KINDS` only. Dispatch locally:

```python
if k == "silver":
    from scripts.tools.wechat_mp_silver_article import build_silver_article
    return build_silver_article(
        lane=silver_lane,
        topic_hint=topic_hint,
        codex_draft=codex_draft,
        upload_figures=upload_figures,
    )
```

Extend `build_article` with `silver_lane: str | None = None`. Do not add `silver` to `DAILY_DRAFT_KINDS`.

- [ ] **Step 5: Run writer and rendering regressions**

```bash
PYTHONPATH=. uv run pytest \
  tests/unit/test_wechat_mp_silver_article.py \
  tests/unit/test_wechat_mp_disclaimer_render.py \
  tests/unit/test_wechat_mp_hot_business_article.py -q
```

- [ ] **Step 6: Commit Task 3 files**

Stage only the relevant `wechat_mp_content.py` hunks because the worktree contains unrelated changes.

---

### Task 4: Manual CLI, Independent Slot, Presentation, and Short Drama

**Files:**
- Create: `stock-ai/tests/unit/test_wechat_mp_silver_cli.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_draft.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_draft_slots.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_masthead.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_seo.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_monetization.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_public.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_traffic_checklist.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_short_drama.py`

**Interfaces:**
- Produces: `wechat_mp_draft --kind silver [--silver-lane relation|health|money] [--topic TEXT] [--codex-draft PATH] [--dry-run]` and slot `silver`.

- [ ] **Step 1: Write failing CLI acceptance tests**

Assert `silver` is manual-only, `--silver-lane` accepts only a single silver kind, `--topic` accepts silver and hot-business only, `--codex-draft` loads the matching contract, dry-run forwards `upload_figures=False`, formal flow uses `slot_key="silver"`, no fixed title prefix is introduced, no scheduled batch contains silver, and dry-run prints lane/source/fact/authority/short-drama information without calling draft or image upload APIs.

- [ ] **Step 2: Run CLI tests and verify RED**

```bash
PYTHONPATH=. uv run pytest tests/unit/test_wechat_mp_silver_cli.py -q
```

- [ ] **Step 3: Implement manual routing**

Add argparse choice `--silver-lane relation|health|money`. Generalize topic validation to permit exactly one `hot_business` or `silver`. Generalize Codex loader routing for `hotspot`, `hot_business`, and `silver`. Pass `silver_lane`, `topic_hint`, and `upload_figures` into the builder. Resolve the slot unconditionally to `silver` for this kind.

- [ ] **Step 4: Add exact presentation mappings**

- Draft slot title hints: retirement, health, family, pension, fraud phrases without forcing a prefix.
- Masthead slogan: `退休不是退场，把日子重新安排好`.
- SEO core: `("退休生活", "中年生活")`; lane-specific phrases and hashtags.
- Monetization vocabulary: relation `夫妻/子女/边界/退休/生活`, health `睡眠/饮食/运动/体检/习惯`, money `养老金/消费/防骗/旅游/直播购物`.
- Public disclaimer: lane-specific health, money, or general-information notice.
- Traffic checklist: 1600—2600 characters, 3—5 headings, natural title, opening life scene, final interaction question.
- Short drama: add `silver` to `LONGFORM_KINDS` and `SOFT_SHORT_DRAMA_KINDS`; retain ordinary-CPS and duplicate-component blocking.

- [ ] **Step 5: Run focused presentation and short-drama regressions**

```bash
PYTHONPATH=. uv run pytest \
  tests/unit/test_wechat_mp_silver_cli.py \
  tests/unit/test_wechat_mp_short_drama.py \
  tests/unit/test_wechat_mp_monetization.py \
  tests/unit/test_wechat_mp_sousou_eval.py \
  tests/unit/test_wechat_mp_disclaimer_render.py -q
```

- [ ] **Step 6: Commit Task 4 hunks only**

Use `git add -p` for every pre-dirty file and inspect `git diff --cached --check` before committing.

---

### Task 5: Operator Documentation and End-to-End Verification

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-drafts/INDEX.md`
- Modify: `stock-ai/tests/unit/test_wechat_mp_silver_cli.py`

**Interfaces:**
- Produces: documented manual commands and final acceptance evidence.

- [ ] **Step 1: Add command-level acceptance test**

Model this invocation with controlled external boundaries:

```text
wechat_mp_draft --kind silver --silver-lane health --topic 退休后每天走一万步合适吗 --dry-run
```

Assert one `=== silver ===` report, lane `health`, at least three source domains, authority gate PASS, no fixed title prefix, no image/material upload, no WeChat draft write, and no usage record.

- [ ] **Step 2: Run acceptance test and verify RED before final report wiring**

- [ ] **Step 3: Complete dry-run report and update docs**

Document the three commands from the design, all-manual account structure, independent `silver` slot, safety gates, best-effort short drama, and the fact that silver does not consume the daily hotspot pool automatically.

- [ ] **Step 4: Run all silver and adjacent regressions**

```bash
PYTHONPATH=. uv run pytest \
  tests/unit/test_wechat_mp_codex_silver.py \
  tests/unit/test_wechat_mp_silver_topics.py \
  tests/unit/test_wechat_mp_silver_article.py \
  tests/unit/test_wechat_mp_silver_cli.py \
  tests/unit/test_wechat_mp_short_drama.py \
  tests/unit/test_wechat_mp_hot_business_cli.py \
  tests/unit/test_wechat_mp_hot_business_article.py -q
```

- [ ] **Step 5: Verify syntax, diff hygiene, and scheduler isolation**

```bash
python3 -m py_compile \
  scripts/tools/wechat_mp_codex_silver.py \
  scripts/tools/wechat_mp_silver_topics.py \
  scripts/tools/wechat_mp_silver_article.py \
  scripts/tools/wechat_mp_content.py \
  scripts/tools/wechat_mp_draft.py
git diff --check
rg -n 'silver' scripts/tools/wechat_mp_draft_batch.py scripts/wechat_mp_draft_scheduled.sh
```

Expected: compile and diff checks exit 0; scheduler search returns no match.

- [ ] **Step 6: Run a real dry-run without publishing**

```bash
PYTHONPATH=. uv run python -m scripts.tools.wechat_mp_draft --kind silver --silver-lane relation --dry-run
```

Expected: a complete preview, or a clear fail-closed research/authentication message before any WeChat write.

- [ ] **Step 7: Commit documentation and acceptance-test hunks**

Stage only the silver documentation additions and exact acceptance-test hunks, preserving all unrelated dirty-worktree changes.
