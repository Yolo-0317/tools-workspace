# Short Drama Revenue Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace relevance-led short-drama selection with an explainable revenue-first ranking based on commission, logarithmic heat, appeal hooks, a narrow incompatibility gate, and top-three rotation.

**Architecture:** Keep the implementation inside `wechat_mp_short_drama.py`, where candidate eligibility, selection, attribution, and diagnostics already live. Introduce a score breakdown value object so ranking and user-visible diagnostics consume the same computed values, then integrate it into `pick_short_drama`, `attach_short_drama`, and `promotion_summary` without changing attribution or component construction.

**Tech Stack:** Python 3.11+, standard library (`dataclasses`, `math`, `re`, `datetime`), pytest.

## Global Constraints

- Optimize expected revenue with weights: commission 45%, logarithmic heat 35%, appeal 20%.
- Article relevance does not add score; it only rejects clearly incompatible serious-event and escapist-drama combinations.
- Apply recent-use penalties only after selecting the top three candidates by base commercial score.
- Fail closed when no eligible attributed candidate remains.
- Diagnostics must never expose `wxTicket`, full jump paths, cookies, or credentials.
- Preserve the existing WeChat attribution, component validation, draft write, and read-back gates.

---

### Task 1: Revenue Score Breakdown

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_short_drama.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_short_drama.py`

**Interfaces:**
- Produces: `DramaScore` with `commission_score`, `heat_score`, `appeal_score`, `usage_penalty`, and `final_score` floats.
- Produces: `drama_appeal_points(drama: ShortDrama) -> int` in the inclusive range 0–20.
- Produces: `score_drama(drama, *, population, usage_count=0) -> DramaScore`.

- [ ] **Step 1: Write failing score tests**

Add literal tests proving that commission contributes 45 points, logarithmic heat contributes 35 points, appeal contributes at most 20 points, and an equal-valued metric receives full credit. Include one ranking case where a 70% lower-heat candidate beats a 60% higher-heat candidate only when the weighted total is higher.

```python
def test_score_drama_uses_revenue_weights_and_log_heat() -> None:
    rows = [
        drama("high-rate", "城市故事", rate_bp=7000, hot_degree=100),
        drama("high-heat", "城市故事", rate_bp=6000, hot_degree=10_000),
    ]
    score = short_drama.score_drama(rows[0], population=rows)
    assert score.commission_score == 45.0
    assert score.heat_score == 0.0


def test_drama_appeal_points_caps_strong_and_medium_hooks_at_twenty() -> None:
    row = drama("hook", "豪门千金重生后反击", theme="都市、爱情、家庭")
    assert short_drama.drama_appeal_points(row) == 20
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
.venv/bin/pytest tests/unit/test_wechat_mp_short_drama.py -q
```

Expected: FAIL because `DramaScore`, the new scoring signature, and appeal scoring do not exist.

- [ ] **Step 3: Implement the minimal scoring model**

Add `math` import, the frozen `DramaScore` dataclass, centralized strong and medium hook term tuples, and scoring helpers. Use `math.log1p` before min-max normalization for heat. Change the equal-range normalization result from `0.5` to `1.0` to match the approved design.

```python
@dataclass(frozen=True)
class DramaScore:
    commission_score: float
    heat_score: float
    appeal_score: float
    usage_penalty: float
    final_score: float


def score_drama(
    drama: ShortDrama,
    *,
    population: Sequence[ShortDrama],
    usage_count: int = 0,
) -> DramaScore:
    commission = _minmax(drama.rate_bp, [row.rate_bp for row in population]) * 45
    heat = _minmax_float(
        math.log1p(drama.hot_degree),
        [math.log1p(row.hot_degree) for row in population],
    ) * 35
    appeal = drama_appeal_points(drama)
    penalty = min(max(0, usage_count) * 3, 9)
    return DramaScore(commission, heat, appeal, penalty, commission + heat + appeal - penalty)
```

- [ ] **Step 4: Run the score tests and verify GREEN**

Run the same pytest command. Expected: all score and existing parser/component tests pass after updating obsolete relevance-score assertions.

- [ ] **Step 5: Commit Task 1**

```bash
git add stock-ai/scripts/tools/wechat_mp_short_drama.py stock-ai/tests/unit/test_wechat_mp_short_drama.py
git commit -m "feat: score short dramas for expected revenue"
```

### Task 2: Incompatibility Gate and Top-Three Rotation

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_short_drama.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_short_drama.py`

**Interfaces:**
- Produces: `incompatibility_reason(article: Mapping[str, Any], drama: ShortDrama) -> str | None`.
- Changes: `pick_short_drama(...) -> tuple[ShortDrama, DramaScore]` so the caller retains the exact selected score.

