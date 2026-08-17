# Five-Day Ranking V3 Market and Strategy Attribution Design

Date: 2026-08-17

## Status

Approved design for a train-only diagnostic. This design does not change any
ranking rule, qualification threshold, execution profile, validation decision,
or trading permission.

## Problem

The first real V3 train diagnosis ended with `NO_TRAIN_CANDIDATE`. All four
profile roots had negative full-window and recent-window net expectancy, all
eight policies failed qualification, and Rank-1 underperformed Rank 2-3. The
existing artifact cannot distinguish three different causes:

1. the market fell during the evaluated holding intervals;
2. candidate direction was poor relative to the contemporaneous market;
3. ranking, entry, stop, or costs destroyed an otherwise useful signal.

The existing `ALLOW` and `LIMITED` labels are insufficient for this
attribution. They summarize market state but do not retain the benchmark return
over each evaluated interval.

## Objective

Produce one immutable, aggregate-only, train-only attribution artifact that:

- compares V3 outcomes with a matched index and a same-universe market median;
- separates actual-holding attribution from fixed-five-session opportunity
  attribution;
- diagnoses Rank-1 against lower rank bands on the same dates;
- reports market, strategy, mixed, or inconclusive evidence without changing
  V3;
- is reproducible, tamper-evident, idempotent, and safe to inspect;
- creates no validation, test, trading, notification, holding, or memory side
  effects.

## Non-Goals

This work must not:

- change V3 scores, features, gates, weights, capacity, or winner rules;
- run `validate-ranking` or read validation/test outcomes;
- promote a strategy or produce a buy recommendation;
- modify V1, V2, V3, or their parent research artifacts;
- store observation rows, stock codes, positions, or database credentials in
  the attribution artifact;
- implement public strategies or machine-learning models.

A separate follow-on design will create a public-strategy challenger suite.
The first intended challengers are a daily price-volume subset of 101
Formulaic Alphas, five-session market/sector residual reversal, an A-share
price-limit delayed-discovery baseline, and a Qlib Alpha158 Linear baseline.
They will use this attribution design's benchmark, label, cost, split, and
reporting contracts.

## Selected Architecture

Use a standalone attribution pipeline rather than modifying the V3 artifact.
The pipeline has three isolated components:

1. a pure attribution domain module for intervals, benchmark returns,
   aggregation, paired rank comparisons, and verdicts;
2. a strict immutable report module for canonical serialization and loading;
3. a manual CLI that verifies lineage, loads bounded market data, builds the
   report, and stops.

The implementation must not import or invoke validation, test, freeze,
forward-screen, settlement, advisor, notification, memory, or order flows.

## Inputs and Lineage

The CLI accepts exactly:

- one strict V3 train artifact;
- its strict parent five-day research artifact;
- one output directory;
- configured read-only MySQL access for `stock_daily`;
- the existing BaoStock benchmark loader with the existing Eastmoney fallback
  for an entirely empty index series.

Before any market data is read, the CLI must verify:

- the V3 artifact is the current canonical train schema and policy registry;
- `validation_outcomes_read=false` and `test_outcomes_read=false`;
- `promotion_eligible=false` and `trade_permission=NO-TRADE`;
- the parent research identity and input fingerprint match exactly;
- the parent is point-in-time complete and test-untainted;
- only parent train dates and train observations can be mapped.

A lineage failure must stop before MySQL or external benchmark access.

## Benchmark Universe

### Matched index

Map each security to the closest existing benchmark:

- Shanghai main board to `sh.000001`;
- Shenzhen main board to `sz.399001`;
- a future STAR-board candidate to `sh.000688`.

The current five-day candidate universe is Shanghai and Shenzhen main board.
The STAR mapping is retained only to make the boundary explicit if that
universe changes later. Unsupported boards fail closed rather than silently
using an unrelated index.

### Same-universe market median

For each required date pair, calculate the median close-to-close return among
the Shanghai and Shenzhen main-board stocks that the current discovery runtime
can load. A stock contributes only when both endpoints are present, finite, and
strictly positive.

Do not mix ChiNext, STAR, Beijing, funds, or indices into this median. A broader
"all A-share" median would not be an apples-to-apples measure of the current
strategy's opportunity set.

### Coverage

Every attributed interval requires:

- both endpoint closes for the matched index;
- at least 1,000 same-universe stocks with valid endpoint closes for the market
  median;
- both endpoint dates in the bounded training calendar.

Missing coverage is evidence, not a value to impute. If any required aggregate
cannot meet its hard coverage contract, the artifact status is
`MARKET_DATA_INCOMPLETE`, no causal verdict is emitted, and the missing
coverage is reported only as aggregate counts and dates.

## Time and Return Definitions

All arithmetic uses `Decimal` under an explicit local precision. Returns are
simple returns, not percentages, in the serialized artifact.

### Actual-holding attribution

