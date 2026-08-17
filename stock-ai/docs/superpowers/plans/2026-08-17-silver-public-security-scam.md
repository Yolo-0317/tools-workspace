# Silver Public-Security Scam Draft Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create and push a verified `silver` money-safety draft about “安全账户” scams, using only traceable public-reporting facts and images.

**Architecture:** First extend the new `silver` pipeline to reuse the proven discussion-image preparation, injection, and cover path while keeping silver prose and safety validation unchanged. Codex then prepares a structured `CodexSilverDraft` JSON from three authoritative public reports; `wechat_mp_draft --kind silver` performs originality, compliance, rendering, image upload, short-drama selection, and independent-slot persistence. Public images live in one topic asset directory with a `figure_sources.json` provenance manifest; if four safe, traceable images cannot be obtained, the workflow stops instead of generating replacements.

**Tech Stack:** Python 3, existing `stock-ai` WeChat draft tools, pytest, JSON, WeChat Official Account draft API.

## Global Constraints

- Audience: readers aged 50—65 who are near or newly in retirement; speak directly and respectfully without age anxiety.
- Lane and slot are exactly `money` and `silver`.
- Body length is 1900—2300 non-whitespace characters and must remain within the platform gate of 1600—2600.
- Use 3—4 natural `> ` section headings, short paragraphs, a concrete opening scene, and one ending question.
- Use at least three distinct source domains and bind every `facts[].source_url` to `research_urls`.
- Use one cover and three body images from verified original report pages only; no generated, search-thumbnail, unattributed, or sensitive transaction-detail images.
- Do not reproduce operational scam details, account identifiers, phone numbers, QR codes, or credentials.
- Do not recommend financial products or promise recovery, returns, or outcomes.
- Quality score must be at least 75, AI-flavor score at most 20, and compliance failures empty.
- Short-drama insertion is best-effort; ordinary CPS product cards must remain absent.
- Create a draft only; do not publish.

---

## File Map

- Create: `stock-ai/output/silver_public_security_scam_20260817.json` — local structured article handoff; never commit.
- Create: `stock-ai/assets/wechat_mp/inline-discussion/冒充公检法安全账户诈骗/still-01.jpg` through `still-04.jpg` — verified report images; do not commit unless the repository’s existing asset policy explicitly tracks the topic directory.
- Create: `stock-ai/assets/wechat_mp/inline-discussion/冒充公检法安全账户诈骗/figure_sources.json` — per-image provenance.
- Create: `stock-ai/assets/wechat_mp/inline-discussion/冒充公检法安全账户诈骗/codex-images-ready.json` — image handoff marker using the article type accepted by the current discussion renderer.
- Modify: `stock-ai/scripts/tools/wechat_mp_codex_silver.py` — add the silver draft’s discussion-topic adapter.
- Modify: `stock-ai/scripts/tools/wechat_mp_silver_article.py` — prepare and inject verified public images and retain the last built silver topic.
- Modify: `stock-ai/scripts/tools/wechat_mp_draft.py` — select the verified discussion cover for `silver` instead of the generic hot-business cover.
- Read only: `stock-ai/scripts/tools/wechat_mp_short_drama.py` — short-play and plain-CPS verification regexes.
- Modify: `stock-ai/tests/unit/test_wechat_mp_codex_silver.py` — test topic adapter shape.
- Modify: `stock-ai/tests/unit/test_wechat_mp_silver_article.py` — test three-image injection and fail-closed behavior.
- Modify: `stock-ai/tests/unit/test_wechat_mp_silver_cli.py` — test the public discussion cover selection.
- Read/write by pipeline: `stock-ai/data/wechat_mp_draft_slots.json` — `silver` media ID after successful push.

