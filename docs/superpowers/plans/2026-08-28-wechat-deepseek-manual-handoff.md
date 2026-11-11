# WeChat DeepSeek Manual Handoff Implementation Plan

> **For agentic workers:** Execute these documentation changes inline and verify the resulting routing text by search.

**Goal:** Make manual prompt handoff the only DeepSeek collaboration route for user-initiated WeChat articles.

**Architecture:** Update the authoritative WeChat routing and writing documents while preserving editing, image, confirmation, and push gates.

**Tech Stack:** Markdown Skill documentation, ripgrep validation

## Global Constraints

- Agent only gives the complete prompt to the user.
- User independently communicates with DeepSeek and pastes the result back.
- Agent never directly invokes or controls DeepSeek for this workflow.
- No fallback model writes the initial draft.

---

### Task 1: Replace active workflow instructions

- [x] Update the main routing, operations, DeepSeek handoff, and hotspot review documents.
- [x] Preserve two confirmations and downstream fact-checking, image, and push gates.

### Task 2: Verify routing consistency

- [x] Search active workflow documents for stale browser-control instructions.
- [x] Review the diff for changes outside the agreed scope.
