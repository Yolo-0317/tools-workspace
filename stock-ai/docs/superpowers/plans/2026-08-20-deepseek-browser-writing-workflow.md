# DeepSeek Browser Writing Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a two-confirmation workflow in which Agent researches and prepares prompts, OpenCLI writes through one fixed logged-in DeepSeek Chrome conversation, Agent stages an edited hotspot or literary article, and the existing WeChat pipeline pushes only after the second confirmation.

**Architecture:** Add a small OpenCLI browser adapter, a persistent state machine under `output/`, and one orchestration CLI with explicit subcommands. Reuse the existing hotspot renderer and WeChat upsert path; add a separate `literary` article model, cache, renderer entry, and slot while keeping `tv_review` unchanged. Browser and login failures stop the workflow and never call another model or WeChat API.

**Tech Stack:** Python 3.11+, OpenCLI 1.8 browser `bind/state/type/click/eval/unbind`, pytest, existing WeChat MP rendering and draft API modules.

## Global Constraints

- The fixed conversation ID is `f0cc031d-233f-4648-807d-354275738e61` for both `hotspot` and `literary`.
- OpenCLI must bind the current foreground Chrome tab; it must not open an automation window.
- Prompt confirmation and push confirmation are separate, per-workflow, non-reusable gates.
- If DeepSeek is logged out, show the exact login instruction from the design and stop.
- DeepSeek failure must not fall back to Codex, DeepSeek API, Composer, templates, or another conversation.
- `literary` is a manual-only kind and slot shared by literature and `典籍里的中国`; it must not overwrite `tv_review`.
- OpenCLI must never read, print, or persist cookies, tokens, credentials, or browser storage.
- Agent must unbind after browser work and leave the user's Chrome tab open.
- No workflow may call the WeChat API before state `push_confirmed`.
- Preserve unrelated dirty-worktree changes and commit only files from the current task.

---

### Task 1: Persistent two-confirmation workflow state

**Files:**
- Create: `scripts/tools/wechat_mp_browser_workflow.py`
- Test: `tests/unit/test_wechat_mp_browser_workflow.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `WorkflowStatus`, `BrowserWritingWorkflow`, `create_workflow()`, `load_workflow()`, `confirm_prompt()`, `record_response()`, `stage_edited_article()`, `confirm_push()`, `mark_drafted()`, and `mark_blocked()`.
- Persists: `output/wechat_mp_browser_workflows/<workflow_id>.json`.
- Consumes later: browser orchestration CLI and hotspot/literary push adapters.

- [ ] **Step 1: Write failing state-transition tests**

```python
def test_workflow_requires_prompt_confirmation_before_response(tmp_path):
    workflow = create_workflow(
        kind="hotspot",
        topic="测试热点",
        prompt="写一篇热点深评",
        research_urls=("https://a.example/x",),
        root=tmp_path,
    )
    with pytest.raises(WorkflowTransitionError, match="prompt_confirmed"):
        record_response(workflow.workflow_id, "标题\n\n正文", root=tmp_path)


def test_workflow_requires_second_confirmation_before_drafted(tmp_path):
    workflow = _response_received_workflow(tmp_path, kind="literary")
    stage_edited_article(workflow.workflow_id, tmp_path / "article.json", root=tmp_path)
    with pytest.raises(WorkflowTransitionError, match="push_confirmed"):
        mark_drafted(workflow.workflow_id, "media-id", root=tmp_path)


