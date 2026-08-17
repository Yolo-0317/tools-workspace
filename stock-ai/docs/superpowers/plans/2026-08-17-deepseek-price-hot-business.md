# DeepSeek Price Hot Business Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the new longform completion rules, then research, write, illustrate, validate, and push one `hot_business` WeChat draft about DeepSeek's API price change.

**Architecture:** Keep the reusable behavior change separate from the one-off article. The writing skill and `hot_business` generation prompt own future completion-rate guidance; the existing Codex hot-business JSON contract, public-image pipeline, originality gate, short-drama selection, and WeChat slot upsert own this article's delivery.

**Tech Stack:** Python 3, pytest, existing WeChat MP draft pipeline, public web research, DeepSeek official documentation, WeChat Official Account draft API.

## Global Constraints

- User-visible copy and reports contain no emoji.
- Public title is `DeepSeek涨价，低价牌打完了吗？` and remains no more than 20 Chinese characters.
- Body is pure paragraphs with 2,300–2,700 non-whitespace Chinese characters and no numbered or report-style headings.
- Research uses at least three distinct source domains, including DeepSeek's official pricing or release documentation.
- Price comparisons use the same currency, model tier, token category, and billing basis; otherwise omit the percentage change.
- The first 80 characters state the event, change, and reader impact; the first 300 characters establish fact, open loop, and business question.
- Add one information increment or rhythm hook every 300–500 characters and at least two directly retellable details.
- Use one cover and three evenly distributed body images from traceable public sources before generating any original fallback.
- Quality requires score at least 75, AI flavor at most 20, no compliance failures, and traffic checklist 21/21.
- Push only the independent `hot_business` draft slot and never call the publish API.
- If a short-play card is inserted, readback must show exactly one short-play card, zero ordinary CPS cards, and a non-empty attribution ticket.
- Preserve all unrelated dirty-worktree changes and stage only files explicitly named by a task.

---

### Task 1: Persist the completion-rate writing rules

**Files:**
- Modify: `.cursor/skills/wechat-mp-writing/traffic-copy-craft.md`
- Modify: `stock-ai/scripts/tools/wechat_mp_hot_business_article.py`
- Modify: `stock-ai/tests/unit/test_wechat_mp_hot_business_article.py`

**Interfaces:**
- Consumes: `generate_hot_business_draft(topic_hint: str = "") -> CodexHotBusinessDraft`.
- Produces: a reusable hotspot/hot-business completion checklist and an LLM prompt that contains the same concrete constraints.

- [ ] **Step 1: Add a failing prompt-contract test**

Add a test that captures the user prompt passed to `call_wechat_mp_llm` and asserts the reusable completion constraints are present:

```python
def test_generate_hot_business_prompt_contains_completion_rules(monkeypatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(article_mod, "pick_hot_business_topic", lambda **_: _selected_topic())

    def fake_llm(messages, **_kwargs):
        captured.append(messages[-1]["content"])
        return json.dumps(_valid_payload(), ensure_ascii=False)

    monkeypatch.setattr(article_mod, "call_wechat_mp_llm", fake_llm)
    article_mod.generate_hot_business_draft()

    prompt = captured[0]
    assert "前 80 字" in prompt
    assert "前 300 字" in prompt
    assert "每 300 至 500 字" in prompt
    assert "至少两个可转述" in prompt
```

