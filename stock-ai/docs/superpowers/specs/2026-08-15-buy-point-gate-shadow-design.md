# Buy-Point Market and Sector Gate Shadow Design

## Status

Approved in conversation on 2026-08-15. This feature is research-only and
does not change formal selection, gates, portfolio, decision memory, or order
behavior.

## Purpose

Determine whether the current market and sector gates reject otherwise valid
short-term buy points. The study uses formal production setup detections and
counterfactually admits exactly one gate failure reason at a time. It must
produce point-in-time, zero-share evidence before any broader historical study
is considered.

The preceding threshold-shadow study found 1,889 incremental relaxed-setup
hits across the July 20 through August 7 signal windows, but no downstream
candidate. The downstream rejection counts were:

- 884 sector-gate rejections;
- 813 market-gate rejections;
- 158 price-plan rejections; and
- 34 anti-chase rejections.

Those relaxed-setup rows remain attribution evidence only. They cannot be
admitted by this study because doing so would combine a setup relaxation with a
gate relaxation.

## Considered Approaches

### Single-reason counterfactual admission

Selected. A row enters a shadow cohort only when the formal setup exists and
the relevant gate fails for exactly one supported reason. Every other gate and
the price plan remain unchanged. This provides the clearest attribution and
preserves the single-variable boundary.

### Numeric threshold ladders

Rejected for this iteration. Applying 10%, 25%, and 50% ladders to market and
sector thresholds would multiply the number of profiles and invite overfitting
on the short available windows.

### Whole-gate bypass

Rejected. Skipping an entire market or sector gate would mix multiple failure
causes and could admit incomplete or structurally unsafe reference data.

## Research Profiles

The profile matrix contains exactly six reason-level profiles.

Market diagnostic profiles:

- `MARKET:INDEX_AND_BREADTH_WEAK:DIAGNOSTIC`;
- `MARKET:AMOUNT_AND_BREADTH_WEAK:DIAGNOSTIC`.

Sector research profiles:

- `SECTOR:SECTOR_RELATIVE_STRENGTH_WEAK:BYPASS`;
- `SECTOR:SECTOR_NOT_RESONATING:BYPASS`;
- `SECTOR:SECTOR_BREADTH_WEAK:BYPASS`;
- `SECTOR:SECTOR_AMOUNT_WEAK:BYPASS`.

A market profile is permanently diagnostic-only. It can receive an outcome and
appear in comparison reports, but cannot enter a freeze artifact, a forward
screen, or a formal rule.

A sector profile may enter a retrospective freeze only after meeting the
defined evidence thresholds. That freeze grants only permission to appear in a
zero-share forward screen.

## Hard Boundaries

The following failures are never counterfactually admitted:

- incomplete market data;
- incomplete sector membership;
- an insufficient liquid sector sample;
- a non-main-board security;
- an existing holding;
- a point-in-time `VETO` risk flag;
- insufficient history or duplicate dates;
- invalid, suspended, or illiquid bars;
- any anti-chase failure;
- any price-plan failure, including insufficient 2R space or invalid risk
  distance; and
- more than one market or sector failure reason.

Announcement coverage may remain incomplete for case evidence, but the
incompleteness must be explicit and keeps all promotion eligibility false.

## Cohort Isolation

The study keeps two different populations separate.

### Formal-setup gate shadows

These are the only rows eligible for reason-level outcomes, sector-profile
freezing, and prospective screening. Each stock-date must:

1. pass the production base gate;
2. contain at least one formal production setup;
3. fail exactly one supported market or sector reason;
4. pass every other production gate; and
5. produce a valid production price plan with sufficient 2R space.

If multiple formal setups exist for one stock-date, the existing deterministic
setup preference and planning logic choose the representative structure. The
study does not introduce a new setup ranking.

### Relaxed-setup funnel attribution

The 48-profile threshold-shadow rows from the preceding study may be summarized
by downstream failure stage and reason. They remain outside all candidate,
freeze, screen, and outcome-selection calculations. No gate bypass can be
applied to them.

## Signal-Time Data Flow

For each requested signal date, load the complete point-in-time panel once.
Future bars are unavailable to signal generation and participate only in later
outcome settlement.

The pipeline is:

1. require complete signal-date bars, holdings, market state, sector
   membership, and ST/suspension facts;
2. run the unchanged base gate;
3. run the unchanged formal setup detectors;
4. classify the unchanged market gate;
5. require the unchanged anti-chase gate to pass;
6. classify the unchanged sector gate;
7. admit only an exact single supported failure reason;
8. build the unchanged price plan and require its complete validation; and
9. wrap the result as a zero-share gate-shadow candidate.

For a market diagnostic profile, the market gate is the single counterfactual
step; the sector gate must pass normally. For a sector research profile, the
market gate and anti-chase gate must pass normally, and only the one matching
sector reason is counterfactually admitted.

Every shadow object is labeled `CASE_ANALYSIS_ONLY`, `NO-TRADE`, and
`executable_shares=0`.

## Outcome Evaluation

Candidates use the formal 3.1.0 plan trigger, validity period, invalidation,
2R target, transaction costs, five-trading-session horizon, and intraday
ambiguity handling.

For each profile, report:

- raw formal-setup hits;
- downstream counterfactual candidates;
- triggered and resolved counts;
- mean and median transaction-cost-adjusted net return;
- positive-net-return rate, defined as `net_return > 0`;
- stop-first rate;
- mean MFE and MAE;
- exact-date overlap with the v5 actionable-winner cohort; and
- rejection counts after the counterfactual step.

