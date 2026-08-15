# Eastmoney Main-Board Announcement Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore strict, complete Eastmoney announcement synchronization for the Shanghai/Shenzhen main-board buy-point universe.

**Architecture:** Keep the existing provider and sync interfaces unchanged. Narrow the upstream Eastmoney query from the mixed `A` scope to `SHA,SZA`, then retain every existing page, record, duplicate, point-in-time, and declared-total validation. The runtime backfill remains a separate manual checkpoint after the code fix is verified.

**Tech Stack:** Python 3, `requests`, `pytest`, SQLAlchemy-backed reference sync, local read-only Eastmoney HTTP verification.

## Global Constraints

- Preserve `PROVIDER_RATE_LIMITED`, `PROVIDER_UNAVAILABLE`, and `PROVIDER_SCHEMA_CHANGED` fail-closed behavior.
- Do not skip malformed rows or reduce provider-declared totals locally.
- Do not change announcement normalization, risk classification, sync checkpoints, or completeness thresholds.
- Do not fabricate or infer historical holdings before 2026-05-31.
- Do not write MySQL reference data during this implementation plan.
- Do not modify production selection, portfolio state, advisor memory, notifications, schedules, or orders.
- Preserve unrelated dirty-worktree changes. The seven Eastmoney fallback files listed below form one coherent in-progress feature and must be reviewed before staging.

---

### Task 1: Narrow the Eastmoney announcement request and prove strict compatibility

**Files:**
- Create from the existing untracked implementation: `stock_ai/buy_point_selection/reference_eastmoney.py`
- Create from the existing untracked tests: `tests/unit/test_buy_point_reference_eastmoney.py`
- Review and include unchanged fallback seam: `stock_ai/buy_point_selection/reference_sync.py`
- Review and include unchanged source-attribution seam: `stock_ai/buy_point_selection/reference_normalization.py`
- Review and include unchanged CLI seam: `scripts/sync/sync_buy_point_reference_data.py`
- Review and include unchanged source-injection test: `tests/unit/test_buy_point_alternative_reference_sync.py`
- Review and include unchanged CLI tests: `tests/unit/test_sync_buy_point_reference_data.py`

**Interfaces:**
- Consumes: `EastmoneyAnnouncementProvider.fetch_announcement_page(day: date, page_no: int) -> AnnouncementPage` and the existing `sync_alternative_reference_data(..., announcement_source=...)` seam.
- Produces: the same interface and artifact semantics, with the request parameter `ann_type=SHA,SZA` instead of `ann_type=A`.

- [ ] **Step 1: Add the failing request-scope assertion**

In `test_eastmoney_announcement_page_preserves_pit_time_and_paging`, append this assertion after the existing request checks:

```python
assert session.requests[0][1]["ann_type"] == "SHA,SZA"
```

- [ ] **Step 2: Run the focused test and prove it fails for the current mixed scope**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_reference_eastmoney.py::test_eastmoney_announcement_page_preserves_pit_time_and_paging
```

Expected: one failure showing actual `"A"` versus expected `"SHA,SZA"`.

- [ ] **Step 3: Make the minimal provider change**

In `EastmoneyAnnouncementProvider.fetch_announcement_page`, change only the request value:

```python
params = {
    "sr": "-1",
    "page_size": str(self._page_size),
    "page_index": str(page_no),
    "ann_type": "SHA,SZA",
    "client_source": "web",
    "f_node": "0",
    "s_node": "0",
    "begin_time": day.isoformat(),
    "end_time": day.isoformat(),
}
```

Do not change `_announcement`, response parsing, page counts, identity checks, or error mappings.

- [ ] **Step 4: Run focused provider and sync tests**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_buy_point_reference_eastmoney.py \
  tests/unit/test_buy_point_alternative_reference_sync.py \
  tests/unit/test_buy_point_reference_normalization.py \
  tests/unit/test_sync_buy_point_reference_data.py
```

Expected: all selected tests pass with zero failures.

- [ ] **Step 5: Validate one full historical day without database writes**

Run the provider for 2026-05-22, fetch every declared page, and pass them through the existing strict validator:

```bash
PYTHONPATH=. .venv/bin/python -c '
from datetime import date
from stock_ai.buy_point_selection.reference_eastmoney import EastmoneyAnnouncementProvider
from stock_ai.buy_point_selection.reference_sync import _validate_announcement_pages
p = EastmoneyAnnouncementProvider()
first = p.fetch_announcement_page(date(2026, 5, 22), 1)
pages = [first]
for page_no in range(2, first.page_count + 1):
    pages.append(p.fetch_announcement_page(date(2026, 5, 22), page_no))
records = _validate_announcement_pages(pages)
print({"pages": len(pages), "records": len(records), "unique": len({r.announcement_id for r in records})})
'
```

Expected exact output values: `pages=15`, `records=1417`, `unique=1417`.

- [ ] **Step 6: Run the complete buy-point unit regression**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  $(rg --files tests/unit | rg '/test_(review_)?buy_point.*\.py$')
```

Expected: all discovered buy-point tests pass with zero failures.

- [ ] **Step 7: Review and commit only the coherent Eastmoney fallback files**

First inspect the complete scoped diff and confirm it contains only the raw Eastmoney provider, its explicit CLI selection seam, its source-injection seam, and their tests:

```bash
git diff --check -- \
  stock_ai/buy_point_selection/reference_eastmoney.py \
  stock_ai/buy_point_selection/reference_sync.py \
  stock_ai/buy_point_selection/reference_normalization.py \
  scripts/sync/sync_buy_point_reference_data.py \
  tests/unit/test_buy_point_reference_eastmoney.py \
  tests/unit/test_buy_point_alternative_reference_sync.py \
  tests/unit/test_sync_buy_point_reference_data.py
git status --short -- \
  stock_ai/buy_point_selection/reference_eastmoney.py \
  stock_ai/buy_point_selection/reference_sync.py \
  stock_ai/buy_point_selection/reference_normalization.py \
  scripts/sync/sync_buy_point_reference_data.py \
  tests/unit/test_buy_point_reference_eastmoney.py \
  tests/unit/test_buy_point_alternative_reference_sync.py \
  tests/unit/test_sync_buy_point_reference_data.py
```

Then stage exactly those seven files and commit:

```bash
git add \
  stock_ai/buy_point_selection/reference_eastmoney.py \
  stock_ai/buy_point_selection/reference_sync.py \
  stock_ai/buy_point_selection/reference_normalization.py \
  scripts/sync/sync_buy_point_reference_data.py \
  tests/unit/test_buy_point_reference_eastmoney.py \
  tests/unit/test_buy_point_alternative_reference_sync.py \
  tests/unit/test_sync_buy_point_reference_data.py
git commit -m "fix(stock-ai): restore Eastmoney announcement sync"
```

**Checkpoint:** Report the red-green evidence, focused and complete regression counts, live read-only page/record totals, exact commit hash, and the remaining historical-holdings limitation. Do not start MySQL announcement backfill automatically.
