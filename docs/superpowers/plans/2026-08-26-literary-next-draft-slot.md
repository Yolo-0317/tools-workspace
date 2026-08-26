# 文学稿候补草稿槽位 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增受管理的 `literary_next` 槽位，使《道德经》与尚未发表的《徐霞客游记》同时保留在公众号草稿箱。

**Architecture:** 文学稿模型允许两个固定槽位，并在渲染、浏览器推送和草稿清理链路中原样传递 `slot_key`。草稿更新器仍按槽位独立替换，因而不会触碰另一文学槽位。

**Tech Stack:** Python 3、dataclass、pytest、微信公众号草稿 API、`wechat_mp_browser_write` 双确认流程。

## Global Constraints

- `literary` 继续作为文学稿默认槽位。
- 新槽位名称固定为 `literary_next`，不接受任意动态槽位。
- 两个槽位都必须纳入受管理草稿保留集合。
- 只写入草稿箱，不发表文章。
- 推送前后核对 `literary` 的媒体 ID 不变。

---

### Task 1: 允许文学稿选择候补槽位

**Files:**
- Modify: `stock-ai/tests/unit/test_wechat_mp_literary.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_literary.py`

**Interfaces:**
- Consumes: 文学稿 JSON 的 `slot_key: str`。
- Produces: `load_literary_draft_data()` 和 `build_literary_article()` 保留 `literary_next`。

- [ ] **Step 1: Write the failing test**

```python
def test_literary_next_slot_is_preserved() -> None:
    payload = _payload()
    payload["slot_key"] = "literary_next"
    draft = load_literary_draft_data(payload)
    article = build_literary_article(draft, upload_figures=False)
    assert draft.slot_key == "literary_next"
    assert article["slot_key"] == "literary_next"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_literary.py::test_literary_next_slot_is_preserved -q`

Expected: FAIL，提示文学草稿 `slot_key` 必须为 `literary`。

- [ ] **Step 3: Write minimal implementation**

在 `wechat_mp_literary.py` 定义允许集合 `LITERARY_SLOT_KEYS = {"literary", "literary_next"}`；校验使用该集合；构建文章时写入 `draft.slot_key`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_literary.py -q`

Expected: 全部 PASS。

### Task 2: 让候补槽位进入草稿保留集合

**Files:**
- Modify: `stock-ai/tests/unit/test_wechat_mp_draft_slots.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_draft_slots.py`

**Interfaces:**
- Consumes: `managed_slot_keys()`。
- Produces: 返回值包含 `literary_next`，供清理流程读取其媒体 ID。

- [ ] **Step 1: Write the failing test**

```python
def test_managed_slots_include_literary_next() -> None:
    assert "literary_next" in slots.managed_slot_keys()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_draft_slots.py::test_managed_slots_include_literary_next -q`

Expected: FAIL，返回集合中没有 `literary_next`。

- [ ] **Step 3: Write minimal implementation**

新增 `LITERARY_SLOT_KEYS = ("literary", "literary_next")`，并在 `managed_slot_keys()` 中合并这两个固定键。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_draft_slots.py -q`

Expected: 全部 PASS。

### Task 3: 将《道德经》转入候补槽位并推送

**Files:**
- Modify: `stock-ai/output/literary_daodejing.json`
- Runtime state: `stock-ai/data/wechat_mp_draft_slots.json`

**Interfaces:**
- Consumes: 已暂存工作流 `a69a6448-d0c6-4773-808e-0dbe2b0befc0`。
- Produces: `literary_next` 的新媒体 ID；`literary` 的原媒体 ID保持不变。

- [ ] **Step 1: Change the article slot**

将 `literary_daodejing.json` 的 `slot_key` 从 `literary` 改为 `literary_next`，重新执行 `stage` 前先把工作流从 `edited` 状态安全更新为引用新稿件内容。

- [ ] **Step 2: Run focused regression tests**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_literary.py tests/unit/test_wechat_mp_draft_slots.py tests/unit/test_wechat_mp_browser_write_cli.py tests/unit/test_wechat_mp_browser_push.py -q`

Expected: 全部 PASS。

- [ ] **Step 3: Record the existing literary slot**

读取 `stock-ai/data/wechat_mp_draft_slots.json`，记录 `literary.media_id` 与标题，确认是《徐霞客游记》对应草稿。

- [ ] **Step 4: Confirm and push the new slot**

运行 `confirm-push` 与 `push`，只写入公众号草稿箱。

- [ ] **Step 5: Verify both slots**

再次读取槽位文件，确认：`literary.media_id` 未变化；`literary_next.title` 为《老子说“无为”，最该听的为何不是懒人？》；两个媒体 ID 均非空且不同。