def test_confirmation_cannot_be_reused_by_another_workflow(tmp_path):
    first = create_workflow(kind="hotspot", topic="甲", prompt="甲提示", root=tmp_path)
    second = create_workflow(kind="hotspot", topic="乙", prompt="乙提示", root=tmp_path)
    confirm_prompt(first.workflow_id, root=tmp_path)
    assert load_workflow(second.workflow_id, root=tmp_path).status == WorkflowStatus.RESEARCHED
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_browser_workflow.py -q`

Expected: collection fails because `scripts.tools.wechat_mp_browser_workflow` does not exist.

- [ ] **Step 3: Implement the state model and atomic JSON persistence**

```python
class WorkflowStatus(StrEnum):
    RESEARCHED = "researched"
    PROMPT_CONFIRMED = "prompt_confirmed"
    RESPONSE_RECEIVED = "response_received"
    EDITED = "edited"
    PUSH_CONFIRMED = "push_confirmed"
    DRAFTED = "drafted"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class BrowserWritingWorkflow:
    workflow_id: str
    kind: Literal["hotspot", "literary"]
    topic: str
    prompt: str
    prompt_sha256: str
    conversation_id: str
    status: WorkflowStatus
    research_urls: tuple[str, ...] = ()
    raw_response: str = ""
    article_path: str = ""
    first_confirmation_at: str = ""
    second_confirmation_at: str = ""
    media_id: str = ""
    error_code: str = ""
```

Use a temporary sibling file plus `Path.replace()` for writes. Enforce the exact transition sequence from the design, reject unknown kinds, and compute `prompt_sha256` internally.

- [ ] **Step 4: Add ignored workflow output path**

Add `output/wechat_mp_browser_workflows/` to `.gitignore` without changing other ignore rules.

- [ ] **Step 5: Run the state tests and verify GREEN**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_browser_workflow.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit the state machine**

```bash
git add .gitignore scripts/tools/wechat_mp_browser_workflow.py tests/unit/test_wechat_mp_browser_workflow.py
git commit -m "功能：新增浏览器写稿状态门禁"
```

---

### Task 2: OpenCLI fixed-conversation browser adapter

**Files:**
- Create: `scripts/tools/wechat_mp_deepseek_browser.py`
- Test: `tests/unit/test_wechat_mp_deepseek_browser.py`

**Interfaces:**
- Consumes: an injected `OpenCliRunner.run(args: Sequence[str]) -> CommandResult`.
- Produces: `DeepSeekBrowserClient.validate_current_tab()`, `send_and_receive(prompt, timeout_seconds)`, `unbind()` and typed exceptions `DeepSeekLoginRequired`, `DeepSeekWrongConversation`, `DeepSeekBusy`, `DeepSeekResponseTimeout`, `DeepSeekSendFailed`.
- Constant: `FIXED_CONVERSATION_ID = "f0cc031d-233f-4648-807d-354275738e61"`.

- [ ] **Step 1: Write failing browser-state tests**

```python
def test_validate_current_tab_accepts_fixed_logged_in_conversation():
    runner = FakeRunner.for_page(
        url="https://chat.deepseek.com/a/chat/s/f0cc031d-233f-4648-807d-354275738e61",
        title="公众号爆文秘诀 - DeepSeek",
        textarea=True,
        login_form=False,
        generating=False,
    )
    state = DeepSeekBrowserClient(runner).validate_current_tab()
    assert state.conversation_id == FIXED_CONVERSATION_ID


def test_validate_current_tab_reports_login_instruction_when_logged_out():
    runner = FakeRunner.for_page(
        url="https://chat.deepseek.com/sign_in",
        textarea=False,
        login_form=True,
    )
    with pytest.raises(DeepSeekLoginRequired, match="请在 Chrome 登录 DeepSeek"):
        DeepSeekBrowserClient(runner).validate_current_tab()


def test_validate_current_tab_rejects_other_conversation():
    runner = FakeRunner.for_page(
        url="https://chat.deepseek.com/a/chat/s/other",
        textarea=True,
    )
    with pytest.raises(DeepSeekWrongConversation):
        DeepSeekBrowserClient(runner).validate_current_tab()
```

- [ ] **Step 2: Run the browser-state tests and verify RED**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_deepseek_browser.py -q`

Expected: import failure because the adapter does not exist.

- [ ] **Step 3: Implement bind validation without sensitive-data access**

The adapter may execute only these OpenCLI browser operations: `bind`, `state`, `eval` against DOM text/counts, `type`, `click`, `wait time`, and `unbind`. The validation JavaScript returns only:

```json
{
  "url": "location.href",
  "title": "document.title",
  "has_textarea": true,
  "has_login_form": false,
  "is_generating": false,
  "assistant_count": 12
}
```

