# WeChat Thread-Confirmed Body Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow a complete article already shown and explicitly approved in the current task to enter the WeChat draft workflow without asking the user to paste the same body again.

**Architecture:** Add a distinct `thread_confirmed_body` provenance to the persisted browser-writing workflow, plus a `record-confirmed-body` CLI command that records the full body and the user’s confirmation text. Reuse the existing response, edit, second-confirmation, image, quality, and draft-slot gates; only broaden the accepted provenance set and update operator documentation.

**Tech Stack:** Python 3, `dataclasses`, `argparse`, JSON workflow files, pytest, Markdown Skill documentation.

## Global Constraints

- A complete article body must already exist; summaries, review conclusions, and fragments are not accepted.
- Store the user’s explicit confirmation text and time for `thread_confirmed_body` provenance.
- Preserve first confirmation, Agent edit notes, verified real images, second confirmation, quality checks, WeChat egress checks, and independent draft slots.
- Do not label a thread-confirmed body as a DeepSeek paste.
- Do not publish a public post; the workflow writes only to the WeChat draft box.
- Preserve compatibility with existing workflow JSON files.

---

### Task 1: Persist and validate thread-confirmed provenance

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_workflow.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_workflow.py`

**Interfaces:**
- Produces: `record_confirmed_body(workflow_id: str, raw_response: str, *, confirmation_text: str, sent_at: str = "", root: Path | None = None) -> BrowserWritingWorkflow`
- Produces: `require_hotspot_body_provenance(workflow: BrowserWritingWorkflow) -> None`
- Extends: `BrowserWritingWorkflow.response_confirmation_text: str` and `BrowserWritingWorkflow.response_confirmation_at: str`

- [ ] **Step 1: Write failing workflow tests**

Add tests that create and prompt-confirm a hotspot workflow, call `record_confirmed_body`, and assert:

```python
assert saved.status == WorkflowStatus.RESPONSE_RECEIVED
assert saved.response_provider == "thread_confirmed_body"
assert saved.response_confirmation_text == "就按照刚刚的正文发布"
assert saved.response_confirmation_at
```

Add rejection tests for empty confirmation text and for an audit-only payload such as:

```python
"这版通过，可以直接进入排版流程。\n\n核对要点：标题合规，事实边界清楚。"
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest tests/unit/test_wechat_mp_browser_workflow.py -q
```

Expected: FAIL because `record_confirmed_body` and the new workflow fields do not exist.

- [ ] **Step 3: Implement the minimal workflow changes**

In `wechat_mp_browser_workflow.py`:

```python
response_confirmation_text: str = ""
response_confirmation_at: str = ""
```

Add a small `_looks_like_complete_article(text: str) -> bool` validation that rejects empty text, short audit conclusions, and text beginning with review language without a substantial article body. Add `record_confirmed_body` using provider `thread_confirmed_body`; require non-empty confirmation text; set confirmation text and time.

Rename `require_deepseek_browser_response` to `require_hotspot_body_provenance` and accept `deepseek_browser`, `deepseek_user_paste`, and `thread_confirmed_body`. For the new provider, require both confirmation fields. Keep a compatibility alias only if existing callers or tests need it during the migration.

- [ ] **Step 4: Run the focused tests and verify pass**

Run the same pytest command. Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add stock-ai/scripts/tools/wechat_mp_browser_workflow.py stock-ai/tests/unit/test_wechat_mp_browser_workflow.py
git commit -m "功能：支持当前任务确认正文来源"
```

### Task 2: Add CLI recording and truthful provenance reporting

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_browser_write.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_codex_client.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_browser_push.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_codex_client.py`

**Interfaces:**
- Consumes: `record_confirmed_body(...)` and `require_hotspot_body_provenance(...)` from Task 1.
- Produces CLI: `record-confirmed-body WORKFLOW_ID --response-file PATH --confirmation-text TEXT [--root PATH]`.
- Produces: `record_thread_confirmed_body(kind: str) -> None` for generation provenance.

- [ ] **Step 1: Write failing CLI and push tests**

Add a parser/command test that runs:

```python
browser_cli.main([
    "record-confirmed-body",
    workflow.workflow_id,
    "--response-file", str(response_file),
    "--confirmation-text", "就按照刚刚的正文发布",
    "--root", str(tmp_path),
])
```

Assert status `response_received`, provider `thread_confirmed_body`, and stored confirmation text. Add a staged-summary assertion:

```python
assert "成稿来源: 当前任务已确认正文" in summary
```

Add a push provenance test that verifies `record_thread_confirmed_body("hotspot")` is called for the new provider and neither DeepSeek recorder is called.

- [ ] **Step 2: Run focused CLI tests and verify failure**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest \
  tests/unit/test_wechat_mp_browser_write_cli.py \
  tests/unit/test_wechat_mp_browser_push.py \
  tests/unit/test_wechat_mp_codex_client.py -q
```

Expected: FAIL because the command, summary label, and provenance recorder do not exist.

- [ ] **Step 3: Implement command and reporting**

