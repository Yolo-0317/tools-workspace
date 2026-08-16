# Stable Announcement Backfill Design

## Goal

Complete the historical point-in-time announcement backfill without repeatedly
running unrelated sector or ST synchronization and without allowing burst
requests to trigger long runs of failed announcement partitions.

The completed backfill remains an audited reference-data operation. It does not
invoke the deprecated Eastmoney eight-dimension diagnosis, change selection
rules, create executable shares, or write holdings, orders, schedules,
notifications, decision memory, or advisor memory.

## Observed Failure

The existing full reference-data command successfully resumed Eastmoney
announcement checkpoints, increasing complete natural-day partitions from 84
to 194. It then received non-standard HTTP 567 responses after sustained burst
pagination. The adapter classified 567 as provider unavailability, and the
generic 1/2/4-second retry policy was too short to clear the provider-side WAF
block.

The full command also revalidates sector and ST data before announcements. This
work is unnecessary for an announcement-only repair and obscures announcement
progress. The official CNINFO endpoint completed a bounded 2024-04-15 sync, but
multiple earlier historical partitions still failed schema validation, so it
is not the selected bulk fallback for this repair.

At the design checkpoint, 194 Eastmoney announcement partitions are complete
and 759 remain failed in the requested 2023-12-26 through 2026-08-04 range.
Existing complete checkpoints must be reused.

## Considered Approaches

### 1. Announcement-only mode with pacing and a circuit breaker

This is the selected approach. It keeps the existing audited page and
natural-day validation while adding an operational path that touches only
announcement data. Eastmoney requests are deliberately paced, HTTP 567 is
treated as rate limiting, and exhausted rate-limit retries stop the whole run
instead of manufacturing failures for every later day.

### 2. Manual date batches with operator-managed cooldowns

This requires no production change, but it is easy to restart too early,
repeats sector/ST work, provides poor progress visibility, and can trigger the
same WAF block at each batch boundary.

### 3. Switch the full history to CNINFO

CNINFO is the preferred official source when its partitions validate, but the
observed historical schema failures make it unsuitable as the immediate bulk
path. Fixing those older records is a separate compatibility task.

## CLI Contract

The existing manual command gains:

```text
--datasets {all,announcement}
```

`all` remains the default and preserves current behavior. `announcement`
requires the `cninfo-baostock` provider family and executes only announcement
synchronization. In announcement-only mode the CLI must not construct a
BaoStock provider, calculate the historical stock universe, fetch industry
changes, or run ST synchronization.

The existing `--announcement-provider {cninfo,eastmoney}`, `--start`, and
`--end` arguments continue to select the raw source and bounded date range.
No scheduling, automatic rerun, notification, AI diagnosis, or trading option
is added.

## Components and Data Flow

### Announcement-only synchronization function

A public announcement-only synchronization function accepts ordered trading
dates, the selected announcement source, the repository, a captured timestamp,
and optional progress and sleep dependencies. It reuses the existing
natural-day partition expansion, page validation, announcement normalization,
risk-flag upsert, sync-run audit, and checkpoint persistence.

For every natural-day partition:

1. A complete checkpoint for the selected provider is skipped.
2. Otherwise every declared page is fetched and validated.
3. Declared totals, page indexes, page sizes, page counts, required fields, and
   duplicate announcement identities remain fail-closed.
4. Only normalized material-risk flags are written to the risk table; ordinary
   announcements still contribute to coverage evidence through checkpoints.
5. A complete checkpoint is saved only after the entire partition validates.

Announcement-only historical backfill disables the normal recent-date refresh
behavior. A completed recent partition is skipped just like any other completed
historical partition; current-day refresh remains part of the existing
all-dataset operational path.

### Eastmoney request pacing

`EastmoneyAnnouncementProvider` gains injectable sleeping and a conservative
request interval. Production Eastmoney requests wait 0.5 seconds between HTTP
calls. Tests inject a no-wait recorder, so the pacing contract is deterministic
without slowing the unit suite.

