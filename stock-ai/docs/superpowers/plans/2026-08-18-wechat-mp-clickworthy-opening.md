# 微信公众号高点击且可推荐标题与引子 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为热点深评和热点商业稿提供可开关的具体化标题与合成情境引子，同时保持事实、合规、搜索路牌和推荐安全。

**Architecture:** 新增纯函数模块处理标题候选与引子文本。热点标题在现有清洗前调用它；正文仅在研究事实足够且开关开启时插入带披露语的合成情境。旧行为、人工标题与研究不足路径保持原样。

**Tech Stack:** Python 3、pytest、现有 `scripts.tools.wechat_mp_*` 模块。

## Global Constraints

- `WECHAT_MP_TITLE_VIRAL_MODE` 默认关闭；关闭时输出不变。
- 人工 `title_override` 不自动改写。
- 标题保留可搜索主体、通过既有公开合规清洗，且不超过 32 字。
- 合成情境必须明确披露，不得包含虚构机构回复、薪资、名额、私信、采访或未公开事实。
- 合成情境后 80 字内必须落到可核验的事件事实；研究不足时不插入。

---

### Task 1: 可开关的热点标题具体化

**Files:**
- Create: `scripts/tools/wechat_mp_clickworthy.py`
- Modify: `scripts/tools/wechat_mp_hotspot_article.py:1701-1737`
- Test: `tests/unit/test_wechat_mp_clickworthy.py`

**Interfaces:**
- Produces: `rewrite_clickworthy_title(title: str, *, topic_label: str, enabled: bool) -> str`。

- [ ] **Step 1: Write the failing test**

```python
def test_rewrite_clickworthy_title_makes_abstract_question_concrete() -> None:
    assert rewrite_clickworthy_title(
        "董明珠任校长，格力技校能改命吗？",
        topic_label="董明珠任格力技校校长",
        enabled=True,
    ) == "董明珠当校长，技校生毕业真能进格力吗？"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_wechat_mp_clickworthy.py::test_rewrite_clickworthy_title_makes_abstract_question_concrete -q`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def rewrite_clickworthy_title(title: str, *, topic_label: str, enabled: bool) -> str:
    if not enabled or "改命" not in title or "董明珠" not in title or "格力" not in title:
        return title
    return "董明珠当校长，技校生毕业真能进格力吗？"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_wechat_mp_clickworthy.py::test_rewrite_clickworthy_title_makes_abstract_question_concrete -q`

Expected: PASS.

- [ ] **Step 5: Integrate and verify**

Call the function after fact-title construction and before `sanitize_public_title` in both branches of `build_hotspot_title`. Generalize the literal branch only for abstract words when the topic label supplies a concrete subject, then run `uv run pytest tests/unit/test_wechat_mp_clickworthy.py tests/unit/test_wechat_mp_hotspot_article.py -q`.

### Task 2: 可披露的合成情境引子

**Files:**
- Modify: `scripts/tools/wechat_mp_clickworthy.py`
- Modify: `scripts/tools/wechat_mp_content.py:803-824`
- Test: `tests/unit/test_wechat_mp_clickworthy.py`

**Interfaces:**
- Produces: `prepend_disclosed_composite_opening(body: str, *, topic_label: str, fact_lines: list[str], enabled: bool) -> str`。

- [ ] **Step 1: Write the failing test**

```python
def test_composite_opening_discloses_its_status_and_lands_on_fact() -> None:
    out = prepend_disclosed_composite_opening(
        "格力宣布参与技校办学。",
        topic_label="格力技校",
        fact_lines=["格力宣布参与技校办学"],
        enabled=True,
    )
    assert "合成情境" in out
    assert "格力宣布参与技校办学" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_wechat_mp_clickworthy.py::test_composite_opening_discloses_its_status_and_lands_on_fact -q`

Expected: FAIL because the function does not exist.

- [ ] **Step 3: Write minimal implementation and integrate**

Return the original body unless enabled and a fact line is available; otherwise prepend a disclosure followed by the first fact line. Feed it research hit titles/snippets only for automatic hotspot/hot-business construction, and skip codex drafts and bodies that already begin with a disclosure.

- [ ] **Step 4: Run focused pipeline tests**

Run: `uv run pytest tests/unit/test_wechat_mp_clickworthy.py tests/unit/test_wechat_mp_hotspot_article.py tests/unit/test_wechat_mp_hot_business_article.py -q`

Expected: PASS.

### Task 3: 文档与全量验证

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/rules-implemented.md`
- Modify: `.cursor/skills/wechat-mp-writing/traffic-copy-craft.md`
- Modify: `docs/superpowers/plans/2026-08-18-wechat-mp-clickworthy-opening.md`

- [ ] **Step 1: Update operations rules**

Record the environment variable, coverage, disclosure wording, title/body consistency, and exclusions for manual titles and insufficient research.

- [ ] **Step 2: Verify and review**

Run: `uv run pytest tests/unit/test_wechat_mp_clickworthy.py tests/unit/test_wechat_mp_hotspot_article.py tests/unit/test_wechat_mp_hot_business_article.py tests/unit/test_wechat_mp_public.py -q` and `git diff --check`.

- [ ] **Step 3: Commit scoped changes**

Commit only the listed source, test, rule and plan files with message `feat: 优化公众号标题与引子`.
