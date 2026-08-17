# Silver Live-Shopping Article Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a source-backed, mobile-readable silver money article about resisting livestream sales pressure and validate it without publishing.

**Architecture:** Research current primary regulatory guidance and independent public reporting first, then write one structured `CodexSilverDraft` JSON whose facts point only to approved URLs. Feed that JSON through the existing silver dry-run pipeline so originality, money-safety, image provenance, rendering, and promotion compatibility are checked before any WeChat write.

**Tech Stack:** Web research, Codex writing, JSON, existing Python `wechat_mp_draft` and silver validators.

## Global Constraints

- Audience is 50—65-year-old readers addressed directly and respectfully.
- Body length is 1600—2200 Chinese non-whitespace characters, within the pipeline limit of 1600—2600.
- Use 3—4 natural `> ` headings and mostly one-to-three-line mobile paragraphs.
- Use at least three distinct source domains, including a government or regulatory authority.
- Do not invent consumer cases, loss figures, experts, enforcement data, or quotations.
- Do not recommend products, promise returns, or equate all livestream promotion with fraud.
- Use public-report images only when the original page, subject, and source can be verified.
- Do not push or publish; this plan ends at a passing dry-run and user review.

---

### Task 1: Build the verified source packet

**Files:**
- Create: `stock-ai/output/silver_live_shopping_sources_20260818.json`

**Interfaces:**
- Consumes: the research rules in `stock-ai/docs/superpowers/specs/2026-08-18-silver-live-shopping-design.md`.
- Produces: a JSON array of source objects with exact keys `title`, `publisher`, `published_at`, `url`, `claims`, and `image_candidates`.

- [ ] **Step 1: Search primary authorities and public reports**

Search current pages from the State Administration for Market Regulation, China Consumers Association or local consumer councils, public-security authorities, and established news organizations. Prefer pages that directly discuss livestream shopping, impulse purchasing, health-product claims, payment channels, return policies, or evidence retention.

- [ ] **Step 2: Verify every retained source**

Open each candidate page and retain it only when the page itself supports at least one article claim. Record no claim based only on a search-result snippet.

- [ ] **Step 3: Save the source packet**

Write `output/silver_live_shopping_sources_20260818.json` with at least three distinct domains. Each `claims` item must be a concise paraphrase, and each `image_candidates` item must include the original page URL and direct image URL when available.

- [ ] **Step 4: Check the source packet**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -c 'import json; from urllib.parse import urlparse; p=json.load(open("output/silver_live_shopping_sources_20260818.json")); assert len({urlparse(x["url"]).hostname for x in p}) >= 3; assert all(x["claims"] for x in p); print(len(p))'
```

Expected: prints at least `3` and exits successfully.

### Task 2: Write the structured Codex silver draft

**Files:**
- Create: `stock-ai/output/silver_live_shopping_20260818.json`

**Interfaces:**
- Consumes: `output/silver_live_shopping_sources_20260818.json` and `CodexSilverDraft` from `scripts.tools.wechat_mp_codex_silver`.
- Produces: one JSON object accepted by `load_codex_silver_draft(Path(...))`.

- [ ] **Step 1: Draft the article around one thesis**

Use the title `直播间越催着下单，越要先停十分钟` unless verified research makes that promise inaccurate. Open with the payment-button countdown scene; explain the loss of comparison time; provide four practical actions; close with one concrete reader question.

- [ ] **Step 2: Populate the exact contract**

Write these fields: `title`, `digest`, `body`, `topic`, `lane`=`money`, `research_urls`, `original_thesis`, `reader_problem`, `facts`, `practical_steps`, `cautions`, `rejected_claims`, and `slot_key`=`silver`. Every `facts[].source_url` must exactly equal one value in `research_urls`.

- [ ] **Step 3: Validate the JSON contract**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -c 'from pathlib import Path; from scripts.tools.wechat_mp_codex_silver import load_codex_silver_draft; d=load_codex_silver_draft(Path("output/silver_live_shopping_20260818.json")); print(d.title, len("".join(d.body.split())), len(d.research_urls), len(d.facts))'
```

Expected: the title, a character count from 1600 through 2200, at least three URLs from distinct domains, and at least one mapped fact.

### Task 3: Run the publishing pipeline in preview-only mode

**Files:**
- Read: `stock-ai/output/silver_live_shopping_20260818.json`
- Create or update: ignored public-image provenance assets under the silver discussion topic output directory.

**Interfaces:**
- Consumes: the validated `CodexSilverDraft` JSON.
- Produces: a passing silver dry-run preview and provenance-checked image set; no draft ID and no publication.

- [ ] **Step 1: Run the silver dry-run**

Run:

```bash
cd stock-ai
PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_draft \
  --kind silver \
  --silver-lane money \
  --codex-draft output/silver_live_shopping_20260818.json \
  --dry-run
```

Expected: originality report passes; `lane=money`; at least three source domains; at least one authority source; no WeChat draft write.

- [ ] **Step 2: Review the rendered copy and image provenance**

Confirm the first 80 characters deliver the title promise, every 300—500 characters adds information or a pacing hook, public images are spread through the body, and `figure_sources.json` records the original page and publisher for each retained image.

- [ ] **Step 3: Correct only failing evidence or copy**

If a gate fails, revise the source packet or structured JSON and rerun the same dry-run. Do not weaken length, authority-source, claim mapping, medical, financial, or image-provenance checks.

- [ ] **Step 4: Hand the draft to the user**

Return the final title, digest, full copy, source list, image-source summary, and dry-run result. Wait for explicit approval before removing `--dry-run`.
