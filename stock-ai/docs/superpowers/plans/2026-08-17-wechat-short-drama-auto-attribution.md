# WeChat Short Drama Auto Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically obtain a validated, drama-specific `wxTicket` path from the WeChat editor's `minidrama?action=link` endpoint after revenue-first short-drama selection.

**Architecture:** Extend `wechat_mp_short_drama.py` with a strictly local web-session loader, a small request/response client for the link endpoint, and an ensure-attribution boundary used by `attach_short_drama`. The selected drama comes from the full eligible commercial pool; cached attribution is reused only when it still matches, otherwise a fresh path is fetched, validated, saved, and passed through the existing component and draft read-back gates.

**Tech Stack:** Python 3.11+, `requests`, standard library (`dataclasses`, `json`, `os`, `stat`, `time`, `urllib.parse`), pytest.

## Global Constraints

- Never commit, print, or include real Cookie, backend token, fingerprint, `wxTicket`, or full attribution path in test output or logs.
- Read browser session data only from a Git-ignored JSON file whose group/other permission bits are zero.
- Keep the existing feature default off and fail closed on missing, expired, malformed, or mismatched attribution data.
- Validate `dramaId`, `srcAppid`, `play_appid`, and `plan_id` against the selected `ShortDrama` before caching or building a component.
- Do not fall back to ordinary commission-product cards.
- Record rotation usage only after the saved WeChat draft is read back successfully.

---

### Task 1: Secure Web Session and Link Response Parser

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_short_drama.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_short_drama.py`

**Interfaces:**
- Produces: `WeChatDramaWebSession(cookie: str, token: str, fingerprint: str, lang: str)`.
- Produces: `load_drama_web_session(path: Path | None = None) -> WeChatDramaWebSession`.
- Produces: `parse_minidrama_link_response(payload: Mapping[str, Any], drama: ShortDrama, now: datetime | None = None) -> ShortDramaAttribution`.

- [ ] **Step 1: Write failing security and parser tests**

Create a mode-`0600` JSON fixture with synthetic values and assert successful loading. Create a mode-`0644` fixture and assert rejection. Parse a literal double-encoded response containing a synthetic path and assert exact drama, plan, apps, and ticket fields. Add mismatched drama ID, missing ticket, nonzero outer return, and nonzero inner error tests; error strings must not contain the synthetic Cookie or ticket.

- [ ] **Step 2: Run the tests and verify RED**

```bash
.venv/bin/pytest tests/unit/test_wechat_mp_short_drama.py -q
```

Expected: FAIL because the session model, loader, and response parser do not exist.

- [ ] **Step 3: Implement the session loader and parser**

Use `os.stat(path).st_mode` with `stat.S_IMODE`; reject any mode where `mode & 0o077` is nonzero. Require nonempty `cookie`, `token`, and `fingerprint`; default `lang` to `zh_CN`. Parse the outer response, then parse its string-valued `data`, validate the `plugin-private` path query, and construct `ShortDramaAttribution` using the selected drama's plan and apps.

- [ ] **Step 4: Run Task 1 tests and verify GREEN**

Run the targeted tests and then the whole short-drama unit file. Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add stock-ai/scripts/tools/wechat_mp_short_drama.py stock-ai/tests/unit/test_wechat_mp_short_drama.py
git commit -m "feat: parse secure short drama attribution sessions"
```

### Task 2: Minidrama Link Client

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_short_drama.py`
- Test: `stock-ai/tests/unit/test_wechat_mp_short_drama.py`

**Interfaces:**
- Produces: `fetch_short_drama_attribution(drama: ShortDrama, *, web_session: WeChatDramaWebSession | None = None, session: requests.Session | None = None, now: datetime | None = None, random_value: float | None = None) -> ShortDramaAttribution`.
- Consumes: `WECHAT_MP_DRAMA_KOL_ID` and `WECHAT_MP_DRAMA_WEB_SESSION_FILE`.

- [ ] **Step 1: Write a failing exact-request-contract test**

Extend the fake HTTP session to record headers and form data. Assert that the URL is `https://mp.weixin.qq.com/cgi-bin/minidrama?action=link`, `cps_detail` contains the exact millisecond request ID, `biz_type=0`, candidate `play_appid`, candidate `plan_id`, KOL ID, and empty `ext_info`. Assert the outer form contains token, language, JSON flags, fingerprint, deterministic random value, and no browser-version headers.