### Task 1: Add verified public-image support to the silver pipeline

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_codex_silver.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_silver_article.py`
- Modify: `stock-ai/scripts/tools/wechat_mp_draft.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_codex_silver.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_silver_article.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_silver_cli.py`

**Interfaces:**
- Consumes: `CodexSilverDraft`, `prepare_hotspot_topic_images(topic_dict, body_count=3)`, `inject_discussion_figures(body, topic_dict)`, `ensure_discussion_cover(topic_dict)`, and `pick_discussion_draft_thumb(topic_dict)`.
- Produces: `CodexSilverDraft.as_discussion_topic() -> dict[str, object]`, `get_last_built_silver_topic() -> dict[str, object] | None`, three `[[fig:discussion/...]]` markers in the built body, and a discussion cover selected from the same verified topic directory.

- [ ] **Step 1: Write the failing topic-adapter test**

Add this assertion to `test_wechat_mp_codex_silver.py` using the existing `_draft()` fixture:

```python
def test_silver_draft_exposes_discussion_topic() -> None:
    topic = _draft().as_discussion_topic()
    assert topic["trend_title"] == _draft().topic
    assert topic["title_zh"] == _draft().topic
    assert topic["cover_slug"] == "冒充公检法安全账户诈骗"
    assert topic["research_urls"] == list(_draft().research_urls)
```

Update the fixture topic to `冒充公检法安全账户诈骗` for this test only so the expected slug is deterministic.

- [ ] **Step 2: Run the adapter test and verify it fails**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_wechat_mp_codex_silver.py::test_silver_draft_exposes_discussion_topic
```

Expected: FAIL because `CodexSilverDraft` has no `as_discussion_topic` method.

- [ ] **Step 3: Implement the minimal topic adapter**

Add `as_discussion_topic()` to `CodexSilverDraft`. It must return the exact keys asserted above plus `from_trend: False`; derive `cover_slug` by retaining Chinese letters, ASCII letters, and digits from `topic`, with the compact topic itself as the result for this article.

- [ ] **Step 4: Write failing image-injection tests**

In `test_wechat_mp_silver_article.py`, monkeypatch the public-image preparation and injection functions and assert:

```python
article = article_mod.build_silver_article(codex_draft=_draft(), upload_figures=False)
assert article["body_text"].count("[[fig:") == 3
assert article_mod.get_last_built_silver_topic()["cover_slug"] == "冒充公检法安全账户诈骗"
```

Add a second test where injection returns only two markers and assert `RuntimeError` contains `银发正文配图不足 3 张`.

- [ ] **Step 5: Run the image tests and verify they fail**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_wechat_mp_silver_article.py::test_silver_injects_three_verified_discussion_images \
  tests/unit/test_wechat_mp_silver_article.py::test_silver_fails_closed_when_public_images_are_insufficient
```

Expected: both FAIL because the silver builder does not prepare or inject discussion images.

- [ ] **Step 6: Implement fail-closed silver image preparation**

In `wechat_mp_silver_article.py`, add a module-level `_LAST_BUILT_SILVER_TOPIC`, a getter, and a focused helper that:

```python
topic_dict = draft.as_discussion_topic()
target = discussion_body_figure_target()
prepare_hotspot_topic_images(topic_dict, body_count=target)
body = inject_discussion_figures(draft.body, topic_dict)
if body.count("[[fig:") < target:
    raise RuntimeError(f"银发正文配图不足 {target} 张可用公开报道图")
ensure_discussion_cover(topic_dict)
```

Store the topic for cover selection, and pass the returned body to `_article_shell`. Do not change silver title, disclaimer, hashtags, lane validation, or short-drama behavior.

- [ ] **Step 7: Write the failing cover-selection test**

In `test_wechat_mp_silver_cli.py`, monkeypatch `get_last_built_silver_topic()` to return the test topic and `pick_discussion_draft_thumb()` to return `("thumb-silver", None)`. Assert `_pick_cover_for_kind(kind="silver", cover_kind="hot_business")` returns `("discussion", "thumb-silver", None)`.

- [ ] **Step 8: Implement the silver discussion cover branch**

Before the generic cover fallback in `_pick_cover_for_kind`, load the last built silver topic and call `pick_discussion_draft_thumb(topic)`. If no topic exists, retain the existing generic fallback for non-Codex legacy calls; this article’s fail-closed image helper guarantees a topic.

- [ ] **Step 9: Run focused tests and commit the isolated pipeline change**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_wechat_mp_codex_silver.py \
  tests/unit/test_wechat_mp_silver_article.py \
  tests/unit/test_wechat_mp_silver_cli.py
```

Expected: all pass. Stage only the six silver files named in this task and commit with `feat: add verified images to silver drafts`.

