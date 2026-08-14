# Resistance Evidence Validation Design

## Status

Approved in conversation on 2026-08-14. The implementation remains research-only and read-only with respect to portfolio and market-data stores.

## Purpose

Remove a false historical-holdings incompleteness signal, separate two materially different reasons that the repeated-pivot resistance variant passes, and run two frozen out-of-sample weekly case reviews before considering any formal rule change.

The August 3–7 v3 case showed 15 complete resistance profiles. Nine passed the repeated-pivot variant, but that total mixed opportunities with an observed resistance cluster at or above 2R and opportunities for which no repeated cluster was found. Those groups cannot be interpreted as one cohort.

## Root Cause Evidence

The August 5 incomplete date originates in historical holdings, not market or reference data:

- sector and ST coverage are complete;
- the market snapshot is complete;
- August 3, 4, 6, and 7 have EOD account and position snapshots;
- August 5 has no EOD snapshot;
- there are no portfolio position events between August 4 and August 6; and
- the August 4 and August 6 positions are identical.

`_load_holdings_by_date` currently treats only an exact-date EOD snapshot as authoritative. When one is missing, it tries to reconstruct holdings from append-only events without starting from the latest earlier snapshot. With no August 5 event, it returns an empty holding set and marks the date incomplete. This loses unchanged positions and is the root cause.

## Considered Approaches

### Carry forward the latest EOD snapshot and apply later events

This is the selected approach. For every signal date, select the latest EOD account snapshot on or before that date, copy its positive-share positions, then apply per-code `shares_after` events after that snapshot's EOD boundary and before the signal date's EOD boundary. An exact-date EOD snapshot is used directly and is not modified by same-day events already represented in it.

This preserves point-in-time semantics, requires no database mutation, and fails closed when no prior snapshot exists.

### Reconstruct entirely from portfolio events

Rejected because the event table is append-only per changed code and is not guaranteed to contain a complete opening portfolio. An event-only reconstruction can silently drop unchanged holdings.

### Backfill the missing August 5 snapshot in MySQL

Rejected for this task because it mutates portfolio history and fixes only one date. The reader must correctly handle any future gap between authoritative snapshots.

## Historical Holdings Reconstruction

The loader queries the latest EOD account snapshot on or before the first requested signal date as an anchor, plus every EOD snapshot through the final requested signal date. It loads matching position rows and position events through the final signal-date cutoff.

For each requested signal date:

1. Find the latest snapshot date no later than the signal date.
2. If none exists, return an empty set with `complete=False`.
3. Start from all positive-share positions in that snapshot.
4. Apply events with timestamps from the next calendar day after the snapshot through, but not including, the next calendar day after the signal date.
5. A positive `shares_after` adds or updates the code; zero removes it.
6. Return the resulting positive-share code set with `complete=True`.

An exact-date snapshot remains authoritative. Events earlier than its next-day boundary are not replayed onto it because they are already reflected by the EOD snapshot.

## Resistance Pass Evidence

The immutable report schema advances from `buy-point-case-review-v3` to `buy-point-case-review-v4`. Existing v1, v2, and v3 artifacts remain unchanged.

Every complete variant receives one derived evidence basis:

- `LEVEL_AT_OR_ABOVE_2R`: a resistance level exists and is at or above the existing 2R target;
- `NO_LEVEL`: no resistance level of that variant exists in the bounded 60-bar signal-time window;
- `LEVEL_BELOW_2R`: a resistance level exists below the 2R target; or
- `INCOMPLETE`: the profile is incomplete and cannot pass.

Existing `passes_two_r` semantics remain unchanged for compatibility: the first two bases pass, while the latter two do not. No production plan, selector, gate, rule version, or position size reads this evidence basis.

The v4 payload adds the basis to serialized variants and adds `resistance_evidence_comparison`, grouped by setup type, resistance variant, and passing basis. Only `LEVEL_AT_OR_ABOVE_2R` and `NO_LEVEL` appear in passing-cohort rows. Each row reports:

- complete profile count for the setup and variant;
- cohort opportunity count;
- triggered, resolved, successful, and stop-first counts;
- mean fee-adjusted net return, MFE, and MAE where present;
- codes and episode IDs for audit.

The existing aggregate `resistance_comparison` remains in v4 so prior v3 interpretation can be reproduced, but all new decisions use the evidence-split comparison.

## Frozen Validation Windows

After implementation and regression verification, regenerate these two independent reviews without changing any resistance definitions or thresholds between runs:

- signal window 2026-07-20 through 2026-07-24, outcome cutoff 2026-07-31;
- signal window 2026-07-27 through 2026-07-31, outcome cutoff 2026-08-07.

Also regenerate the August 3–7 case through August 14 to verify that August 5 is no longer incomplete and that the v4 split reconciles to the v3 aggregate counts.

The validation reports, by setup type and evidence basis, trigger rate inputs, resolved successes, stop-first count, mean net return, MFE, MAE, and missed buyable winners. No parameter is changed after seeing either validation window.

## Safety and Failure Handling

- MySQL access remains read-only; no snapshot, event, holding, memory, or order row is inserted or updated.
- A missing prior EOD snapshot fails closed even if later events exist.
- Future snapshots and events cannot affect an earlier signal date.
- Existing exact-date snapshots remain authoritative.
- All resistance profiles remain `CASE_ANALYSIS_ONLY`, `NO-TRADE`, and zero-share.
- Production `planning.py`, `nearest_resistance_above`, `build_price_plan`, and rule version `buy-point-selection-3.1.0` remain unchanged.
- Announcement incompleteness remains visible and is not rewritten by this change.
- Generated JSON and Markdown remain ignored by Git.

## Tests

Tests must prove:

- a missing middle-day snapshot inherits the latest prior positive-share positions;
- intervening buy, sell, and full-clear events are applied in timestamp order;
- an exact-date EOD snapshot overrides an older snapshot and does not double-apply same-day events;
- a signal date before the first available snapshot remains incomplete;
- future snapshots and events do not leak backward;
- the August 5 input becomes holdings-complete through the real read-only LAN path;
- each resistance variant derives the correct evidence basis for level pass, no level, below 2R, and incomplete input;
- evidence comparisons do not mix `LEVEL_AT_OR_ABOVE_2R` with `NO_LEVEL` outcomes;
- exact representative outcome joins and zero-share safety remain intact;
- v4 identity differs from v3 while all v3 payload fields remain present;
- production planning tests and the broader buy-point regression remain unchanged.

## Acceptance Criteria

The work is complete when:

- August 5 is no longer incomplete because of a missing exact-date holdings snapshot;
- the August v4 report separately displays observed-level passes and no-level passes;
- both frozen July weekly windows produce immutable v4 artifacts with complete audit rows;
- no formal rule, position, memory, or order state changes;
- all relevant unit and integration tests pass; and
- the tracked implementation paths are clean after scoped commits.
