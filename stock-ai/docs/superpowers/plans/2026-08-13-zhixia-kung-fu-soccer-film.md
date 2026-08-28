# Zhixia Kung Fu Soccer Film Post Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a full-spoiler Zhixia film-post draft about Shuangshuang learning to win without making victory the team's only reason to play.

**Architecture:** Store the verified plot arc in a film topic card and write a 550–750-character body that follows disagreement, expulsion, apology, reunion, and championship. Prepare images and run the WeChat dry-run only after the user approves the copy.

**Tech Stack:** JSON topic card, plain-text WeChat copy, existing `wechat_mp_newspic_draft` validator.

## Global Constraints

- Title: `《功夫女足》：赢了以后呢`, under 20 characters.
- S2 with `含结局讨论` on the first line.
- `character_arc` with four distinct stages.
- Snowfield says “我踢球就是为了踢球”; do not attribute it to Shuangshuang.
- Include Shuangshuang expelling Snowfield, apologizing after defeat, the reunion, and the final comeback championship.
- Do not invent scores, dialogue, match order, or real viewing experience.
- `ai_disclosure_mode=platform_publish`; no repeated AI disclosure in body.
- Do not push a draft without a separate confirmation.

---

### Task 1: Write the verified topic card

**Files:**
- Create: `stock-ai/output/zhixia-kung-fu-soccer-topic-card.json`

**Interfaces:**
- Consumes: 1905 film profile and post-release report, plus corroborating plot summaries
- Produces: a complete `popular_film` S2 `character_arc` card with four HTTPS-backed plot anchors

- [ ] Record the disagreement, expulsion, apology/reunion, and championship as distinct stages.
- [ ] Run JSON parsing and film-topic-card validation.

### Task 2: Write and inspect the copy

**Files:**
- Create: `stock-ai/output/zhixia-kung-fu-soccer-copy.txt`

**Interfaces:**
- Consumes: the four plot anchors
- Produces: a 550–750-character body whose first line is `含结局讨论`

- [ ] Write the plot-causal draft with short mobile paragraphs.
- [ ] Check title length, body length, spoiler line, anchor presence, and replacement-film specificity.
- [ ] Deliver the copy for user review; defer image acquisition and dry-run until approval.
