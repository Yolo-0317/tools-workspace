# Hot Business Short Drama Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable best-effort automatic short-drama promotion for `hot_business` while allowing the article to continue when promotion selection or construction fails.

**Architecture:** Reuse the existing short-drama pool, compatibility filter, ranking, attribution, component builder, saved-draft verification, and usage ledger. Add `hot_business` to the longform registration plus a narrowly scoped soft-failure policy; all other longform kinds retain strict behavior.

**Tech Stack:** Python 3.11, pytest, existing WeChat short-drama pipeline.

## Global Constraints

- `hot_business` attempts to insert exactly one compatible short-drama component when `WECHAT_MP_SHORT_DRAMA` is enabled.
- No candidate, pool failure, attribution failure, or component-build failure must not block a `hot_business` draft.
- Soft failures are stored only in `article["short_drama_skipped"]`; they must not enter public article content.
- Existing longform kinds remain strict when short-drama promotion is enabled.
- A `hot_business` article with a component must still reject multiple components and ordinary CPS products.
- Usage is recorded only after the saved WeChat draft passes the existing read-back verification.
- Do not change the drama scoring formula, incompatibility rules, scheduler, or draft slot behavior.

---

### Task 1: Register Best-Effort Promotion and Preserve Strict Kinds

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_short_drama.py:40-60,620-705`
- Modify: `stock-ai/tests/unit/test_wechat_mp_short_drama.py:1105-1255`
- Modify: `stock-ai/scripts/tools/wechat_mp_draft.py:310-330`
- Modify: `stock-ai/tests/unit/test_wechat_mp_hot_business_cli.py`

**Interfaces:**
- Consumes: `attach_short_drama(article, kind, now=None)`, `assert_longform_promotion_safe(article, kind)`, `promotion_summary(article)`.
- Produces: `SOFT_SHORT_DRAMA_KINDS = frozenset({"hot_business"})` and optional `article["short_drama_skipped"] = {"reason": str}`.

- [ ] **Step 1: Write failing tests for a compatible automatic selection**

Add a test using the existing `drama()` and `attribution()` fixtures. Patch only the external pool and attribution boundaries, keep `attach_short_drama` and the real picker/component builder active:

```python
def test_hot_business_attaches_best_compatible_short_drama(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_SHORT_DRAMA", "1")
    monkeypatch.setattr(
        short_drama,
        "load_or_refresh_drama_pool",
        lambda **_: [
            drama("unsafe", "复仇归来", theme="复仇", description="血案复仇"),
            drama("safe", "职场新局", theme="职场", description="公司经营故事"),
        ],
    )
    monkeypatch.setattr(
        short_drama,
        "ensure_attribution_for_drama",
        lambda row, **_: attribution(row.drama_id),
    )
    article = {
        "title": "某品牌涨价，渠道成本由谁承担",
        "body_text": "品牌、渠道与成本变化的商业分析。",
        "content": "<p>品牌、渠道与成本变化的商业分析。</p>",
    }

    out = short_drama.attach_short_drama(article, kind="hot_business", now=NOW)

    assert out["short_drama"]["drama_id"] == "safe"
    assert out["content"].count('data-adtype="short-play"') == 1
    assert "short_drama_skipped" not in out
```

Production mutation caught: removing `hot_business` registration or bypassing the real compatibility filter leaves the article without the expected safe component.

- [ ] **Step 2: Run the compatible-selection test and verify RED**

Run:

```bash
cd stock-ai
PYTHONPATH=. uv run pytest tests/unit/test_wechat_mp_short_drama.py::test_hot_business_attaches_best_compatible_short_drama -q
```

Expected: FAIL because `hot_business` is not in `LONGFORM_KINDS`, so no component is attached.

- [ ] **Step 3: Write failing tests for soft failure and strict-kind regression**

Add tests covering no safe candidate, an external promotion exception, the relaxed missing-component assertion, and unchanged strict behavior:

```python
def test_hot_business_soft_skips_when_no_drama_is_compatible(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_SHORT_DRAMA", "1")
    monkeypatch.setattr(
        short_drama,
        "load_or_refresh_drama_pool",
        lambda **_: [drama("unsafe", "复仇归来", theme="复仇", description="血案复仇")],
    )
    article = {
        "title": "事故赔偿背后的保险成本",
        "body_text": "事故、赔偿与保险成本。",
        "content": "<p>事故、赔偿与保险成本。</p>",
    }

    out = short_drama.attach_short_drama(article, kind="hot_business", now=NOW)

    assert "short_drama" not in out
    assert "没有通过题材安全门禁的短剧" in out["short_drama_skipped"]["reason"]
    short_drama.assert_longform_promotion_safe(out, kind="hot_business")


def test_hot_business_soft_skips_promotion_dependency_failure(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_SHORT_DRAMA", "1")
    monkeypatch.setattr(
        short_drama,
        "load_or_refresh_drama_pool",
        lambda **_: (_ for _ in ()).throw(RuntimeError("短剧池不可用")),
    )

    out = short_drama.attach_short_drama(
        {"title": "平台涨价", "body_text": "商业分析", "content": "<p>商业分析</p>"},
        kind="hot_business",
        now=NOW,
    )

    assert out["short_drama_skipped"] == {"reason": "短剧池不可用"}


def test_existing_hotspot_still_requires_short_drama_when_enabled(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_SHORT_DRAMA", "1")
    with pytest.raises(RuntimeError, match="缺少短剧组件"):
        short_drama.assert_longform_promotion_safe(
            {"content": "<p>正文</p>"}, kind="hotspot"
        )
```

Production mutations caught: re-raising a promotion error for `hot_business`, relaxing every longform kind, or silently swallowing the reason breaks a separate assertion.

- [ ] **Step 4: Run the soft-failure tests and verify RED**

Run the three new test node IDs. Expected failures:

- no-compatible case raises instead of returning an article;
- pool exception propagates;
- the compatible-selection test still lacks a component;
- the strict `hotspot` characterization remains PASS.

- [ ] **Step 5: Implement the minimal short-drama policy**

In `wechat_mp_short_drama.py`:

```python
LONGFORM_KINDS = frozenset({
    "hotspot", "hot_business", "tv_review", "tv", "film", "movie",
    "sector", "market", "news", "top5", "dragons", "workspace", "temp",
})
SOFT_SHORT_DRAMA_KINDS = frozenset({"hot_business"})


def _soft_skip_short_drama(
    article: Mapping[str, Any], *, kind: str, error: Exception
) -> dict[str, Any]:
    if kind not in SOFT_SHORT_DRAMA_KINDS:
        raise error
    out = dict(article)
    out["short_drama_skipped"] = {"reason": str(error) or type(error).__name__}
    return out
```

Wrap the promotion-only body of `attach_short_drama` in `try/except Exception as exc` and return `_soft_skip_short_drama(...)`. Before calling `pick_short_drama`, explicitly raise `RuntimeError("没有通过题材安全门禁的短剧")` when every eligible row is incompatible; do not pass an empty compatible set into ranking. Keep all existing strict-kind exceptions unchanged.

Change the missing-component branch in `assert_longform_promotion_safe` to:

```python
if short_drama_enabled() and count == 0 and normalized not in SOFT_SHORT_DRAMA_KINDS:
    raise RuntimeError("长文缺少短剧组件")
```

Do not relax the ordinary-CPS or multiple-component checks.

- [ ] **Step 6: Run short-drama tests and verify GREEN**

Run:

```bash
cd stock-ai
PYTHONPATH=. uv run pytest tests/unit/test_wechat_mp_short_drama.py -q
```

Expected: all short-drama tests pass with no new warnings.

- [ ] **Step 7: Add a dry-run output test for the skip reason**

Extend the existing hot-business CLI acceptance fixture with an article containing:

```python
"short_drama_skipped": {"reason": "没有通过题材安全门禁的短剧"}
```

Assert the captured dry-run output contains:

```python
assert "短剧推广: 已跳过" in output
assert "没有通过题材安全门禁的短剧" in output
```

Production mutation caught: failing to expose an internal skip reason during dry-run leaves operators unable to distinguish disabled promotion from a safe soft failure.

- [ ] **Step 8: Run the CLI output test and verify RED**

Run:

```bash
cd stock-ai
PYTHONPATH=. uv run pytest tests/unit/test_wechat_mp_hot_business_cli.py::test_manual_hot_business_dry_run_prints_quality_report_without_upload -q
```

Expected: FAIL because `wechat_mp_draft.main()` currently prints promotion information only when `short_drama` exists.

- [ ] **Step 9: Implement dry-run skip reporting**

In the dry-run output branch of `wechat_mp_draft.py`, after the existing `short_drama` summary:

```python
skip_meta = article.get("short_drama_skipped") or {}
if kind == "hot_business" and skip_meta:
    print(f"短剧推广: 已跳过 · {skip_meta.get('reason') or '无可用候选'}")
```

Do not include this metadata in `article["content"]` or `body_text`.

- [ ] **Step 10: Run focused regression tests**

Run:

```bash
cd stock-ai
PYTHONPATH=. uv run pytest \
  tests/unit/test_wechat_mp_short_drama.py \
  tests/unit/test_wechat_mp_hot_business_cli.py \
  tests/unit/test_wechat_mp_hot_business_article.py -q
```

Expected: all tests pass.

- [ ] **Step 11: Verify syntax and diff hygiene**

Run:

```bash
cd stock-ai
python3 -m py_compile \
  scripts/tools/wechat_mp_short_drama.py \
  scripts/tools/wechat_mp_draft.py
git diff --check -- \
  scripts/tools/wechat_mp_short_drama.py \
  scripts/tools/wechat_mp_draft.py \
  tests/unit/test_wechat_mp_short_drama.py \
  tests/unit/test_wechat_mp_hot_business_cli.py
```

Expected: both commands exit 0 with no output.

- [ ] **Step 12: Commit only the implementation files**

Because the worktree contains unrelated changes, inspect and stage only the exact implementation hunks before committing:

```bash
git diff -- \
  stock-ai/scripts/tools/wechat_mp_short_drama.py \
  stock-ai/scripts/tools/wechat_mp_draft.py \
  stock-ai/tests/unit/test_wechat_mp_short_drama.py \
  stock-ai/tests/unit/test_wechat_mp_hot_business_cli.py
git add -p -- stock-ai/scripts/tools/wechat_mp_short_drama.py
git add -p -- stock-ai/scripts/tools/wechat_mp_draft.py
git add -p -- stock-ai/tests/unit/test_wechat_mp_short_drama.py
git add -p -- stock-ai/tests/unit/test_wechat_mp_hot_business_cli.py
git diff --cached --check
git commit -m "feat: add best-effort drama to hot business"
```