Do not evaluate `document.cookie`, `localStorage`, `sessionStorage`, IndexedDB, request headers, or service-worker caches.

- [ ] **Step 4: Write failing new-response extraction tests**

```python
def test_send_and_receive_returns_only_new_assistant_message():
    runner = FakeRunner.with_message_sequence(
        before=[("user", "旧问题"), ("assistant", "旧长文")],
        after_send=[
            ("user", "新提示词"),
            ("assistant", "新标题\n\n新正文"),
        ],
    )
    result = DeepSeekBrowserClient(runner).send_and_receive("新提示词", 30)
    assert result.text == "新标题\n\n新正文"
    assert result.assistant_index == 2


def test_send_and_receive_rejects_unpersisted_prompt():
    runner = FakeRunner.with_message_sequence(
        before=[("assistant", "旧长文")],
        after_send=[("assistant", "旧长文")],
    )
    with pytest.raises(DeepSeekSendFailed):
        DeepSeekBrowserClient(runner).send_and_receive("新提示词", 30)
```

- [ ] **Step 5: Run the extraction tests and verify RED**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_deepseek_browser.py -q`

Expected: failures because `send_and_receive()` has no message-boundary implementation.

- [ ] **Step 6: Implement native send, polling, and exact new-reply extraction**

Capture message-role/text snapshots before sending. Use OpenCLI `type <textarea-ref> <prompt>` followed by `click <enabled-send-ref>`. Poll until generating is false and the assistant count increases. Verify the new user message hash matches the submitted prompt, then return only the assistant message added after the captured boundary. Always unbind in `finally`.

- [ ] **Step 7: Run browser adapter tests and verify GREEN**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_deepseek_browser.py -q`

Expected: all tests pass.

- [ ] **Step 8: Commit the browser adapter**

```bash
git add scripts/tools/wechat_mp_deepseek_browser.py tests/unit/test_wechat_mp_deepseek_browser.py
git commit -m "功能：接入固定 DeepSeek 浏览器会话"
```

---

### Task 3: Research prompt builder and first-confirmation CLI stages

**Files:**
- Create: `scripts/tools/wechat_mp_browser_prompt.py`
- Create: `scripts/tools/wechat_mp_browser_write.py`
- Test: `tests/unit/test_wechat_mp_browser_prompt.py`
- Test: `tests/unit/test_wechat_mp_browser_write_cli.py`

**Interfaces:**
- Produces: `build_browser_prompt(kind, topic, thesis, fact_lines, research_urls) -> str`.
- CLI subcommands: `prepare`, `confirm-prompt`, `write`, `show`.
- Test seam: `make_browser_client() -> DeepSeekBrowserClient`; production returns the real Task 2 client and tests replace only this factory.
- Consumes: Task 1 workflow state and Task 2 browser client.

- [ ] **Step 1: Write failing prompt tests for both kinds**

```python
def test_hotspot_prompt_contains_fact_pack_and_no_internal_secrets():
    prompt = build_browser_prompt(
        kind="hotspot",
        topic="具体公共事件",
        thesis="组织者没有动手，也可能承担安全保障责任。",
        fact_lines=("法院判决新人承担40%责任｜来源：光明网",),
        research_urls=(
            "https://m.gmw.cn/example",
            "https://www.thepaper.cn/example",
            "https://www.chinanews.com.cn/example",
        ),
    )
    assert "一句话钉子" in prompt
    assert "法院判决新人承担40%责任" in prompt
    assert "第一行标题" in prompt
    assert "cookie" not in prompt.lower()
    assert "token=" not in prompt.lower()


def test_literary_prompt_requires_scene_opening_and_verified_quotes():
    prompt = build_browser_prompt(
        kind="literary",
        topic="《典籍里的中国·史记》",
        thesis="司马迁最重要的选择不是忍辱，而是让写作目标压过个人评价。",
        fact_lines=("《史记》共130篇｜来源：中国国家博物馆",),
        research_urls=(
            "https://www.chnmuseum.cn/example",
            "https://tv.cctv.com/example",
            "https://www.nlc.cn/example",
        ),
    )
    assert "作品场面、原文细节或节目动作" in prompt
    assert "不得虚构观看经历" in prompt
    assert "直接引文" in prompt
```

