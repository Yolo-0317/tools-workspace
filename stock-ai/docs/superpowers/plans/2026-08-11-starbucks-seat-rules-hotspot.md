# Starbucks Seating Rules Hotspot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce and validate a 2,000-plus-character WeChat hotspot deep review about whether Starbucks should manage non-paying seat use.

**Architecture:** Store the manually researched article as the existing Codex hotspot JSON contract, then pass it through the normal hotspot draft dry-run so title, body, layout, sourcing, figures, and compliance use the same production gates. Stop before remote draft creation.

**Tech Stack:** JSON, Python 3.12, existing `scripts.tools.wechat_mp_draft` hotspot pipeline

## Global Constraints

- Title: `星巴克该管“只坐不买”的人吗？`
- Body target: 2,100–2,400 Chinese characters, at least 2,000.
- Use pure paragraphs without headings or numbered lists.
- Separate verified facts from commentary and avoid group labels or moral condemnation.
- Include the three approved research URLs.
- Dry-run only; do not write to the WeChat draft box without another user confirmation.

---

### Task 1: Write the structured hotspot article

**Files:**
- Create: `output/hotspot_codex_starbucks_seating_20260811.json`

**Interfaces:**
- Consumes: the approved title, argument design, and three research URLs.
- Produces: a JSON object with `title`, `digest`, `body`, `topic`, `research_urls`, and `slot_key`.

- [x] **Step 1: Write the eight-unit argument as natural paragraphs**

Write the current dispute, the 2024 Xi'an incident, the 2025 study-room counterexample, the three seat-use scenarios, the positions of paying customers and visitors, the burden on store staff, practical rule boundaries, and the final “third space has rules” conclusion.

- [x] **Step 2: Validate the local artifact**

Run a Python assertion that parses the JSON, checks the exact title, requires at least 2,000 body characters, checks all three URLs, and rejects the banned meta phrases from the design.

### Task 2: Run the production dry-run gates

**Files:**
- Consume: `output/hotspot_codex_starbucks_seating_20260811.json`
- May create: the existing hotspot figure cache and source manifest under the normal pipeline paths.

**Interfaces:**
- Consumes: `--kind hotspot --codex-draft <json> --dry-run`.
- Produces: a validated local preview result without a remote draft mutation.

- [x] **Step 1: Run the exact dry-run**

```bash
WECHAT_MP_HOTSPOT_TREND_ENRICH=0 uv run python -m scripts.tools.wechat_mp_draft \
  --kind hotspot \
  --codex-draft output/hotspot_codex_starbucks_seating_20260811.json \
  --dry-run
```

- [x] **Step 2: Fix only reported content or figure failures**

If the gate reports body length, banned phrasing, title, paragraph, source, or figure failures, revise the JSON or supply only the requested missing figure slots, then rerun the same command.

- [x] **Step 3: Report the verified title, body length, sources, and dry-run status**

Do not remove `--dry-run` until the user explicitly asks to push the draft.
