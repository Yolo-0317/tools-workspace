# Five-Day Benchmark Index Fallback Design

## Goal

Restore complete point-in-time market snapshots for the five-day return
research without changing its benchmark definition or weakening its
fail-closed coverage rules.

The research continues to require exactly three benchmark indices:
`sh.000001` (上证指数), `sz.399001` (深证成指), and `sh.000688` (科创50).
BaoStock remains the primary source. Raw Eastmoney index K-lines are used only
when BaoStock returns an entirely empty series for one of those exact indices.

## Evidence and Root Cause

The completed announcement backfill covers all 504 train-plus-validation
research dates. Sector, ST, and announcement reference coverage are each
504/504, so announcements are no longer the blocker.

The latest research artifact still contains zero observations and reports
`point_in_time_complete=false`. A source-level probe found:

- `sh.000001`: 636 BaoStock bars and zero missing research dates;
- `sz.399001`: 636 BaoStock bars and zero missing research dates;
- `sh.000688`: zero BaoStock bars and all 504 research dates missing.

Historical market snapshots require all three benchmark series. The empty
科创50 series therefore makes every snapshot incomplete, and signal discovery
fails closed before stock-level candidates are evaluated.

A bounded raw Eastmoney/OpenCLI probe for index code `000688` returned 636
unique bars for 2023-06-29 through 2026-02-06 and covered all 504 required
research dates. No MySQL write or Eastmoney stock-diagnosis framework was used
in that probe.

## Considered Approaches

### 1. Reuse the existing empty-series fallback adapter

This is the selected approach. The existing
`_load_benchmark_index_bars(start, end)` adapter already loads all three
indices from BaoStock and calls the raw Eastmoney index K-line endpoint only
for an empty primary series. The five-day research and range input loaders
will pass this adapter through the existing `benchmark_loader` dependency.

This is the smallest change, keeps one benchmark definition, and makes
research, frozen test input loading, and forward input loading use the same
source policy.

### 2. Persist Eastmoney index bars in MySQL

This would reduce repeated network reads and improve source auditing, but it
requires a new schema, synchronization lifecycle, completeness checkpoints,
and migration work. It is unnecessary for proving and unblocking the current
research path.

### 3. Replace 科创50 with another BaoStock-supported index

This would avoid the missing source but would silently change the already
approved market-state definition and make earlier research incomparable. It is
rejected.

## Components and Data Flow

The benchmark code set remains the existing
`BENCHMARK_INDEX_CODES = ("sh.000001", "sz.399001", "sh.000688")`.

The existing `_load_benchmark_index_bars(start, end)` function remains the
single source adapter:

1. Load every benchmark series from BaoStock.
2. Keep every non-empty BaoStock series authoritative and unchanged.
3. Collect only codes whose BaoStock result is entirely empty.
4. Fetch those codes from the raw Eastmoney index K-line endpoint through
   `fetch_index_kline_rows_opencli`.
5. Normalize valid, date-bounded rows into `IndexBar` values.
6. Return an empty series when fallback retrieval or normalization cannot
   produce valid bars, allowing downstream coverage checks to fail closed.

Both `_load_mysql_research_inputs(...)` and
`_load_mysql_range_inputs(...)` in the five-day CLI will pass this adapter as
`benchmark_loader` to `load_mysql_five_day_inputs(...)`. The range loader is
shared by later frozen-test and forward stages, so all stages receive the same
benchmark source behavior without changing their one-shot or artifact gates.

No fallback data is persisted in MySQL in this change.

## Error Handling and Safety

- BaoStock remains primary. Eastmoney never overwrites a non-empty BaoStock
  series and does not fill isolated gaps inside a non-empty primary series.
- Malformed rows, invalid dates, non-positive closes, and out-of-range rows are
  ignored by the existing normalizer.
- Eastmoney transport, OpenCLI, parsing, or provider errors produce an empty
  fallback series. Downstream point-in-time completeness remains false rather
  than fabricating benchmark data.
- The fallback uses only the raw Eastmoney index K-line endpoint. The
  deprecated Eastmoney eight-dimension or any stock-diagnosis framework remains
  forbidden to AI and is not invoked.
- The change creates no orders, executable shares, holdings writes, decision
  memory, advisor memory, schedules, or notifications.
- This implementation and acceptance run stop at `research`; they do not run
  `freeze` or the one-shot `test` stage.

## Testing

Tests are written before the production wiring and must prove:

- the research input loader passes the benchmark fallback adapter into
  `load_mysql_five_day_inputs`;
- the range input loader used by later test and forward stages passes the same
  adapter;
- existing fallback behavior preserves non-empty BaoStock series and fills
  only empty series;
- a failed or empty Eastmoney fallback remains empty so completeness continues
  to fail closed;
- no diagnosis, persistence, trading, scheduling, notification, or memory
  surface is introduced.

Focused unit tests for the CLI loader wiring and benchmark merge run first.
Then the most relevant five-day research/runtime regression tests run. The
pre-existing unrelated dirty test and working-tree changes are preserved.

## Runtime Acceptance

After code verification:

1. Run the five-day `research` stage only with the existing MySQL runtime
   connection override at `192.168.1.13:3306`.
2. Confirm all required benchmark dates are covered and
   `point_in_time_complete=true`.
3. Inspect the new research artifact for nonzero observations, rejection
   evidence, profile sample counts, and return metrics; nonzero observations
   are required, but profile qualification is determined by evidence rather
   than forced.
4. Compare the artifact identity and input fingerprint with the prior
   zero-observation artifact so the source-policy change is auditable.
5. Stop before `freeze` and `test` and report the research result for review.

## Out of Scope

- Changing the three benchmark indices or weakening completeness rules.
- Filling individual holes inside a non-empty BaoStock series.
- Adding an index-bar database table, cache, scheduled synchronization, or
  automatic retry service.
- Changing candidate discovery, profile thresholds, return labels, position
  sizing, `TWO_R`, or short-term trading advice.
- Using Eastmoney stock diagnosis, the deprecated eight-dimension framework,
  or any AI interpretation of that framework.
- Running `freeze`, consuming the one-shot test set, or enabling live orders.