Update the CLI parser and command dispatch. Replace DeepSeek-only helper naming where it controls all hotspot provenance. Map sources explicitly:

```python
response_labels = {
    "deepseek_user_paste": "用户粘贴的 DeepSeek 初稿",
    "deepseek_browser": "DeepSeek 固定浏览器会话",
    "thread_confirmed_body": "当前任务已确认正文",
}
```

In `wechat_mp_codex_client.py`, add `record_thread_confirmed_body` using provider `thread_confirmed_body` and source marker `thread_confirmed_response`. Route `_record_workflow_deepseek_provenance` through an accurately named provenance dispatcher.

- [ ] **Step 4: Run focused CLI tests and verify pass**

Run the same three-file pytest command. Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add \
  stock-ai/scripts/tools/wechat_mp_browser_write.py \
  stock-ai/scripts/tools/wechat_mp_codex_client.py \
  stock-ai/tests/unit/test_wechat_mp_browser_write_cli.py \
  stock-ai/tests/unit/test_wechat_mp_browser_push.py \
  stock-ai/tests/unit/test_wechat_mp_codex_client.py
git commit -m "功能：新增当前任务正文登记命令"
```

### Task 3: Update Skill rules and run regression validation

**Files:**
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-drafts/operations-sop.md`
- Modify: `.cursor/skills/wechat-mp-drafts/rules-implemented.md`
- Modify: `.cursor/skills/wechat-mp-writing/deepseek-writer-sop.md`

**Interfaces:**
- Documents the `record-confirmed-body` route created in Task 2.
- Preserves the default DeepSeek manual handoff while removing redundant repaste requirements when the complete body is already present and approved in the task.

- [ ] **Step 1: Update the operator rules**

State in each relevant document:

```text
默认仍由用户贴回 DeepSeek 完整输出。若完整正文已经在当前任务中完整展示，且用户明确要求按该正文发布，可登记为“当前任务已确认正文”，无需再次复制。审核结论、摘要、零散修改或 Agent 转述不能替代完整正文。
```

Add the exact command example:

```bash
uv run python -m scripts.tools.wechat_mp_browser_write record-confirmed-body \
  <workflow-id> \
  --response-file <full-body-file> \
  --confirmation-text "就按照刚刚的正文发布"
```

- [ ] **Step 2: Run workflow regression tests**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest \
  tests/unit/test_wechat_mp_browser_workflow.py \
  tests/unit/test_wechat_mp_browser_write_cli.py \
  tests/unit/test_wechat_mp_browser_push.py \
  tests/unit/test_wechat_mp_codex_client.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Validate both Skills**

Run:

```bash
/Users/huan.yu/.codex/skills/feishu-app-doc-reader/.venv/bin/python \
  /Users/huan.yu/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .cursor/skills/wechat-mp-drafts

/Users/huan.yu/.codex/skills/feishu-app-doc-reader/.venv/bin/python \
  /Users/huan.yu/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .cursor/skills/wechat-mp-writing
```

Expected: both report `Skill is valid!`.

- [ ] **Step 4: Commit Task 3**

```bash
git add \
  .cursor/skills/wechat-mp-drafts/SKILL.md \
  .cursor/skills/wechat-mp-drafts/operations-sop.md \
  .cursor/skills/wechat-mp-drafts/rules-implemented.md \
  .cursor/skills/wechat-mp-writing/deepseek-writer-sop.md
git commit -m "文档：更新公众号正文来源门禁"
```

### Task 4: Register and push the approved monthly-payment article

**Files:**
- Use: `stock-ai/output/platform_monthly_payment_20260916/article.json`
- Use: `stock-ai/assets/wechat_mp/inline-discussion/平台月付支付选项区隔/`
- Create: workflow JSON under `stock-ai/output/wechat_mp_browser_workflows/`

**Interfaces:**
- Consumes the new `record-confirmed-body` command.
- Produces a new independent WeChat draft slot using `hotspot_platform_monthly_payment_20260916_new`.

- [ ] **Step 1: Re-run article and image gates without writing WeChat**

Use the existing article JSON and image source records. Confirm title, digest, 2–3 highlights, at least three source domains, two verified body images, one reused cover, and the independent slot key.

- [ ] **Step 2: Create and advance the workflow**

Run `prepare`, `confirm-prompt`, and `record-confirmed-body`, using the full approved article body as the response file and the exact user confirmation `就按照刚刚的正文发布`.

- [ ] **Step 3: Stage and inspect the report**

Run `stage` with Agent edit notes for fact checking, prose editing, and image verification. Confirm the report says `成稿来源: 当前任务已确认正文` and lists one cover plus two body images.

- [ ] **Step 4: Register the second confirmation and push**

Run `confirm-push` using the already received explicit instruction, then `push`. Expected: a new WeChat draft media ID and no modification of unrelated slots.

- [ ] **Step 5: Verify draft-slot isolation**

Read the updated slot registry and confirm `hotspot_platform_monthly_payment_20260916_new` points to the new media ID while existing hotspot and hot-business slots retain their prior IDs.
