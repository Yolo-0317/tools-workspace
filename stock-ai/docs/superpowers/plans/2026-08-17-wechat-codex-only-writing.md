# 公众号 Codex 唯一写稿后端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让「牛马也智能」公众号的所有 AI 成稿、扩写和改稿只调用本机 Codex CLI，失败时停止推稿，同时不改变东财 DeepSeek 流程。

**Architecture:** 新建一个只负责 `codex exec` 的公众号客户端，并让现有 `call_wechat_mp_llm` 成为该客户端的兼容门面。使用进程内生成轨迹记录 `provider=codex`，公众号草稿 CLI 在每篇构建前重置轨迹、在微信写入前校验；人工 `--codex-draft` 也登记为 Codex 来源。要闻点评移除直接 DeepSeek 调用，全部汇入相同入口。

**Tech Stack:** Python 3.11、`subprocess`、`tempfile`、`contextvars`、pytest、现有 `wechat_mp_draft` CLI 与文章生成器。

## Global Constraints

- 公众号 AI 写稿与 AI 改稿不得调用 DeepSeek API、Cursor Agent 或 Composer。
- Codex CLI 不存在、未登录、超时、返回空值或返回非法结构时，必须在微信写入前停止，不设置备用模型。
- 东财选股、投资分析和 `SOP_LLM_BACKEND=deepseek` 保持不变。
- 现有 `--codex-draft` JSON 格式、公众号草稿槽位、选题、图片、原创度、完读率和短剧规则保持兼容。
- 不把 Cookie、Token、`wxTicket`、`.env` 内容、完整提示或完整正文写入诊断记录。
- 用户可见内容、UI 与汇报禁止 emoji；本功能不顺带清理工作区既有修改。

---

## File Structure

- Create `scripts/tools/wechat_mp_codex_client.py`: Codex CLI 调用、参数校验、敏感信息门禁、生成轨迹。
- Create `tests/unit/test_wechat_mp_codex_client.py`: 客户端命令、失败关闭、轨迹与敏感信息测试。
- Modify `scripts/tools/deepseek_client.py`: 保留通用和 SOP DeepSeek 能力；将公众号兼容入口改接 Codex 客户端。
- Modify `tests/unit/test_deepseek_client_backend.py`: 将旧 Cursor/Composer 断言改为 Codex，保留 SOP DeepSeek 断言。
- Modify `scripts/tools/wechat_mp_news_article.py`: 要闻 AI 点评改用公众号统一入口。
- Modify `tests/unit/test_wechat_mp_news_article.py`: 断言要闻不读取 DeepSeek 后端变量。
- Modify `scripts/tools/wechat_mp_draft.py`: 每篇建立生成作用域，登记人工 Codex 草稿，并在 `upsert_draft_article` 前验证来源。
- Create `tests/unit/test_wechat_mp_codex_provenance.py`: 推送前来源门禁和多篇轨迹隔离测试。
- Modify `stock-ai/.env.example`, `docs/DEEPSEEK_USAGE.md`, `.cursor/skills/wechat-mp-drafts/INDEX.md`, `.cursor/skills/wechat-mp-drafts/SKILL.md`, `.cursor/skills/wechat-mp-drafts/operations-sop.md`, `.cursor/skills/wechat-mp-drafts/reference.md`: 更新配置与运维说明。

---

### Task 1: Codex CLI client and generation trace

**Files:**
- Create: `stock-ai/scripts/tools/wechat_mp_codex_client.py`
- Create: `stock-ai/tests/unit/test_wechat_mp_codex_client.py`

**Interfaces:**
- Consumes: `messages_to_prompt(messages: list[dict[str, str]]) -> str` from `cursor_agent_client.py` only as a pure formatter; it must not call Cursor.
- Produces: `call_wechat_mp_codex(messages, *, model=None, max_retries=None, timeout_seconds=None, output_schema=None) -> str`.
- Produces: `codex_available() -> bool`, `wechat_mp_codex_model() -> str | None`, `generation_scope(kind: str)`, `record_interactive_codex_draft(kind: str) -> None`, `generation_events() -> Sequence[CodexGenerationEvent]`, and `assert_codex_only_generation(*, allow_empty: bool = True) -> None`.