The primary attribution population is admitted, completed V3 trades for every
policy, selection mode, and fold. Non-triggered, cancelled, missing, and
capacity-rejected rows remain in aggregate funnel counts but do not receive a
fabricated holding return.

For a completed trade:

- the stock result is the existing after-cost `net_return`;
- the gross trade return is `exit_price / entry_price - 1`;
- the benchmark interval is index close on actual entry date to index close on
  actual exit date;
- the market interval is the same-universe median return over those endpoints;
- when actual entry and exit occur on the same training date, both benchmark
  returns are exactly zero because the close-to-close endpoints are identical;
  the interval still requires that day's matched-index close and at least 1,000
  valid same-universe closes, and only an exit before entry is invalid;
- index excess is `net_return - matched_index_return`;
- market-median excess is `net_return - market_median_return`;
- after-cost drag is `gross_trade_return - net_return`.

The close-to-close benchmark is an attribution approximation for an intraday
fill. It must be labelled as such and must not be presented as an exact hedged
return.

### Fixed-five-session opportunity attribution

The secondary population is every V3 scored plan retained in a rank trace,
whether or not it was selected or traded. It measures candidate direction and
must remain separate from realized execution.

For each ranked plan:

- start at the signal-date close;
- end at the close of the fifth strictly subsequent trading session;
- compute the stock close-to-close return;
- compute matched-index and same-universe-median returns over the same pair;
- compute the two excess returns.

Rows without a fifth subsequent train session are excluded and counted. The
pipeline must never reach into validation dates to complete a train row.

## Aggregation

Every metric set reports:

- eligible rows and completed rows;
- excluded and missing-coverage counts;
- arithmetic mean and exact median;
- positive-return ratio and Wilson interval;
- matched-index mean and median;
- market-median mean and median;
- mean and median excess against each benchmark;
- gross return and after-cost drag where applicable.

Aggregate actual-holding results by:

- policy;
- selection mode: `FORMAL`, `TOP_1`, and `TOP_5`;
- `train-fold-1`, `train-fold-2`, and `train-combined`;
- outcome status.

Aggregate fixed-five-session results by the same policy, mode, and fold and by
these existing rank bands:

- `RANK_1`;
- `RANK_2_3`;
- `RANK_4_5`;
- `RANK_6_PLUS`.

No stock key or date-keyed observation row may appear in persisted aggregates.

## Rank-1 Diagnosis

The report must not infer rank quality only from unconditional band means.
Market conditions can differ across dates. For each policy and fold, calculate
a same-date paired comparison on dates where Rank-1 and at least one Rank 2-3
row both have valid fixed-five-session outcomes.

For each paired date:

- compare Rank-1 with the median Rank 2-3 raw return;
- compare matched-index excess returns;
- compare market-median excess returns.

Persist the number of paired dates, mean and median paired differences, and the
ratio of dates on which Rank-1 wins. Also report daily cross-sectional Spearman
correlation between negative ordinal rank, where Rank-1 is highest, and each
return target when at least five valid ranked rows exist. Positive correlation
therefore means that better-ranked plans had higher returns. The artifact
reports aggregate correlation counts and mean/median correlations, never daily
rows.

## Attribution Verdicts

Verdicts are descriptive labels and have no promotion effect.

For a metric set with sufficient coverage and samples:

- `MARKET_DRAG`: mean net/raw return is below zero while both benchmark excess
  means are above zero;
- `STRATEGY_DRAG`: both benchmark excess means are at most zero;
- `MIXED`: exactly one benchmark excess mean is positive and the other is at
  most zero;
- `INCONCLUSIVE`: coverage or sample requirements are not met, or the net/raw
  return is non-negative and does not need a negative-return cause label.

The minimum verdict sample is 30 completed actual trades or 30 fixed-five
outcomes. Equality at zero is not positive. Medians and Wilson intervals remain
visible so the user can detect a mean driven by outliers, but they do not alter
the frozen first-version label.

Rank-1 is labelled `RANKER_INVERTED` only when at least 15 paired dates exist
and both mean paired excess differences are at most zero. Opposite signs yield
`RANKER_MIXED`; insufficient pairs yield `RANKER_INCONCLUSIVE`.

## Artifact Contract

The canonical file name is:

```text
ranking-v3-train-attribution-<artifact_identity>.json
```

The payload includes:

- schema and attribution version;
- parent V3 train identity and parent research identity;
- parent input fingerprint and split;
- market-data fingerprint;
- benchmark definitions and coverage thresholds;
- actual-holding aggregates;
- fixed-five-session aggregates;
- Rank-1 paired aggregates;
- attribution and ranker labels;
- `train_only=true`;
- `validation_outcomes_read=false`;
- `test_outcomes_read=false`;
- `promotion_eligible=false`;
- `trade_permission=NO-TRADE`;
- status `COMPLETE` or `MARKET_DATA_INCOMPLETE`.