- [ ] **Step 2: Run the request test and verify RED**

Run the single test. Expected: FAIL because the client does not exist.

- [ ] **Step 3: Implement the client**

Create a fresh `requests.Session` when none is injected and set `trust_env=False`. Send only the required headers and form fields with a 30-second timeout. Call `raise_for_status`, parse JSON, then delegate to `parse_minidrama_link_response`. Convert transport and JSON failures into short actionable `RuntimeError` messages without including raw responses, request headers, paths, or tickets.

- [ ] **Step 4: Run client and parser tests and verify GREEN**

Run the short-drama unit file. Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add stock-ai/scripts/tools/wechat_mp_short_drama.py stock-ai/tests/unit/test_wechat_mp_short_drama.py
git commit -m "feat: fetch WeChat short drama attribution links"
```

### Task 3: Revenue Selection Integration and Safe CLI

**Files:**
- Modify: `stock-ai/scripts/tools/wechat_mp_short_drama.py`
- Modify: `.cursor/skills/wechat-mp-drafts/operations-sop.md`
- Modify: `.cursor/skills/wechat-mp-drafts/reference.md`
- Test: `stock-ai/tests/unit/test_wechat_mp_short_drama.py`
- Verify: `stock-ai/tests/unit/test_wechat_mp_draft_short_drama.py`
- Verify: `stock-ai/tests/unit/test_wechat_mp_product.py`
- Verify: `stock-ai/tests/unit/test_wechat_mp_seo.py`

**Interfaces:**
- Produces: `ensure_attribution_for_drama(drama: ShortDrama, *, path: Path = ATTRIBUTION_PATH, now: datetime | None = None) -> ShortDramaAttribution`.
- Changes: `attach_short_drama` ranks the full eligible pool, then ensures attribution for the selected winner.
- Adds CLI: `--fetch-attribution --drama-id ID`, printing only drama ID, plan ID, and whether a ticket exists.

- [ ] **Step 1: Write failing cache and integration tests**

Assert that a valid cached attribution avoids an HTTP fetch, a missing or stale attribution fetches and saves a replacement, and `attach_short_drama` selects the revenue winner even when only a lower-ranked drama was previously cached. Assert failure leaves the attribution cache unchanged. Add a CLI output assertion proving the synthetic ticket and full path are absent.

- [ ] **Step 2: Run integration tests and verify RED**

Run the affected test file. Expected: FAIL because current attachment prefilters to already-attributed rows.

- [ ] **Step 3: Implement ensure-attribution and attachment integration**

Try `load_attribution_for_drama` first. On missing or mismatched data, fetch a fresh attribution, validate it with `_attribution_matches`, save it atomically through `_save_attributions`, and return it. Change `attach_short_drama` to call `pick_short_drama` on the full eligible deduplicated pool, then call `ensure_attribution_for_drama` for that winner before building the component.

- [ ] **Step 4: Add the safe CLI and operational documentation**

Document the local session JSON keys, the `0600` command, expiry symptoms, and the diagnostic CLI. Never place a real session example in documentation. The CLI must load the current pool, locate exactly one drama ID, fetch or reuse its attribution, and print only safe identity booleans.

- [ ] **Step 5: Run full relevant verification**

```bash
.venv/bin/pytest tests/unit/test_wechat_mp_short_drama.py tests/unit/test_wechat_mp_draft_short_drama.py tests/unit/test_wechat_mp_product.py tests/unit/test_wechat_mp_seo.py -q
.venv/bin/python -m py_compile scripts/tools/wechat_mp_short_drama.py
```

Expected: all tests pass and compilation exits zero.

- [ ] **Step 6: Run a live fail-closed diagnostic**

Without a configured session file, run the new CLI for a candidate without cached attribution and confirm it reports only the missing local-session instruction. After the user creates a `0600` session file, rerun for the current revenue winner and verify only safe fields are printed. Do not create or publish a WeChat draft during this diagnostic.

- [ ] **Step 7: Commit Task 3**

```bash
git add stock-ai/scripts/tools/wechat_mp_short_drama.py stock-ai/tests/unit/test_wechat_mp_short_drama.py .cursor/skills/wechat-mp-drafts/operations-sop.md .cursor/skills/wechat-mp-drafts/reference.md
git commit -m "feat: automate short drama attribution selection"
```