- [ ] **Step 2: Run the focused test and confirm red**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_wechat_mp_hot_business_article.py::test_generate_hot_business_prompt_contains_completion_rules
```

Expected: FAIL because the current prompt does not contain those four rules.

- [ ] **Step 3: Update the reusable writing rule**

Add a section named `热点长图文完读硬约束` to `traffic-copy-craft.md`, scoped by default to `hotspot` and `hot_business`, containing exactly these rules:

```text
首段 80 字内交代事件、变化和读者利益点。
前 300 字完成事实、悬念和文章核心问题。
每 300 至 500 字至少出现一个信息增量或节奏钩子。
至少两个可转述颗粒。
段落多数为 1 至 3 行，避免连续五段同句长。
正文配图均匀分布，承担滚动阅读换气。
文末只留一个具体互动问题，关注提示交给流水线。
```

- [ ] **Step 4: Put the same constraints into the hot-business prompt**

In `generate_hot_business_draft`, add a completion block after the seven-part structure and before the compliance prohibitions:

```python
"""完读约束：首段前 80 字交代事件、变化和读者利益点；前 300 字完成事实、悬念和核心商业问题；每 300 至 500 字至少加入一个新的信息增量或节奏钩子；全文至少提供两个读者可直接转述的数字、反差或判断；段落多数控制在 1 至 3 行；文末只留一个具体互动问题。"""
```

- [ ] **Step 5: Run focused and neighboring tests**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_wechat_mp_hot_business_article.py \
  tests/unit/test_wechat_mp_hot_business_cli.py \
  tests/unit/test_wechat_mp_codex_hot_business.py
```

Expected: all tests pass.

- [ ] **Step 6: Commit only the reusable rule change**

Before committing, verify the index is empty, then stage only the three files above:

```bash
git diff --cached --name-only
git add \
  .cursor/skills/wechat-mp-writing/traffic-copy-craft.md \
  stock-ai/scripts/tools/wechat_mp_hot_business_article.py \
  stock-ai/tests/unit/test_wechat_mp_hot_business_article.py
git diff --cached --name-only
git commit -m "feat: enforce longform completion rules"
```

### Task 2: Research and write the DeepSeek hot-business JSON

**Files:**
- Create: `stock-ai/output/hot_business_deepseek_price_20260817.json`

**Interfaces:**
- Consumes: DeepSeek current pricing, a comparable official historical price, and at least two independent reports.
- Produces: a valid `CodexHotBusinessDraft` with traceable `facts`, bounded `inferences`, and explicit `rejected_claims`.

- [ ] **Step 1: Capture the current official price table**

Record model name, cache-hit input, cache-miss input, output-token price, context size, and concurrency from DeepSeek's official pricing page. Save the direct official URL in `research_urls`.

- [ ] **Step 2: Find a comparable official historical price**

Use an official version or pricing announcement. Compare only identical currency, model tier, and token category. If an identical basis is unavailable, state both known prices separately and add the unsupported percentage claim to `rejected_claims`.

- [ ] **Step 3: Add two independent domains**

Use the following initial source set, replacing a URL only if the live page no longer supports the stated fact:

```text
https://api-docs.deepseek.com/zh-cn/quick_start/pricing
https://api-docs.deepseek.com/news/news260424/
https://www.scmp.com/tech/big-tech/article/3358868/after-triggering-price-war-deepseek-reverses-course-surcharge-peak-hour-api-use
https://finance.eastmoney.com/a/202607013790214619.html
https://www.workercn.cn/papers/grrb/2026/06/02/6/grrb202606026.pdf
```

The DeepSeek pages establish product and price facts; the South China Morning Post, Shenzhen Business Daily republication, and Workers' Daily provide independent market context. Do not use Reddit, repost aggregators, or social screenshots as support for key numbers.

- [ ] **Step 4: Write the JSON with `apply_patch`**

Create `output/hot_business_deepseek_price_20260817.json` with the exact title, digest, topic, thesis, business question, and slot key below, then write the complete 2,300–2,700-character body and source-mapped facts from the verified pages:

```text
title = DeepSeek涨价，低价牌打完了吗？
digest = 热点商业：DeepSeek调整API价格，真正变化的不只是每百万token的标价，而是模型公司开始按完成任务的工程价值重新定价。
topic = DeepSeek正式涨价
original_thesis = 低价是模型服务打开开发者市场的有效入口，但长期竞争会转向单位任务成本、稳定性与迁移成本，而不是单一token标价。
business_question = DeepSeek为什么在低价成为品牌标签后提高API价格，它正在从便宜token转向销售什么？
slot_key = hot_business
```