- [ ] **Step 1: Write failing client tests**

```python
def test_call_wechat_mp_codex_uses_argv_without_shell(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setenv("WECHAT_MP_CODEX_COMMAND", "/opt/codex/bin/codex")
    monkeypatch.setenv("WECHAT_MP_CODEX_WORKSPACE", str(tmp_path))
    monkeypatch.setattr(client.subprocess, "run", fake_successful_codex_run(seen, "成稿"))
    assert client.call_wechat_mp_codex([{"role": "user", "content": "写稿"}]) == "成稿"
    assert seen["shell"] is False
    assert seen["argv"][:3] == ["/opt/codex/bin/codex", "exec", "--ephemeral"]
    assert "--sandbox" in seen["argv"] and "read-only" in seen["argv"]

def test_codex_failure_has_no_fallback(monkeypatch):
    monkeypatch.setattr(client.subprocess, "run", fake_failed_codex_run(1, "not logged in"))
    with pytest.raises(RuntimeError, match="Codex"):
        client.call_wechat_mp_codex([{"role": "user", "content": "写稿"}], max_retries=1)

def test_sensitive_prompt_is_rejected_before_subprocess(monkeypatch):
    run = Mock()
    monkeypatch.setattr(client.subprocess, "run", run)
    with pytest.raises(ValueError, match="敏感"):
        client.call_wechat_mp_codex([{"role": "user", "content": "wxTicket=secret-value"}])
    run.assert_not_called()

def test_generation_scope_records_codex_provider(monkeypatch):
    monkeypatch.setattr(client.subprocess, "run", fake_successful_codex_run({}, "成稿"))
    with client.generation_scope("tv_review"):
        client.call_wechat_mp_codex([{"role": "user", "content": "写稿"}])
        assert [event.provider for event in client.generation_events()] == ["codex"]
        client.assert_codex_only_generation(allow_empty=False)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_wechat_mp_codex_client.py`

Expected: FAIL because `wechat_mp_codex_client` does not exist.

- [ ] **Step 3: Implement the minimal Codex client**

```python
@dataclass(frozen=True)
class CodexGenerationEvent:
    provider: str
    mode: Literal["codex_exec", "interactive_draft"]
    cli_version: str
    generated_at: str
    kind: str

def _command() -> str:
    configured = os.getenv("WECHAT_MP_CODEX_COMMAND", "").strip()
    resolved = configured or shutil.which("codex") or ""
    if not resolved or not Path(resolved).is_file():
        raise RuntimeError("公众号写稿需要已安装并登录的 Codex CLI")
    return resolved

def call_wechat_mp_codex(messages, *, model=None, max_retries=None,
                         timeout_seconds=None, output_schema=None) -> str:
    prompt = messages_to_prompt(messages)
    _assert_prompt_safe(prompt)
    argv = [_command(), "exec", "--ephemeral", "--sandbox", "read-only",
            "--skip-git-repo-check", "-C", str(_workspace())]
    if model or wechat_mp_codex_model():
        argv.extend(["--model", model or wechat_mp_codex_model()])
    if output_schema:
        argv.extend(["--output-schema", str(output_schema)])
    with tempfile.TemporaryDirectory(prefix="wechat-codex-") as temp_dir:
        output = Path(temp_dir) / "last-message.txt"
        argv.extend(["--output-last-message", str(output), "-"])
        # Run with input=prompt, shell=False, capture_output=True and bounded timeout.
        # Retry only the same Codex command; never call another provider.
        result = subprocess.run(
            argv,
            input=prompt,
            text=True,
            shell=False,
            capture_output=True,
            timeout=timeout_seconds or _timeout_seconds(),
            check=False,
        )
        text = output.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError("Codex 返回空正文")
    _record_event(provider="codex", mode="codex_exec")
    return text
```