The provider treats HTTP 403, 429, and the observed 567 response as
`PROVIDER_RATE_LIMITED`. Transport failures and ordinary 5xx responses remain
`PROVIDER_UNAVAILABLE`; other non-200 responses remain
`PROVIDER_SCHEMA_CHANGED`.

### Rate-limit cooldown and circuit breaker

Announcement-only synchronization applies a dedicated rate-limit policy to the
current page:

- wait five minutes after a rate-limited attempt;
- retry the same page, without advancing its checkpoint;
- allow three cooldown retries;
- if the final retry is still rate-limited, save an auditable failed checkpoint
  and failed sync run for the current partition, then stop the entire command
  with exit code 2.

Stopping the run is intentional. It prevents one WAF event from rewriting every
remaining historical partition as failed. A later manual invocation resumes
from existing complete checkpoints. Generic provider-unavailable and schema
failures retain bounded retries and auditable per-partition failure behavior.

### Progress reporting

Announcement-only mode prints concise progress after every ten processed
natural-day partitions and once at termination. Each update includes processed,
complete, skipped, failed, and total partition counts. It does not print raw
announcement titles, response bodies, credentials, or MySQL URLs.

## Idempotency and Lineage

- Existing complete checkpoints are immutable evidence and are skipped.
- Failed checkpoints may be retried and replaced by complete checkpoints only
  after full validation.
- Risk flags continue to use their existing deterministic identities and
  upsert semantics.
- Sync-run identities, completeness thresholds, risk classification, effective
  dates, and provider labels remain unchanged.
- The operation writes only announcement checkpoints, announcement sync runs,
  and normalized announcement risk flags when `--datasets announcement` is
  selected.

## Error Handling

- HTTP 403/429/567: `PROVIDER_RATE_LIMITED`, dedicated cooldown, then circuit
  breaker on exhaustion.
- Transport error or ordinary HTTP 5xx: `PROVIDER_UNAVAILABLE` under the
  existing bounded transient retry behavior.
- Invalid JSON, metadata drift, malformed records, duplicate identities,
  pagination gaps, or declared-total mismatch: `PROVIDER_SCHEMA_CHANGED` and no
  complete checkpoint.
- MySQL or local programming error: concise CLI failure with exit code 2 for
  expected runtime errors; unexpected programming errors remain visible during
  tests and development.
- A stopped run never marks untouched later partitions as failed.

## Testing

Tests must be written before production changes and prove:

- the parser defaults to `--datasets all` and accepts explicit
  `--datasets announcement`;
- announcement-only CLI execution does not build the universe or invoke sector
  and ST providers;
- Eastmoney waits between requests through an injected sleeper;
- HTTP 567 is classified as `PROVIDER_RATE_LIMITED`;
- a rate-limited page retries after the declared cooldown without advancing the
  checkpoint;
- three exhausted cooldown retries stop the run and leave later partitions
  untouched;
- completed checkpoints are skipped on resumption;
- progress is emitted every ten processed natural days and at termination;
- existing all-dataset behavior, pagination validation, normalization, and
  coverage tests remain unchanged.

Focused provider, alternative-reference-sync, and CLI tests run first. The
complete buy-point regression must then pass before any live backfill resumes.

## Runtime Acceptance

After code verification:

1. Wait until the current Eastmoney WAF block clears.
2. Run a bounded announcement-only batch and verify complete checkpoints,
   progress output, pacing, and zero sector/ST writes from that invocation.
3. Resume the full 2023-12-26 through 2026-08-04 Eastmoney backfill.
4. Verify every required research date has complete announcement coverage.
5. Rerun the five-day `research` stage only after coverage is complete.
6. Do not run `freeze` or the irreversible one-shot `test` stage without a
   separate review of the new research artifact.

## Out of Scope

- Relaxing announcement completeness or fabricating missing dates.
- Skipping malformed provider rows or reducing declared totals locally.
- Changing announcement risk keywords, severity, effective dates, or veto
  behavior.
- Repairing old CNINFO historical schema differences.
- Adding concurrency, proxy rotation, IP evasion, automatic scheduling, or
  background reruns.
- Modifying selection profiles, `TWO_R`, the five-day return research logic,
  holdings, orders, position memory, advisor memory, or decision ledgers.