The strict loader rejects:

- an identity, filename, schema, registry, lineage, split, or fingerprint
  mismatch;
- non-finite numeric values;
- invalid sample counts or arithmetic relationships;
- contradictory coverage and verdict states;
- unexpected policies, modes, folds, or rank bands;
- any nested key named `observations`, `selected_observations`, `plans`,
  `plan_keys`, `ranked_plan_keys`, `admitted_trade_keys`, `code`, `ts_code`,
  `position`, `holding`, `order`, `notification`, or `memory`;
- any flag that suggests validation/test access, promotion, or trading.

Serialization is canonical JSON with sorted keys and compact separators. The
writer creates by content identity and verifies identical bytes if the target
already exists.

## Market Data Fingerprint

The market-data fingerprint binds all bounded inputs without persisting their
rows. It hashes:

- ordered training calendar dates;
- each required benchmark code, date, close, and source-selected series;
- each same-universe security code, endpoint date, and close used by a required
  date pair;
- the benchmark mapping and universe-filter version.

The raw fingerprint material exists only in memory. Database URLs, provider
credentials, and fallback URLs are never included.

## CLI and Failure Handling

Provide one manual command for train attribution. It has no validation or
production subcommands. Expected arguments are the V3 train artifact, parent
research artifact, and output directory.

The CLI prints only the generated artifact path on success. Expected I/O,
lineage, contract, provider, or data errors return a non-zero code with one
sanitized Chinese failure message. It must not print database URLs, stock rows,
observation keys, or provider response bodies.

A legitimate bounded coverage gap produces a strict
`MARKET_DATA_INCOMPLETE` artifact rather than a stack trace. A technical failure
that prevents trustworthy coverage accounting produces no artifact.

## Testing Strategy

### Pure attribution tests

- board-to-index mapping and unsupported-board rejection;
- actual entry/exit endpoint selection;
- same-day actual entry/exit attribution keeps the trade, assigns zero to both
  close-to-close benchmarks, preserves hard coverage, and rejects reversed
  endpoints;
- fifth strictly subsequent train session and no validation spillover;
- exact `Decimal` raw, gross, benchmark, excess, and after-cost drag returns;
- same-universe median with odd/even populations;
- 1,000-security coverage boundary;
- aggregate mean, median, Wilson interval, and status counts;
- verdict truth table, zero boundaries, and minimum samples;
- same-date Rank-1 pairing and minimum paired dates;
- rank correlation minimum cross-section.

### Report tests

- canonical payload and content-addressed filename;
- strict round trip;
- tamper, filename, lineage, registry, and fingerprint rejection;
- count and arithmetic-consistency rejection;
- forbidden nested-key rejection;
- incomplete coverage cannot carry a verdict;
- complete artifact cannot omit required aggregates;
- idempotent write and immutable conflict handling.

### CLI tests

- lineage rejection occurs before market loaders are invoked;
- parent validation/test contamination is rejected;
- only train dates are requested;
- successful dispatch writes one attribution artifact;
- incomplete coverage writes only an incomplete attribution artifact;
- sanitized failure output;
- no validation, test, freeze, forward, settlement, notification, holding,
  memory, or order calls.

### Real train-only verification

After all tests pass:

1. snapshot the output directory and V1/V2/V3 identities;
2. run the manual attribution command once against the canonical V3 train;
3. strict-load the artifact and inspect only aggregates;
4. rerun the identical command and require the same path and file hash;
5. confirm V1/V2/V3 identities are unchanged;
6. confirm no validation/test or operational side effects exist;
7. report the descriptive cause labels and stop.

## Success Criteria

The work is complete only when:

- the artifact can distinguish negative absolute return from negative excess
  return under both benchmarks;
- actual execution and fixed-five opportunity results cannot be confused;
- Rank-1 is compared with Rank 2-3 on the same dates;
- incomplete benchmark data fails closed;
- all persisted data is aggregate-only and strictly loadable;
- repeated execution is byte-identical;
- the real run remains train-only and `NO-TRADE`;
- no existing artifact identity changes.

## Follow-On Public Challenger Suite

The next independent design will compare V3 against public, reproducible
baselines rather than importing published returns as claims. Candidate sources
include:

- 101 Formulaic Alphas, whose published formulas have short average holding
  periods;
- Microsoft Qlib Alpha158/Alpha360 and its China-stock benchmark workflows;
- A-share research on price-limit-driven daily momentum and delayed price
  discovery;
- A-share overnight/intraday reversal and decomposed momentum;
- post-announcement drift using only information available after official
  publication;
- regime-conditioned momentum and liquidity-sensitive short-term reversal.

Every challenger will use the same universe, point-in-time rules, train split,
transaction costs, five-session label, dual benchmarks, and frozen validation
protocol. Public strategies are comparison baselines, not automatic production
rules.