Use a `ContextVar[Sequence[CodexGenerationEvent]]` whose stored value is an immutable tuple, plus a second current-kind `ContextVar`. `generation_scope(kind)` must reset both tokens on exit so consecutive draft kinds cannot share provenance. `_assert_prompt_safe` must reject assignments for `cookie`, `wxTicket`, `slave_sid`, `data_ticket`, `token` with non-empty values and any literal `.env` file content marker. Diagnostic errors may include exit code and a bounded stderr tail but not the prompt.

- [ ] **Step 4: Run client tests and verify GREEN**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_wechat_mp_codex_client.py`

Expected: PASS.

- [ ] **Step 5: Commit the isolated client**

```bash
git add stock-ai/scripts/tools/wechat_mp_codex_client.py stock-ai/tests/unit/test_wechat_mp_codex_client.py
git commit -m "feat(stock-ai): add codex wechat writer client"
```

### Task 2: Rewire the公众号 compatibility facade

**Files:**
- Modify: `stock-ai/scripts/tools/deepseek_client.py:20-75`
- Modify: `stock-ai/tests/unit/test_deepseek_client_backend.py:15-60`

**Interfaces:**
- Consumes: `call_wechat_mp_codex`, `codex_available`, `wechat_mp_codex_model` from Task 1.
- Produces: existing `call_wechat_mp_llm(messages, keyword arguments) -> str`, `is_wechat_mp_llm_configured() -> bool`, `wechat_mp_llm_backend() -> Literal["codex"]`, and `wechat_mp_llm_model() -> str | None` with unchanged import locations for article modules.

- [ ] **Step 1: Replace old Cursor expectations with failing Codex tests**

```python
def test_wechat_mp_backend_always_codex(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "deepseek")
    assert deepseek_client.wechat_mp_llm_backend() == "codex"

def test_call_wechat_mp_llm_uses_codex_client(monkeypatch):
    seen = {}
    monkeypatch.setattr(deepseek_client, "call_wechat_mp_codex",
                        lambda messages, **kwargs: seen.update(kwargs) or "正文")
    assert deepseek_client.call_wechat_mp_llm([{"role": "user", "content": "hi"}]) == "正文"
    assert "backend" not in seen

def test_sop_backend_defaults_deepseek(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "codex")
    assert deepseek_client.sop_llm_backend() == "deepseek"
```

- [ ] **Step 2: Run facade tests and verify RED**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_deepseek_client_backend.py`

Expected: FAIL because the facade still returns `cursor` and calls `call_deepseek`.

- [ ] **Step 3: Delegate only公众号 functions to Codex**

```python
def wechat_mp_llm_backend() -> Literal["codex"]:
    return "codex"

def wechat_mp_llm_model() -> str | None:
    return wechat_mp_codex_model()

def is_wechat_mp_llm_configured() -> bool:
    return codex_available()

def call_wechat_mp_llm(messages, *, max_retries=None, **kwargs):
    timeout = kwargs.pop("timeout", None)
    if kwargs.pop("backend", None) not in (None, "codex"):
        raise ValueError("公众号写稿后端只允许 codex")
    if kwargs:
        kwargs.pop("temperature", None)
        kwargs.pop("max_tokens", None)
    return call_wechat_mp_codex(
        messages,
        model=wechat_mp_llm_model(),
        max_retries=max_retries,
        timeout_seconds=_read_timeout(timeout),
    )
```

Do not change `call_deepseek`, `sop_llm_backend`, `is_sop_llm_configured`, `sop_review_single.py`, or `sop_review_top5_concurrent.py`.

- [ ] **Step 4: Run facade and existing article tests**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_deepseek_client_backend.py tests/unit/test_wechat_mp_hot_business_article.py tests/unit/test_wechat_mp_silver_article.py`

Expected: PASS.

- [ ] **Step 5: Commit the facade migration**

```bash
git add stock-ai/scripts/tools/deepseek_client.py stock-ai/tests/unit/test_deepseek_client_backend.py
git commit -m "refactor(stock-ai): route wechat writing to codex"
```

### Task 3: Remove the news DeepSeek bypass

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_news_article.py:55-70,800-815`
- Modify: `stock-ai/tests/unit/test_wechat_mp_news_article.py:60-75`