The initial fact map must include the official current V4 Flash and V4 Pro price rows, the official V4 context/output limits, and the independently reported peak-hour rule. Put unsupported claims about compute shortage, financing pressure, user loss, and profit change in `rejected_claims`; do not repeat their full wording in public copy.

- [ ] **Step 5: Validate the contract and completion shape**

Run a local Python check that calls `load_codex_hot_business_draft`, prints title length, non-whitespace body length, paragraph count, distinct source domains, and verifies no rejected claim appears in public copy.

Expected: title no more than 20 characters, body 2,300–2,700 characters, at least three domains, and no validation error.

### Task 3: Obtain public images and pass the dry run

**Files:**
- Create or update: `stock-ai/assets/wechat_mp/inline-discussion/DeepSeek正式涨价/figure_sources.json`
- Create or update: four verified image assets in the same directory.

**Interfaces:**
- Consumes: Task 2 JSON and its research URLs.
- Produces: one cover source plus three evenly distributed body images and a passing dry-run report.

- [ ] **Step 1: Run the initial dry run**

Run:

```bash
cd stock-ai
set -a; source .env; set +a
WECHAT_MP_HOTSPOT_TREND_ENRICH=0 PYTHONPATH=. .venv/bin/python \
  -m scripts.tools.wechat_mp_draft \
  --kind hot_business \
  --codex-draft output/hot_business_deepseek_price_20260817.json \
  --dry-run
```

Expected: either a passing preview or an explicit `codex-image-request.json` identifying missing slots.

- [ ] **Step 2: Curate four traceable public images**

Prefer DeepSeek official release pages and original reporting pages. Record `page_url`, `image_url`, `source_name`, `published_at`, `source_type`, `verified`, `caption`, and `page_title` for every retained file. Reject images whose original page cannot be verified or whose page forbids reuse.

- [ ] **Step 3: Generate only unresolved image slots**

If four verified public images cannot be obtained, read every slot and safety rule from `codex-image-request.json`, call ImageGen once per listed slot, and save only to the listed `output_path`. Do not replace already verified public images.

- [ ] **Step 4: Repeat the dry run until all gates pass**

Expected report:

```text
原创增量报告 [PASS]
阅读量清单 自动 21/21
质量分 >= 75
AI味 <= 20
无合规失败
```

Manually confirm the first 300 characters establish the event and business question, the body contains at least two retellable details, and the three body images are distributed rather than clustered at the start.

### Task 4: Push and verify the independent draft slot

**Files:**
- Modify through existing APIs only: ignored local `stock-ai/data/wechat_mp_draft_slots.json` and short-drama usage cache.

**Interfaces:**
- Consumes: the passing Task 3 draft.
- Produces: one remotely readable `hot_business` draft with safe promotion state.

- [ ] **Step 1: Push without `--dry-run`**

Run the Task 3 command without `--dry-run`. Do not pass `--publish`.

- [ ] **Step 2: Read back the saved draft**

Use `fetch_draft_news_item` with the `hot_business` slot media ID. Verify the remote title matches, body contains three `<img>` tags, and the cover exists locally.

- [ ] **Step 3: Verify promotion safety**

If a short drama was selected, assert:

```text
short_play_count=1
plain_cps_count=0
attribution_ticket_present=True
```

If the documented soft-failure policy skipped short drama, assert `short_play_count=0`, `plain_cps_count=0`, and report the recorded skip reason.

- [ ] **Step 4: Run final regression tests**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_wechat_mp_hot_business.py \
  tests/unit/test_wechat_mp_hot_business_article.py \
  tests/unit/test_wechat_mp_hot_business_cli.py \
  tests/unit/test_wechat_mp_codex_hot_business.py \
  tests/unit/test_wechat_mp_short_drama.py
```

Expected: all pass.

- [ ] **Step 5: Report the result**

Report title, media ID, body length, public/generated image mix, source-domain count, quality score, AI flavor, traffic checklist result, short-drama name or skip reason, and confirm the article remains a draft rather than published.