- [ ] **Step 2: Run prompt tests and verify RED**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_browser_prompt.py -q`

Expected: import failure because the prompt module does not exist.

- [ ] **Step 3: Implement deterministic prompt construction**

Build prompts from explicit arguments only. Require at least three non-empty `research_urls`, at least one fact line, a thesis of at least 20 Chinese characters, and output format `第一行标题，空一行后输出纯段落正文，不附解释`. Reject prompts containing credential-shaped fields such as `cookie`, `DEEPSEEK_API_KEY`, `WECHAT_MP_SECRET`, `token=`, or local `.env` text.

- [ ] **Step 4: Write failing CLI gate tests**

```python
def test_write_refuses_unconfirmed_prompt(tmp_path, monkeypatch):
    workflow = create_workflow(kind="hotspot", topic="题目", prompt="提示词", root=tmp_path)
    calls = []
    monkeypatch.setattr(browser_cli, "make_browser_client", lambda: RecordingClient(calls))
    assert browser_cli.main(["write", workflow.workflow_id, "--root", str(tmp_path)]) == 2
    assert calls == []


def test_login_failure_marks_workflow_blocked_without_model_fallback(tmp_path, monkeypatch):
    workflow = _confirmed_workflow(tmp_path)
    monkeypatch.setattr(browser_cli, "make_browser_client", lambda: LoginRequiredClient())
    monkeypatch.setattr(browser_cli, "call_deepseek", fail_if_called, raising=False)
    monkeypatch.setattr(browser_cli, "call_wechat_mp_llm", fail_if_called, raising=False)
    assert browser_cli.main(["write", workflow.workflow_id, "--root", str(tmp_path)]) == 3
    assert load_workflow(workflow.workflow_id, root=tmp_path).status == WorkflowStatus.BLOCKED
```

- [ ] **Step 5: Run CLI tests and verify RED**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_browser_write_cli.py -q`

Expected: import failure because the CLI does not exist.

- [ ] **Step 6: Implement `prepare`, `confirm-prompt`, `write`, and `show`**

`prepare` writes `researched`; `confirm-prompt` writes the first timestamp; `write` requires `prompt_confirmed`, invokes only `DeepSeekBrowserClient`, records the raw response, and prints the login instruction on `DeepSeekLoginRequired`; `show` prints non-sensitive workflow status and response length.

- [ ] **Step 7: Run prompt and CLI tests and verify GREEN**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_browser_prompt.py tests/unit/test_wechat_mp_browser_write_cli.py -q`

Expected: all tests pass.

- [ ] **Step 8: Commit prompt and first-half orchestration**

```bash
git add scripts/tools/wechat_mp_browser_prompt.py scripts/tools/wechat_mp_browser_write.py tests/unit/test_wechat_mp_browser_prompt.py tests/unit/test_wechat_mp_browser_write_cli.py
git commit -m "功能：新增 DeepSeek 写稿确认与提取入口"
```

---

### Task 4: Independent `literary` article model, renderer, cache, and slot

**Files:**
- Create: `scripts/tools/wechat_mp_literary.py`
- Create: `scripts/tools/wechat_mp_literary_cache.py`
- Modify: `scripts/tools/wechat_mp_content.py`
- Modify: `scripts/tools/wechat_mp_draft.py`
- Modify: `scripts/tools/wechat_mp_draft_slots.py`
- Modify: `scripts/tools/wechat_mp_product.py`
- Modify: `scripts/tools/wechat_mp_monetization.py`
- Modify: `scripts/tools/wechat_mp_seo.py`
- Test: `tests/unit/test_wechat_mp_literary.py`
- Test: `tests/unit/test_wechat_mp_literary_cli.py`
- Test: `tests/unit/test_wechat_mp_draft_slots.py`

**Interfaces:**
- Produces: `LiteraryDraft`, `load_literary_draft(path)`, `validate_literary_draft()`, `build_literary_article(draft, upload_figures=True)`.
- Slot: `literary`.
- Cache: `data/wechat_mp_literary_body_cache/<topic_slug>.json`.
- Consumes later: workflow `stage` and `push` commands.

- [ ] **Step 1: Write failing literary model and slot tests**

```python
def test_literary_is_manual_kind_with_independent_slot():
    assert "literary" in content.DRAFT_KINDS
    assert "literary" not in content.DAILY_DRAFT_KINDS
    assert draft_cli._resolve_draft_slot_key("literary", None) == "literary"
    assert "literary" in draft_slots.managed_slot_keys()