### Task 2: Verify the reporting record and choose safe public images

**Files:**
- Create: `stock-ai/assets/wechat_mp/inline-discussion/冒充公检法安全账户诈骗/figure_sources.json`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/冒充公检法安全账户诈骗/still-01.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/冒充公检法安全账户诈骗/still-02.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/冒充公检法安全账户诈骗/still-03.jpg`
- Create: `stock-ai/assets/wechat_mp/inline-discussion/冒充公检法安全账户诈骗/still-04.jpg`

**Interfaces:**
- Consumes: the three URLs approved in `stock-ai/docs/superpowers/specs/2026-08-17-silver-public-security-scam-design.md`.
- Produces: four valid JPEG files and manifest entries keyed exactly by `still-01.jpg` through `still-04.jpg`.

- [ ] **Step 1: Re-open the three approved pages and record only directly supported facts**

Check these exact claims against the pages:

```text
新华网：女子躲到偏僻山林；正准备告知验证码；民警及时找到。
武汉市公安局：陈婆婆；1.7万元；民警上门劝阻；资金未损失。
四川在线：36.4万元；“安全账户”；两小时劝解；图片据眉山市公安局彭山区分局。
```

- [ ] **Step 2: Extract candidate image URLs from the original pages**

For each candidate, retain its page URL, direct image URL, visible caption, publisher, and date. Reject any image whose only discovery path is a search result or whose page does not establish provenance.

- [ ] **Step 3: Visually inspect every downloaded candidate**

Use `view_image` and reject transaction screenshots or any frame containing readable accounts, codes, phone numbers, or personal identifiers. Select four images with distinct functions: event/cover, on-site intervention, police explanation, and a second non-sensitive scene.

- [ ] **Step 4: Write and validate the provenance manifest**

Each entry must use this exact shape:

```json
{
  "still-01.jpg": {
    "page_url": "https://original-report.example/article",
    "image_url": "https://original-report.example/image.jpg",
    "source_name": "原始媒体或公安机关",
    "published_at": "2026-07-29",
    "source_type": "official-or-news",
    "verified": "true",
    "caption": "不含个人敏感信息的准确图注",
    "page_title": "原报道标题"
  }
}
```

Run:

```bash
jq -e 'length == 4 and ([to_entries[].value.verified] | all(. == "true"))' \
  stock-ai/assets/wechat_mp/inline-discussion/冒充公检法安全账户诈骗/figure_sources.json
file stock-ai/assets/wechat_mp/inline-discussion/冒充公检法安全账户诈骗/still-*.jpg
```

Expected: `jq` exits 0 and all four files are reported as JPEG images.

### Task 3: Write the structured silver article

**Files:**
- Create: `stock-ai/output/silver_public_security_scam_20260817.json`

**Interfaces:**
- Consumes: verified facts and URLs from Task 2.
- Produces: one JSON object accepted by `load_codex_silver_draft()` with `lane="money"` and `slot_key="silver"`.

- [ ] **Step 1: Draft the article around the approved thesis**

Use the title `陌生电话让你躲起来，先别照做` unless a same-thesis wording change is required by a title gate. The first 300 characters must include the Yunnan scene, the successful intervention, and the question of why isolation matters. Structure the body with 3—4 `> ` headings, introduce a new fact or action every 300—500 characters, and end with one question.

- [ ] **Step 2: Build the complete structured JSON**

Include every required field:

```json
{
  "title": "陌生电话让你躲起来，先别照做",
  "digest": "一通自称办案人员的电话，为什么会让人主动躲开家人？从三个公开案例看，先恢复联系比和骗子斗智更重要。",
  "body": "1900至2300个非空白字符的正文",
  "topic": "冒充公检法 安全账户 诈骗",
  "lane": "money",
  "research_urls": [
    "https://www.news.cn/20260729/7cad54d5e80c43e3a0f484c5111c1b3b/c.html",
    "https://gaj.wuhan.gov.cn/jmzx/jfts/202605/t20260529_2770674.html",
    "https://meishan.scol.com.cn/mzyhj/202606/83269113.html"
  ],
  "original_thesis": "骗子往往先切断受害者与家人、银行和真警察的核实渠道，因此第一道防线是挂断并恢复外部联系。",
  "reader_problem": "对方能说出个人信息并自称办案人员时，怎样尽快打断骗局并恢复正常核实？",
  "facts": [
    {"claim": "可由对应报道直接支持的事实", "source_url": "上述三个URL之一"}
  ],
  "practical_steps": ["挂断陌生来电", "拨打110或去派出所核实", "联系家人", "到银行柜面说明情况"],
  "cautions": ["已经转账或泄露验证码时立即联系银行并报警", "不承诺追回结果"],
  "rejected_claims": ["研究中无法由公开原页核验且未写入正文的说法"],
  "slot_key": "silver"
}
```

- [ ] **Step 3: Run schema and safety validation**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -c '
from pathlib import Path
from scripts.tools.wechat_mp_codex_silver import load_codex_silver_draft
d = load_codex_silver_draft(Path("output/silver_public_security_scam_20260817.json"))
print(d.title, d.lane, len("".join(d.body.split())), len(set(d.research_urls)))
'
```

