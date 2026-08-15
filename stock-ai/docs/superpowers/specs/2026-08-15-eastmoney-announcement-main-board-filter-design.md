# Eastmoney Main-Board Announcement Filter Design

## Goal

Restore complete Eastmoney announcement synchronization for the buy-point reference-data pipeline without weakening fail-closed pagination or record validation.

## Confirmed Root Cause

The Eastmoney endpoint returns HTTP 200 and stable pagination metadata, but `ann_type=A` mixes equity announcements with `INV`, `SB`, bond, and index records. The current adapter requires every returned row to contain an eligible A-share code, so one mixed record raises `PROVIDER_SCHEMA_CHANGED` and fails the entire natural-day partition.

For 2026-05-22, `ann_type=SHA,SZA` returned 15 pages and 1,417 records. All 1,417 records mapped successfully, all announcement identities were unique, and pagination metadata remained stable. This request scope matches the production selector's Shanghai/Shenzhen main-board universe.

## Scope

- Change the Eastmoney announcement request from `ann_type=A` to `ann_type=SHA,SZA`.
- Keep the existing response status, schema, pagination, declared-total, duplicate-identity, required-field, and PIT timestamp checks unchanged.
- Add a regression test that requires the exact `SHA,SZA` request parameter and rejects accidental reversion to the mixed `A` scope.
- Run the focused Eastmoney and reference-sync tests, the broader buy-point regression, and a read-only live full-day provider validation.
- Preserve all existing uncommitted alternative-reference-source work and commit only files intentionally changed by this repair.

## Out of Scope

- Do not skip malformed records or reduce declared totals locally.
- Do not relax `PROVIDER_SCHEMA_CHANGED` handling.
- Do not change announcement normalization, risk classification, sync checkpoints, or completeness thresholds.
- Do not fabricate or infer missing historical holdings for dates before 2026-05-31.
- Do not write MySQL reference data during the code-fix task. Historical announcement resynchronization is a separate, explicit runtime checkpoint after the code passes verification.
- Do not modify production selection, portfolio state, advisor memory, notifications, schedules, or orders.

## Data Flow

1. The CLI explicitly selects the Eastmoney announcement fallback.
2. `EastmoneyAnnouncementProvider` requests one natural-day partition with `ann_type=SHA,SZA`.
3. Every page retains the provider-declared total, page index, page size, and page count.
4. Every returned record must still map to a valid announcement identity, title, eligible stock code, and optional point-in-time timestamp.
5. The existing sync layer validates all pages and requires the normalized record count to equal the declared total before recording a complete checkpoint.

## Error Handling

- HTTP 403/429 remains `PROVIDER_RATE_LIMITED`.
- HTTP 5xx and transport failures remain `PROVIDER_UNAVAILABLE`.
- Non-200 responses, schema mismatches, malformed records, duplicate identities, pagination drift, or declared-total mismatch remain `PROVIDER_SCHEMA_CHANGED`.
- No partial page or partial natural-day result may be marked complete.

## Testing and Acceptance

The repair is accepted only when:

- a unit test proves the adapter sends `ann_type=SHA,SZA`;
- existing provider failure tests remain unchanged and pass;
- focused alternative-reference synchronization tests pass;
- the complete buy-point unit-test selection passes;
- a read-only live check for 2026-05-22 returns 1,417 mapped records across 15 pages with stable metadata and unique identities; and
- no scoped production, portfolio, memory, scheduling, notification, or order path is modified.