Stock-date observations are overlapping and are not represented as independent
samples. An intraday high without a valid plan trigger is not a strategy
success.

## Qualification and Ranking

A sector profile qualifies for a retrospective freeze only when the combined
research rows contain at least 10 triggered outcomes with resolved net returns
and satisfy all of:

- mean net return greater than zero;
- positive-net-return rate at least 50%; and
- stop-first rate no greater than 40%.

Qualifying sector profiles are ranked by:

1. higher mean net return;
2. higher positive-net-return rate;
3. lower stop-first rate; and
4. lexical profile identifier.

Market profiles are excluded before qualification regardless of their metrics.
If no sector profile qualifies, write an explicit empty freeze. Never lower a
threshold or add a fallback profile to fill the freeze.

## Retrospective Research and Prospective Evidence

The July 20 through August 7 signal windows and outcomes through August 14 have
already been inspected. They are therefore retrospective research evidence and
must not be called an independent holdout.

The retrospective workflow aggregates these three five-date windows:

- July 20–24, outcomes through July 31;
- July 27–31, outcomes through August 7; and
- August 3–7, outcomes through August 14.

The resulting sector-profile freeze is identified as retrospective and grants
only zero-share forward-screen eligibility.

Prospective evidence starts on the first trading date after the freeze. The
user triggers it manually. At least 20 different forward signal dates and at
least 20 resolved forward plans are required before deciding whether a profile
deserves a broader historical validation. This condition does not promote the
profile to the formal strategy.

## Manual Workflow

The workflow has four explicit stages and no scheduler integration.

### `research`

Run a retrospective point-in-time window, evaluate every supported profile,
and write immutable JSON and Markdown evidence.

### `freeze`

Consume exactly the three approved retrospective research windows, exclude
market profiles, aggregate raw sector outcomes, apply the qualification rules,
and write an immutable freeze artifact.

### `screen`

Consume the freeze and one completed signal date. Produce zero to five
deduplicated forward candidates with trigger price, invalidation price, 2R
target, structure identity, sector failure reason, and profile rank. An empty
freeze or empty daily cohort produces an explicit empty report.

### `settle`

After five outcome sessions are available, consume an immutable screen artifact
and create a separate outcome artifact. Settlement never overwrites the signal
artifact and never changes its candidate membership or rank.

## Deduplication and Daily Ranking

The research artifact retains all raw profile hits. `screen` deduplicates by
`(signal_date, code)` and ranks eligible sector candidates by:

1. frozen profile rank;
2. higher formal setup quality;
3. larger 2R-space buffer;
4. higher five-day average amount; and
5. normalized stock code.

Retain at most five stocks per signal date. Do not fill missing slots with a
failed, diagnostic-only, or unfrozen profile.

## Artifacts and Identity

Use a separate immutable schema:

```text
buy-point-gate-shadow-v1
```

Artifacts live under an ignored research output directory. Identity fields
include:

- schema and stage;
- signal dates and outcome cutoff where applicable;
- formal rule and policy hash;
- exact six-profile matrix hash;
- point-in-time input fingerprint;
- linked v5 case identity for retrospective research;
- freeze hash for screen and settlement;
- parent screen identity for settlement; and
- evaluator and transaction-cost versions.

Existing artifacts are opened exclusively and accepted only when their bytes
match the deterministic content for the same identity. Signal and settlement
artifacts are separate.

## Failure Handling

- Unsupported, duplicated, or reordered profile definitions fail closed.
- A row with zero or more than one supported failure reason is excluded with an
  explicit rejection stage.
- Any incomplete required signal-time fact excludes the affected date or row.
- A market profile appearing in a freeze or screen is a hard error.
- A freeze with the wrong formal policy, profile matrix, evaluator, or cost hash
  is rejected.
- A screen cannot read future outcome bars.
- Settlement requires exactly five outcome sessions after the signal date.
- A changed screen artifact cannot be settled under the original screen
  identity.
- Every executable-share field must equal zero.
- MySQL access is read-only. The LAN host override remains runtime-only and is
  never committed.

## Safety Boundaries

- Formal rule version remains `buy-point-selection-3.1.0`.
- Production `models.py`, `patterns.py`, `gates.py`, `planning.py`, sizing,
  validation, holdings, decision memory, notifications, and orders remain
  unchanged.
- No artifact can grant formal trade permission.
- No stage writes holdings, portfolio state, decision memory, notifications,
  orders, or formal selection tables.
- No cron, launchd, Docker scheduler, or other automatic trigger is added.
- Generated research and forward evidence remains ignored by Git.
- Incomplete announcement coverage remains visible and blocks any later
  promotion study.

## Testing Requirements

Tests must prove:

- the profile matrix contains exactly the two diagnostic market profiles and
  four research sector profiles;
- formal setups are required and relaxed threshold setups cannot enter;
- exactly one supported failure reason is required;
- every hard boundary remains effective;
- market rows can be evaluated but cannot freeze or screen;
- sector rows pass every unchanged downstream requirement;
- signal generation is unaffected by bars after the signal date;
- qualification boundaries are literal and an empty freeze is preserved;
- daily selection is deterministic, deduplicated, and capped at five;
- retrospective windows are exact and cannot be labeled independent holdout;
- screen artifacts contain no outcome data;
- settlement requires five later sessions and cannot change screen membership;
- immutable identities reject mismatched content; and
- every research, screen, and settlement object has zero executable shares.

Run the complete relevant buy-point regression after implementation and prove
that the production setup, gate, policy, and planning modules are unchanged.
