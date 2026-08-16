# Resident Deposits Hotspot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Research, write, illustrate, validate, and push one original hotspot deep-review draft about the reported July decrease of roughly RMB 630 billion in household deposits.

**Architecture:** Use authoritative public reporting to build a Codex hotspot JSON, then pass it through the existing `wechat_mp_draft --kind hotspot --codex-draft` pipeline. The pipeline owns originality checks, public-image discovery, figure injection, short-drama selection, WeChat upsert, and post-save component verification.

**Tech Stack:** Python 3, existing `stock-ai` WeChat scripts, public web research, WeChat Official Account draft API, OpenCLI-backed short-drama attribution cache.

## Global Constraints

- Public title: `居民存款少了6300亿，钱去哪了？`, no more than 20 Chinese characters excluding punctuation handling by the publisher.
- Body must be pure paragraphs, at least 1,920 non-whitespace characters, with mixed short-paragraph mobile layout.
- Research must use at least three distinct source domains and treat the People's Bank of China as the numeric source of truth.
- Image discovery starts from Weibo media posts and Baidu News, then resolves each image to a verifiable original report page; prefer The Paper, CCTV News, China Newsweek, and comparable authoritative outlets.
- Deliver one cover and three body images; only generate missing slots when four verifiable public-report images cannot be obtained.
- Insert exactly one attributed `short-play` component and reject the push if attribution or draft readback fails.
- Do not modify, stage, or commit unrelated dirty-worktree files.

---

### Task 1: Verify facts and source diversity

**Files:**
- Create: `output/hotspot_resident_deposits_research.json`

**Interfaces:**
- Consumes: public PBOC statistics and at least two independent explanatory reports.
- Produces: a source list with URLs, dates, numeric claims, interpretations, and image candidates.

- [ ] Search the exact event phrase and the PBOC July financial-statistics release.
- [ ] Record the household-deposit monthly change and related deposit categories without inferring an unreported destination.
- [ ] Collect at least three source domains, including one official source.
- [ ] Mark each statement as fact, attributed interpretation, or article inference.

### Task 2: Write the Codex hotspot draft

**Files:**
- Create: `output/hotspot_codex.json`

**Interfaces:**
- Consumes: Task 1 research record.
- Produces: `title`, `digest`, `body`, `topic`, `research_urls`, `original_thesis`, and `slot_key` for `load_codex_hotspot_draft`.

- [ ] Write 2,200 to 2,600 Chinese characters in pure paragraphs.
- [ ] Open with the July household-deposit decrease within 50 characters.
- [ ] Explain at least four plausible destinations or accounting reasons while keeping uncertainty explicit.
- [ ] End on the distinction between fast asset reallocation and slow confidence recovery.
- [ ] Scan for forbidden meta-commentary, numbered headings, unsupported certainty, and mechanical one-sentence paragraphs.

### Task 3: Dry-run originality, layout, and figures

**Files:**
- Create or update: `assets/wechat_mp/inline-discussion/居民存款少了6300亿钱去哪了/figure_sources.json`
- Create or update: the same topic directory's verified cover and body images.

**Interfaces:**
- Consumes: `output/hotspot_codex.json`.
- Produces: a dry-run article with four traceable images and a selected short-drama summary.

- [ ] Run `WECHAT_MP_HOTSPOT_TREND_ENRICH=0 PYTHONPATH=. .venv/bin/python -m scripts.tools.wechat_mp_draft --kind hotspot --codex-draft output/hotspot_codex.json --dry-run`.
- [ ] Inspect `figure_sources.json` and retain only images whose original report page, media name, publication context, and topic match are verifiable.
- [ ] Prefer public-report images; if `codex-image-request.json` is produced, generate only the listed missing slots.
- [ ] Repeat the dry-run until originality, length, source diversity, figure count, compliance, and short-drama preflight all pass.

### Task 4: Push and verify the WeChat draft

**Files:**
- Modify: ignored local `data/wechat_mp_draft_slots.json` through the existing upsert API.
- Modify: ignored local short-drama usage and attribution caches as required by the selected winner.

**Interfaces:**
- Consumes: the passing Task 3 draft and verified assets.
- Produces: one WeChat draft-slot media ID with a validated short-drama card.

- [ ] Run the same command without `--dry-run`.
- [ ] Confirm the API reports a successful create or update action.
- [ ] Confirm draft readback finds exactly one `short-play` component and the selected drama ID matches.
- [ ] Record the chosen drama name, commission rate, figure source mix, title, and media ID without exposing cookies or attribution tickets.

### Task 5: Final verification

**Files:**
- Verify only; do not create tracked artifacts.

**Interfaces:**
- Consumes: pushed draft metadata and local source manifest.
- Produces: a concise delivery report.

- [ ] Run the single-article quality evaluation for `hotspot` with traffic checks.
- [ ] Verify the title length, body length, three-source minimum, one cover plus three body images, and one short-drama card.
- [ ] Verify no ordinary product card is present.
- [ ] Report any remaining manual WeChat publishing step separately from draft completion.