**Interfaces:**
- Consumes: `call_wechat_mp_llm` and `is_wechat_mp_llm_configured` from Task 2.
- Produces: `news_ai_llm_backend() -> Literal["codex"]` retained for diagnostics only; enriched news parsing and output format remain unchanged.

- [ ] **Step 1: Write failing news routing tests**

```python
def test_news_ai_backend_is_codex_even_when_legacy_env_requests_deepseek(monkeypatch):
    monkeypatch.setenv("WECHAT_MP_NEWS_AI_BACKEND", "deepseek")
    assert news_ai_llm_backend() == "codex"

def test_enriched_news_uses_wechat_llm(monkeypatch, sample_items):
    called = {}
    monkeypatch.setattr(news_mod, "call_wechat_mp_llm",
                        lambda messages, **kwargs: called.update(kwargs) or valid_blocks(sample_items))
    news_mod._generate_enriched_blocks(sample_items)
    assert "backend" not in called
```

- [ ] **Step 2: Run the news tests and verify RED**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_wechat_mp_news_article.py`

Expected: FAIL because the module still selects DeepSeek and calls `call_deepseek`.

- [ ] **Step 3: Replace the bypass**

Import `call_wechat_mp_llm` and `is_wechat_mp_llm_configured`. Make `news_ai_llm_backend()` return the literal `"codex"`, make `is_news_ai_llm_configured()` delegate to `is_wechat_mp_llm_configured()`, and replace the enriched-block direct DeepSeek call with `call_wechat_mp_llm(messages, max_tokens=6000)`.

- [ ] **Step 4: Run news tests and a static bypass scan**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_wechat_mp_news_article.py`

Run: `cd stock-ai && rg -n "call_deepseek|call_cursor_agent|WECHAT_MP_NEWS_AI_BACKEND" scripts/tools/wechat_mp_*article.py scripts/tools/wechat_mp_news_article.py`

Expected: tests PASS; scan shows no direct non-Codex writer call in公众号 article modules.

- [ ] **Step 5: Commit news migration**

```bash
git add stock-ai/scripts/tools/wechat_mp_news_article.py stock-ai/tests/unit/test_wechat_mp_news_article.py
git commit -m "fix(stock-ai): route wechat news comments to codex"
```

### Task 4: Enforce provenance before WeChat draft writes

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_draft.py:310-440,540-670`
- Create: `stock-ai/tests/unit/test_wechat_mp_codex_provenance.py`

**Interfaces:**
- Consumes: `generation_scope`, `record_interactive_codex_draft`, `generation_events`, `assert_codex_only_generation` from Task 1.
- Produces: `_build_with_codex_provenance(kind: str, *, codex_draft, **kwargs) -> tuple[dict[str, object], Sequence[CodexGenerationEvent]]` and `_assert_article_provenance(events, *, codex_draft_supplied: bool) -> None`.

- [ ] **Step 1: Write failing provenance tests**

```python
def test_codex_draft_is_recorded_as_interactive(monkeypatch, sample_codex_draft):
    monkeypatch.setattr(draft_cli, "_build_for_kind", lambda *a, **k: {"title": "t"})
    article, events = draft_cli._build_with_codex_provenance(
        "silver", codex_draft=sample_codex_draft, edition=None,
        market_title=None, variant=None, topic_hint="", silver_lane=None,
        upload_figures=False,
    )
    assert article["title"] == "t"
    assert [(e.provider, e.mode, e.kind) for e in events] == [
        ("codex", "interactive_draft", "silver")
    ]

def test_non_codex_event_blocks_upsert():
    events = (CodexGenerationEvent(
        provider="deepseek",
        mode="codex_exec",
        cli_version="codex-cli test",
        generated_at="2026-08-17T00:00:00+08:00",
        kind="silver",
    ),)
    with pytest.raises(RuntimeError, match="只允许 Codex"):
        draft_cli._assert_article_provenance(events, codex_draft_supplied=False)