Expected: no exception; output reports the selected title, `money`, body length 1900—2300, and three URLs.

- [ ] **Step 4: Run independent quality evaluation**

Run `evaluate_article()` against the JSON title, digest, and body and fail unless total score is at least 75, AI flavor at most 20, and `compliance_failures` is empty. If the evaluator requests a structure that conflicts with the silver schema, keep the schema and improve only genuine content weaknesses.

### Task 4: Complete the image handoff and dry-run gates

**Files:**
- Create: `stock-ai/assets/wechat_mp/inline-discussion/冒充公检法安全账户诈骗/codex-images-ready.json`
- Read: `stock-ai/output/silver_public_security_scam_20260817.json`

**Interfaces:**
- Consumes: Task 2 images and Task 3 article JSON.
- Produces: a dry-run article with one cover, three inline images, passing originality/compliance, and a safe short-drama selection or explicit soft skip.

- [ ] **Step 1: Write the image-ready marker**

Write the exact marker used by `prepare_hotspot_topic_images` and the discussion renderer:

```json
{
  "schema_version": 1,
  "article_type": "hotspot",
  "topic": "冒充公检法安全账户诈骗"
}
```

- [ ] **Step 2: Run focused silver tests before the pipeline**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_wechat_mp_codex_silver.py \
  tests/unit/test_wechat_mp_silver_article.py \
  tests/unit/test_wechat_mp_silver_cli.py \
  tests/unit/test_wechat_mp_silver_topics.py \
  tests/unit/test_wechat_mp_short_drama.py
```

Expected: all tests pass.

- [ ] **Step 3: Run the complete dry-run**

Run:

```bash
cd stock-ai
set -a; source .env; set +a
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_draft \
  --kind silver \
  --codex-draft output/silver_public_security_scam_20260817.json \
  --dry-run
```

Expected: originality passes; lane is `money`; at least three source domains and one authority source are reported; no missing-image request remains; quality and traffic gates pass; short drama is selected or safely skipped.

### Task 5: Push and read back the independent silver draft

**Files:**
- Modify by pipeline: `stock-ai/data/wechat_mp_draft_slots.json`

**Interfaces:**
- Consumes: the dry-run-clean article and verified image handoff.
- Produces: one WeChat draft stored in `slots.silver.media_id`.

- [ ] **Step 1: Push only after dry-run success**

Run the Task 4 command without `--dry-run`. If WeChat returns `40164`, stop and report the exact observed IPv4; do not modify routing or guess a whitelist address.

- [ ] **Step 2: Read back the saved draft through the official API**

Use `fetch_draft_news_item(media_id=slots["silver"]["media_id"])` and verify:

```text
title == "陌生电话让你躲起来，先别照做" or the approved same-thesis title
thumb_media_id is non-empty
content contains exactly 3 <img tags
PLAIN_CPS_RE count == 0
SHORT_PLAY_RE count is 0 or 1
if SHORT_PLAY_RE count == 1, content contains wxTicket
```

- [ ] **Step 3: Run final verification**

Re-run the focused tests, independent quality evaluation, and readback assertions with fresh output. Report the final media ID, actual image count, quality score, AI-flavor score, originality result, and short-drama state. State explicitly that the draft was not published.