- [ ] **Step 1: Write failing gate and rotation tests**

Add tests showing that weak relevance does not remove a commercially stronger candidate, a casualty/disaster article rejects an escapist romance candidate, and usage penalties can reorder only the base-score top three. Add a fourth low-scoring unused candidate and assert it never wins merely because it has no penalty.

```python
def test_pick_short_drama_allows_weak_relevance_for_higher_revenue(tmp_path: Path) -> None:
    rows = [
        drama("commercial", "千金反击", theme="都市、家庭", rate_bp=7000, hot_degree=10_000),
        drama("relevant", "报销制度", theme="职场", rate_bp=5000, hot_degree=100),
    ]
    picked, _ = short_drama.pick_short_drama(
        {"title": "公司报销观察"}, rows, kind="workspace",
        usage_path=tmp_path / "usage.json", now=NOW,
    )
    assert picked.drama_id == "commercial"
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
.venv/bin/pytest tests/unit/test_wechat_mp_short_drama.py -q
```

Expected: FAIL because selection still uses relevance and excludes every recently used candidate.

- [ ] **Step 3: Implement the negative gate and commercial shortlist**

Detect serious-event terms in `article_match_text` and escapist hook terms in drama name/theme/description. Return a short Chinese reason when both groups match. In `pick_short_drama`, remove incompatible candidates, raise `RuntimeError("没有通过题材安全门禁的短剧")` if none remain, rank all remaining candidates by base `final_score`, keep only the first three, count each shortlist drama's uses within the configured seven-day window, rescore with penalties, and select the highest final score.

- [ ] **Step 4: Run selection tests and verify GREEN**

Run the same pytest command. Expected: all selection, usage, attribution, and component tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add stock-ai/scripts/tools/wechat_mp_short_drama.py stock-ai/tests/unit/test_wechat_mp_short_drama.py
git commit -m "feat: rotate revenue-ranked short dramas"
```

### Task 3: Selection Diagnostics and End-to-End Verification

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_short_drama.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_short_drama.py`
- Verify: `stock-ai/tests/unit/test_wechat_mp_draft_short_drama.py`
- Verify: `stock-ai/tests/unit/test_wechat_mp_product.py`
- Verify: `stock-ai/tests/unit/test_wechat_mp_seo.py`

**Interfaces:**
- Changes: `attach_short_drama` stores a public `score` mapping under `article["short_drama"]`.
- Changes: `promotion_summary(article) -> str` includes commission, heat, theme, component scores, penalty, and final score.

- [ ] **Step 1: Write a failing public-diagnostics test**

```python
def test_promotion_summary_reports_score_without_attribution_secrets() -> None:
    article = {"short_drama": {
        "drama_name": "千金反击", "theme": "都市、家庭",
        "media_count": 60, "rate_bp": 7000, "hot_degree": 10_000,
        "score": {"commission": 45.0, "heat": 35.0, "appeal": 20.0,
                  "penalty": 3.0, "final": 97.0},
    }}
    summary = short_drama.promotion_summary(article)
    assert "返佣分45.0" in summary
    assert "最终分97.0" in summary
    assert "wxTicket" not in summary
```

- [ ] **Step 2: Run the diagnostics test and verify RED**

Run the single test. Expected: FAIL because current metadata and summary omit score details and heat.

- [ ] **Step 3: Store and render the selected score**

Convert the selected `DramaScore` into a literal public mapping with rounded one-decimal values. Store only business fields; do not store attribution objects, `default_path`, or `wx_ticket` in the article mapping. Extend `promotion_summary` with heat and score components.

- [ ] **Step 4: Run all relevant tests and compile check**

Run:

```bash
.venv/bin/pytest tests/unit/test_wechat_mp_short_drama.py tests/unit/test_wechat_mp_draft_short_drama.py tests/unit/test_wechat_mp_product.py tests/unit/test_wechat_mp_seo.py -q
.venv/bin/python -m py_compile scripts/tools/wechat_mp_short_drama.py
```

Expected: all tests pass and compilation exits zero.

- [ ] **Step 5: Validate against the cached real candidate pool**

Run a read-only local ranking using the current cache and print only drama name, commission, heat, theme, and score breakdown. Confirm the winner belongs to the base-score top three, has a nonzero commission, and contains no attribution secrets.

- [ ] **Step 6: Commit Task 3**

```bash
git add stock-ai/scripts/tools/wechat_mp_short_drama.py stock-ai/tests/unit/test_wechat_mp_short_drama.py
git commit -m "feat: explain short drama revenue selection"
```