def test_generation_events_do_not_leak_between_kinds(monkeypatch):
    kwargs = dict(edition=None, market_title=None, variant=None, topic_hint="",
                  silver_lane=None, upload_figures=False)
    _, first = draft_cli._build_with_codex_provenance(
        "market", codex_draft=None, **kwargs
    )
    _, second = draft_cli._build_with_codex_provenance(
        "sector", codex_draft=None, **kwargs
    )
    assert all(event.kind == "market" for event in first)
    assert all(event.kind == "sector" for event in second)
```

Use complete event fields in the actual test: `cli_version="codex-cli test"` and `generated_at="2026-08-17T00:00:00+08:00"`.

- [ ] **Step 2: Run provenance tests and verify RED**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_wechat_mp_codex_provenance.py`

Expected: FAIL because the draft helpers do not exist.

- [ ] **Step 3: Wrap each article build and gate the upsert**

```python
def _build_with_codex_provenance(kind, *, codex_draft, **kwargs):
    with generation_scope(kind):
        if codex_draft is not None:
            record_interactive_codex_draft(kind)
        article = _build_for_kind(kind, codex_draft=codex_draft, **kwargs)
        events = generation_events()
        assert_codex_only_generation(allow_empty=codex_draft is None)
        return article, events

def _assert_article_provenance(events, *, codex_draft_supplied):
    if codex_draft_supplied and not events:
        raise RuntimeError("Codex 草稿缺少生成来源")
    if any(event.provider != "codex" for event in events):
        raise RuntimeError("公众号 AI 写稿只允许 Codex")
```

Use `_build_with_codex_provenance` in both dry-run and formal loops. In the formal loop call `_assert_article_provenance(events, codex_draft_supplied=codex_draft is not None)` after compliance/quality checks and before cover upload or `upsert_draft_article`. Print only provider, mode, CLI version and kind; never print prompts or正文。

- [ ] **Step 4: Run provenance, CLI and long-form tests**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_wechat_mp_codex_provenance.py tests/unit/test_wechat_mp_codex_hotspot.py tests/unit/test_wechat_mp_hot_business_cli.py tests/unit/test_wechat_mp_silver_cli.py tests/unit/test_wechat_mp_short_drama_feature_cli.py`

Expected: PASS.

- [ ] **Step 5: Commit the provenance gate**

```bash
git add stock-ai/scripts/tools/wechat_mp_draft.py stock-ai/tests/unit/test_wechat_mp_codex_provenance.py
git commit -m "feat(stock-ai): gate wechat drafts on codex provenance"
```

### Task 5: Update configuration and operating documentation

**Files:**
- Modify: `stock-ai/.env.example:25-45,190-205`
- Modify: `stock-ai/docs/DEEPSEEK_USAGE.md`
- Modify: `.cursor/skills/wechat-mp-drafts/INDEX.md`
- Modify: `.cursor/skills/wechat-mp-drafts/SKILL.md`
- Modify: `.cursor/skills/wechat-mp-drafts/operations-sop.md`
- Modify: `.cursor/skills/wechat-mp-drafts/reference.md`

**Interfaces:**
- Consumes: exact environment variables implemented in Task 1.
- Produces: one consistent operator contract:公众号 Codex-only, no fallback; Eastmoney SOP DeepSeek unchanged.

- [ ] **Step 1: Add a failing documentation consistency test**

Add to `stock-ai/tests/unit/test_deepseek_client_backend.py`:

```python
def test_wechat_example_config_names_codex_only():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "WECHAT_MP_CODEX_TIMEOUT_SECONDS=" in text
    assert "WECHAT_MP_CODEX_MAX_RETRIES=" in text
    assert "WECHAT_MP_NEWS_AI_BACKEND=deepseek" not in text
```

- [ ] **Step 2: Run the documentation test and verify RED**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_deepseek_client_backend.py::test_wechat_example_config_names_codex_only`

Expected: FAIL because the example still documents the DeepSeek news backend.

- [ ] **Step 3: Update exact configuration guidance**