def test_literary_does_not_share_tv_review_slot(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(draft_slots, "get_slot_media_id", lambda key: {"literary": "lit-old", "tv_review": "tv-old"}.get(key))
    monkeypatch.setattr(draft_slots, "draft_delete", lambda media_id: calls.append(media_id))
    monkeypatch.setattr(draft_slots, "draft_add", lambda articles: ("lit-new", None))
    monkeypatch.setattr(draft_slots, "set_slot_media_id", lambda *args, **kwargs: None)
    draft_slots.upsert_draft_article("literary", _article(), thumb_media_id="thumb", slot_key="literary")
    assert calls == ["lit-old"]
```

- [ ] **Step 2: Run slot tests and verify RED**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_literary.py tests/unit/test_wechat_mp_literary_cli.py tests/unit/test_wechat_mp_draft_slots.py -q`

Expected: failures because `literary` is unknown and its model does not exist.

- [ ] **Step 3: Implement the literary draft schema and validation**

```python
@dataclass(frozen=True)
class LiteraryDraft:
    title: str
    digest: str
    body: str
    topic: str
    research_urls: tuple[str, ...]
    original_thesis: str
    slot_key: str = "literary"
    topic_slug: str = ""
```

Require a non-empty title/digest/body/topic, body length 1400–3200 Chinese characters, at least three distinct source domains, thesis length at least 20 characters, and `slot_key == "literary"`.

- [ ] **Step 4: Implement literary rendering by reusing proven long-form primitives**

Add `build_literary_article()` to `wechat_mp_content.py`. Reuse `normalize_tv_review_body`, rich highlight rendering, public-source figure injection, follow hook, `attach_publish_hints`, and `_article_shell`, but pass `kind="literary"`. Do not call the TV title picker or write the TV body cache.

- [ ] **Step 5: Register `literary` across kind routing without scheduling it**

Add it to `DRAFT_KINDS`, `_resolve_cover_kind()` using `tv_review` cover infrastructure, `_resolve_draft_slot_key()`, managed title hints, product payload allowlists, non-financial disclaimer routing, SEO topic suggestions, and follow-hook handling. Do not add it to `DAILY_DRAFT_KINDS` or any schedule batch.

- [ ] **Step 6: Implement the independent literary cache**

Store `title`, `digest`, `body_core`, `topic`, `topic_slug`, `research_urls`, `original_thesis`, and `updated_at` under `data/wechat_mp_literary_body_cache/`. Do not read or write `wechat_mp_tv_body_cache`.

- [ ] **Step 7: Run literary and slot tests and verify GREEN**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_literary.py tests/unit/test_wechat_mp_literary_cli.py tests/unit/test_wechat_mp_draft_slots.py -q`

Expected: all tests pass.

- [ ] **Step 8: Commit the literary kind**

```bash
git add scripts/tools/wechat_mp_literary.py scripts/tools/wechat_mp_literary_cache.py scripts/tools/wechat_mp_content.py scripts/tools/wechat_mp_draft.py scripts/tools/wechat_mp_draft_slots.py scripts/tools/wechat_mp_product.py scripts/tools/wechat_mp_monetization.py scripts/tools/wechat_mp_seo.py tests/unit/test_wechat_mp_literary.py tests/unit/test_wechat_mp_literary_cli.py tests/unit/test_wechat_mp_draft_slots.py
git commit -m "功能：新增文学典籍独立草稿槽位"
```

---

### Task 5: Agent editing handoff, second confirmation, and guarded push

**Files:**
- Modify: `scripts/tools/wechat_mp_browser_write.py`
- Modify: `scripts/tools/wechat_mp_draft.py`
- Modify: `scripts/tools/wechat_mp_codex_client.py`
- Test: `tests/unit/test_wechat_mp_browser_push.py`
- Test: `tests/unit/test_wechat_mp_codex_client.py`

**Interfaces:**
- Adds CLI subcommands: `stage`, `confirm-push`, `push`.
- `stage <workflow_id> --article <json>` validates final edited JSON and records its path.
- `push <workflow_id>` requires `push_confirmed`, uses the existing hotspot builder for `hotspot` and `build_literary_article()` for `literary`, then calls `upsert_draft_article()` exactly once.

- [ ] **Step 1: Write failing second-gate and no-fallback tests**

```python
def test_push_refuses_edited_workflow_without_second_confirmation(tmp_path, monkeypatch):
    workflow = _edited_workflow(tmp_path, kind="hotspot")
    calls = []
    monkeypatch.setattr(browser_cli, "upsert_draft_article", lambda *a, **k: calls.append((a, k)))
    assert browser_cli.main(["push", workflow.workflow_id, "--root", str(tmp_path)]) == 2
    assert calls == []


def test_deepseek_failure_never_calls_codex_or_wechat(tmp_path, monkeypatch):
    workflow = _prompt_confirmed_workflow(tmp_path)
    monkeypatch.setattr(browser_cli, "make_browser_client", lambda: TimeoutClient())
    codex_calls, wechat_calls = [], []
    monkeypatch.setattr(browser_cli, "call_wechat_mp_llm", lambda *a, **k: codex_calls.append(1), raising=False)
    monkeypatch.setattr(browser_cli, "upsert_draft_article", lambda *a, **k: wechat_calls.append(1))
    assert browser_cli.main(["write", workflow.workflow_id, "--root", str(tmp_path)]) == 3
    assert codex_calls == []
    assert wechat_calls == []
```

- [ ] **Step 2: Run guarded-push tests and verify RED**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_browser_push.py -q`

Expected: failures because `stage`, `confirm-push`, and `push` do not exist.

- [ ] **Step 3: Implement final-article staging and the second confirmation report**

For hotspot, load with the existing hotspot draft schema and run originality validation. For literary, load with `load_literary_draft()`. Print title, digest, body character count, thesis, distinct source-domain count, figure count/source types from manifests, and rich-control scan. Reject bare `[[hl:`, `[[fig:`, or `[[cta:` in final rendered HTML.

- [ ] **Step 4: Implement guarded push with explicit browser provenance**

Add a generation event provider `deepseek_browser` with mode `opencli_bound_tab`. Permit it only when the workflow JSON is `push_confirmed`, the prompt hash matches, and `conversation_id` matches the fixed ID. Do not weaken the existing Codex-only assertions for ordinary scheduled or manual Codex routes.

- [ ] **Step 5: Route each kind to its existing safe renderer and slot**

For `hotspot`, build with the staged hotspot draft and its explicit existing hotspot slot. For `literary`, build with `build_literary_article()` and slot `literary`. Upload verified cover/body images, run public compliance and promotion safety checks, then call `upsert_draft_article()`. On success call `mark_drafted(workflow_id, media_id)`.

- [ ] **Step 6: Run guarded-push and provenance tests and verify GREEN**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_browser_push.py tests/unit/test_wechat_mp_codex_client.py -q`

Expected: all tests pass and ordinary Codex assertions remain unchanged.

- [ ] **Step 7: Commit the second gate and push adapter**

```bash
git add scripts/tools/wechat_mp_browser_write.py scripts/tools/wechat_mp_draft.py scripts/tools/wechat_mp_codex_client.py tests/unit/test_wechat_mp_browser_push.py tests/unit/test_wechat_mp_codex_client.py
git commit -m "功能：接入浏览器写稿复核与推草稿门禁"
```

---

### Task 6: Documentation, focused regression suite, and live acceptance

**Files:**
- Modify: `../.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `../.cursor/skills/wechat-mp-drafts/INDEX.md`
- Modify: `../.cursor/skills/wechat-mp-drafts/operations-sop.md`
- Modify: `../.cursor/skills/wechat-mp-writing/deepseek-writer-sop.md`
- Modify: `docs/DEEPSEEK_USAGE.md`
- Modify: `docs/WECHAT_MP_SCHEDULING.md`
- Test: `tests/unit/test_wechat_mp_browser_workflow_e2e.py`

**Interfaces:**
- Documents the six commands: `prepare`, `confirm-prompt`, `write`, `stage`, `confirm-push`, `push`.
- Confirms `literary` is manual-only and `hotspot` schedules remain Codex-only unless a user starts this browser workflow.

- [ ] **Step 1: Write a failing orchestration test covering both kinds**

```python
@pytest.mark.parametrize("kind,expected_slot", [("hotspot", "hotspot_afternoon"), ("literary", "literary")])
def test_complete_browser_workflow_uses_two_gates_and_expected_slot(
    kind, expected_slot, tmp_path, fake_browser, fake_wechat
):
    workflow = prepare_confirm_write_stage_confirm(kind, tmp_path, fake_browser)
    result = push_workflow(workflow.workflow_id, root=tmp_path)
    assert result.media_id == "new-media-id"
    assert fake_wechat.slot_keys == [expected_slot]
    assert load_workflow(workflow.workflow_id, root=tmp_path).status == WorkflowStatus.DRAFTED
```

- [ ] **Step 2: Run the orchestration test and verify RED**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_browser_workflow_e2e.py -q`

Expected: failure until all routing and reporting pieces are connected.

- [ ] **Step 3: Update the operational documentation**

Document the approved B flow: Agent shows topic and prompt, user confirms, OpenCLI writes through the fixed current tab, Agent edits and shows the final report, user confirms again, then Agent pushes. Add the exact login instruction and state that a login failure does not trigger model fallback. Remove any statement implying DeepSeek browser writing is only a manual copy/paste workflow for literary content.

- [ ] **Step 4: Run all focused tests and verify GREEN**

Run:

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/unit/test_wechat_mp_browser_workflow.py \
  tests/unit/test_wechat_mp_deepseek_browser.py \
  tests/unit/test_wechat_mp_browser_prompt.py \
  tests/unit/test_wechat_mp_browser_write_cli.py \
  tests/unit/test_wechat_mp_literary.py \
  tests/unit/test_wechat_mp_literary_cli.py \
  tests/unit/test_wechat_mp_browser_push.py \
  tests/unit/test_wechat_mp_browser_workflow_e2e.py \
  tests/unit/test_wechat_mp_draft_slots.py \
  tests/unit/test_wechat_mp_codex_client.py -q
```

Expected: all tests pass with zero failures.

- [ ] **Step 5: Run existing WeChat regression tests**

Run: `PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_wechat_mp_*.py -q`

Expected: zero failures. If unrelated pre-existing failures exist, record their exact names and verify every test changed by this plan separately.

- [ ] **Step 6: Perform live browser acceptance without pushing**

With the fixed DeepSeek conversation as the current logged-in Chrome tab, run one `hotspot` workflow through `response_received` and one `literary` workflow through `response_received`. Confirm each extracted response is new, the tab remains open, and OpenCLI is unbound. Do not run either `push` during this step.

- [ ] **Step 7: Perform user-approved live slot acceptance**

After the user reviews both edited articles and explicitly confirms each push, push one test hotspot to an explicitly selected hotspot slot and one literary article to `literary`. Verify the slot ledger contains distinct media IDs and `tv_review` is unchanged.

- [ ] **Step 8: Commit docs and final tests**

```bash
git add ../.cursor/skills/wechat-mp-drafts/SKILL.md ../.cursor/skills/wechat-mp-drafts/INDEX.md ../.cursor/skills/wechat-mp-drafts/operations-sop.md ../.cursor/skills/wechat-mp-writing/deepseek-writer-sop.md docs/DEEPSEEK_USAGE.md docs/WECHAT_MP_SCHEDULING.md tests/unit/test_wechat_mp_browser_workflow_e2e.py
git commit -m "文档：固化 DeepSeek 浏览器写稿发布流程"
```