Document these variables and defaults:

```dotenv
# 公众号 AI 写稿只调用 Codex CLI；失败时不回退 DeepSeek 或 Composer
# WECHAT_MP_CODEX_COMMAND=/Applications/ChatGPT.app/Contents/Resources/codex
# WECHAT_MP_CODEX_MODEL=
WECHAT_MP_CODEX_TIMEOUT_SECONDS=420
WECHAT_MP_CODEX_MAX_RETRIES=1
```

Remove公众号 instructions that say `LLM_BACKEND=cursor`, `WECHAT_MP_NEWS_AI_BACKEND=deepseek`, `agent login`, or Composer fallback. Keep `SOP_LLM_BACKEND=deepseek` and explain it belongs only to Eastmoney review. Document `codex login` or the signed-in Codex desktop CLI as the readiness check.

- [ ] **Step 4: Run doc test and stale-reference scan**

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_deepseek_client_backend.py`

Run: `rg -n "公众号.*(DeepSeek|Composer|LLM_BACKEND=cursor)|WECHAT_MP_NEWS_AI_BACKEND=deepseek" stock-ai/.env.example stock-ai/docs/DEEPSEEK_USAGE.md .cursor/skills/wechat-mp-drafts`

Expected: tests PASS; any remaining matches describe removed legacy behavior rather than active instructions.

- [ ] **Step 5: Commit configuration and docs**

```bash
git add stock-ai/.env.example stock-ai/docs/DEEPSEEK_USAGE.md .cursor/skills/wechat-mp-drafts/INDEX.md .cursor/skills/wechat-mp-drafts/SKILL.md .cursor/skills/wechat-mp-drafts/operations-sop.md .cursor/skills/wechat-mp-drafts/reference.md stock-ai/tests/unit/test_deepseek_client_backend.py
git commit -m "docs(stock-ai): require codex for wechat writing"
```

### Task 6: Regression and dry-run verification

**Files:**
- Verify only; modify the smallest owning file if a regression exposes a defect.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: evidence that公众号 uses Codex and Eastmoney remains unchanged.

- [ ] **Step 1: Run the focused unit suite**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_wechat_mp_codex_client.py \
  tests/unit/test_deepseek_client_backend.py \
  tests/unit/test_wechat_mp_news_article.py \
  tests/unit/test_wechat_mp_codex_provenance.py \
  tests/unit/test_wechat_mp_codex_hotspot.py \
  tests/unit/test_wechat_mp_hot_business_article.py \
  tests/unit/test_wechat_mp_silver_article.py \
  tests/unit/test_wechat_mp_short_drama_feature_article.py
```

Expected: PASS.

- [ ] **Step 2: Run static provider checks**

Run:

```bash
cd stock-ai
rg -n "call_deepseek|call_cursor_agent" scripts/tools/wechat_mp_*.py
rg -n "SOP_LLM_BACKEND|backend=sop_llm_backend" scripts/analysis tests/unit/test_deepseek_client_backend.py
```

Expected: no direct non-Codex call in公众号 writers; SOP matches remain present.

- [ ] **Step 3: Verify the local Codex command without writing a draft**

Run: `cd stock-ai && /Applications/ChatGPT.app/Contents/Resources/codex --version`

Expected: exit 0 and print a `codex-cli` version.

Run: `cd stock-ai && PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_draft --kind market --dry-run`

Expected: exit 0, print a market preview and Codex provenance, and make no WeChat draft write call. If live data needed by the market builder is unavailable, use the smallest unit-level dry-run fixture instead of weakening the provenance gate.

- [ ] **Step 4: Check the final diff**

Run: `git diff --check`

Run: `git status --short`

Expected: no whitespace errors; only files from this plan plus pre-existing unrelated user changes are present. Do not stage or modify unrelated files.

- [ ] **Step 5: Commit any verification-only correction**

If Step 1-4 required a correction, stage only that correction and its regression test, then run:

```bash
git commit -m "fix(stock-ai): verify codex-only wechat writing"
```

If no correction was needed, do not create an empty commit.
