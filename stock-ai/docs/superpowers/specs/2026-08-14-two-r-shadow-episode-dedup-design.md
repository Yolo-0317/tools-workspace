# 2R Conditional Shadow and Opportunity Deduplication Design

## Status

Approved in conversation on 2026-08-14. This document is awaiting written-spec review before implementation planning.

## Purpose

Extend the short-window buy-point case review with two research-only capabilities:

1. merge overlapping signals for the same stock into one executable opportunity so repeated daily signals do not inflate outcome counts; and
2. isolate a conservative conditional 2R shadow cohort that still has at least 1.5R room to the nearest known resistance.

This extension diagnoses whether the current 2R gate is suppressing useful opportunities. It does not change rule version `buy-point-selection-3.1.0`, formal candidate eligibility, portfolio state, decision memory, or order execution.

## Non-Goals

- Do not relax the production 2R gate.
- Do not create a new live-selection mode or executable plan.
- Do not calibrate probabilities or claim profitability from the short case.
- Do not infer missing holdings, announcements, market data, or outcomes.
- Do not use future outcomes to decide cohort membership or select the representative signal.
- Do not add a scheduler, notification, or automatic order path.

## Opportunity Episodes

### Definition

Candidates are processed in deterministic order by signal date, normalized stock code, existing ranking key, tier, and plan structure ID. A candidate starts a new opportunity episode unless an existing episode for the same normalized six-digit stock code has a representative plan whose `valid_through_trade_date` is on or after the candidate's signal date.

An overlapping candidate belongs to that existing episode regardless of setup type or tier. This reflects the operational constraint that the first plan is still active and the same stock cannot be counted as a new independent opportunity merely because another detector or tier emits it on the next day.

### Representative and Members

- The first chronological candidate is the representative.
- The representative's original setup, signal date, price plan, tier, and outcome remain unchanged.
- Later overlapping signals are recorded as episode members but are not evaluated as independent trades.
- A signal after the representative plan's validity date starts a new episode.
- Episodes never merge across stock codes.
- No outcome information participates in episode construction.

The report retains raw candidate and raw outcome rows for audit compatibility. It adds episode rows and episode-level metrics as the primary non-duplicated comparison.

## Conditional 2R Shadow Cohort

### Admission

A representative opportunity enters `TWO_R_CONDITIONAL_SHADOW` only when all conditions are true at the representative signal date:

- the candidate is an existing one-soft-gate near miss;
- its only failed gate is `INSUFFICIENT_TWO_R_SPACE`;
- all hard gates and all other soft gates passed;
- the diagnostic plan exists and remains zero-share;
- the nearest known resistance and risk distance are finite and positive; and
- effective resistance room is at least 1.5R and below the production requirement of 2R.

The signal-time metric is:

```text
effective_resistance_r = (nearest_resistance - trigger_price) / risk_distance
```

Admission therefore requires:

```text
1.5 <= effective_resistance_r < 2.0
```

The lower boundary is inclusive. Values below 1.5, values at or above 2.0, malformed values, and missing metrics are excluded. A candidate already passing the production 2R gate remains in its existing strict tier and is not duplicated into this cohort.

### Ranking and Safety

The cohort reuses the existing deterministic near-miss ranking: boundary deviation, descending setup quality, descending five-day average amount, and code. No new setup-quality cutoff is introduced because the observed successful case opportunities had setup quality around 0.32 to 0.36; a generic 0.5 threshold would discard them without independent evidence.

Every cohort candidate has `executable_shares = 0`, `trade_permission = NO-TRADE`, and `CASE_ANALYSIS_ONLY` status. Cohort membership cannot create a formal plan, order, position event, holding mutation, promotion artifact, or decision-memory entry.

## Data Flow

1. The existing point-in-time replay creates strict-shadow and one-soft-gate near-miss candidates.
2. A pure classifier derives `effective_resistance_r` from signal-time trace metrics and the frozen diagnostic plan.
3. A pure episode builder groups overlapping candidates without looking at outcomes.
4. Raw candidates continue through the existing outcome evaluator for backward-compatible audit rows.
5. Episode representatives reuse their matching raw outcomes; the evaluator does not simulate a second plan.
6. The report renders raw-layer metrics, episode-layer metrics, and the conditional 2R cohort side by side.

No database schema change is required. The MySQL loader remains read-only.

## Models and Interfaces

The research model adds two immutable values:

```python
@dataclass(frozen=True)
class OpportunityEpisode:
    episode_id: str
    representative: CaseCandidate
    member_signal_dates: tuple[date, ...]
    member_tiers: tuple[str, ...]


@dataclass(frozen=True)
class ConditionalShadowDecision:
    admitted: bool
    tier: str | None
    effective_resistance_r: Decimal | None


@dataclass(frozen=True)
class ConditionalShadowOpportunity:
    episode_id: str
    candidate: CaseCandidate
    effective_resistance_r: Decimal
```

Pure functions expose the behavior:

```python
def classify_conditional_two_r_shadow(
    candidate: CaseCandidate,
    trace: GateTrace,
) -> ConditionalShadowDecision: ...


def build_opportunity_episodes(
    candidates: Sequence[CaseCandidate],
) -> tuple[OpportunityEpisode, ...]: ...


def build_conditional_two_r_shadow(
    episodes: Sequence[OpportunityEpisode],
    traces: Mapping[tuple[date, str], GateTrace],
) -> tuple[ConditionalShadowOpportunity, ...]: ...
```

Episode identity is deterministic from the representative code, signal date, and plan structure ID. It is not a database identifier and does not authorize execution.

`CaseOutcome` adds the representative plan's `structure_id` so an episode can reuse the exact raw outcome when more than one setup exists for a stock on the same signal date. `CaseReview` adds immutable `episodes: tuple[OpportunityEpisode, ...]` and `conditional_two_r_shadow: tuple[ConditionalShadowOpportunity, ...]` fields with empty defaults so existing injected test fixtures and non-case selection code remain compatible.

## Reporting

The JSON schema advances from `buy-point-case-review-v1` to `buy-point-case-review-v2`. Existing fields remain present and keep their meaning. New sections include:

- `opportunity_episodes`: representative signal, member dates and tiers, representative outcome, and episode identity;
- `conditional_two_r_shadow`: admitted episode identities and signal-time `effective_resistance_r`;
- raw and episode counts;
- raw and episode resolved-success numerators and denominators;
- triggered, expired, stop-first, average net return, MFE, and MAE metrics at episode level; and
- conditional-cohort episode metrics beside strict-shadow and all-near-miss metrics.

The Markdown report labels raw signal statistics as potentially duplicated and uses episode statistics for strategy comparison. All rates show raw numerators and denominators. Incomplete signal dates keep recall unavailable and remain explicitly listed.

Because the report content changes while the case window and policy hash remain the same, case identity also includes the report schema version. A v2 report therefore creates a new immutable artifact instead of colliding with the existing v1 revision.

## Integrity and Failure Handling

- Episode construction fails closed on an empty or invalid representative plan validity date.
- A trace that is absent, contains multiple failures, or lacks required 2R metrics cannot enter the conditional cohort.
- Duplicate candidate rows with identical code, signal date, tier, and plan structure ID collapse deterministically inside one episode.
- A representative without an outcome whose code, signal date, tier, and structure ID all match remains auditable but is excluded from resolved outcome denominators.
- `PENDING` outcomes remain excluded from success and failure denominators.
- Missing point-in-time coverage preserves `CASE_ANALYSIS_ONLY / NO-TRADE` and cannot be converted to a valid zero-candidate day.
- Raw rows are never deleted from JSON merely because they were deduplicated at the opportunity layer.

## Tests

Unit tests must prove:

- same-code signals whose dates overlap the first plan's validity become one episode;
- a same-code signal after validity becomes a new episode;
- different codes never merge;
- setup type and tier changes do not create a new episode while the first plan remains active;
- episode construction is independent of outcomes and preserves the earliest plan;
- exactly one `INSUFFICIENT_TWO_R_SPACE` failure with 1.5R room is admitted;
- 1.5R is inclusive and 2.0R is excluded;
- below-1.5R, missing metrics, malformed metrics, multiple failures, and non-2R failures are rejected;
- conditional candidates remain zero-share and cannot enter a formal tier;
- episode outcomes reuse the representative raw outcome and do not run a second simulation;
- v2 payload ordering and identity are deterministic;
- v1 fields remain available in the v2 payload;
- Markdown clearly separates raw signals from deduplicated opportunities; and
- no production plan, memory, holding, profile, or order mutation occurs.

## Acceptance Criteria

The extension is complete when the same short-window case can be regenerated as an immutable v2 revision that:

- counts overlapping daily signals as one opportunity;
- shows which raw signals were merged;
- reports the conditional 1.5R-to-2R cohort using only signal-time facts;
- compares cohort outcomes at the episode level;
- preserves every raw audit row;
- remains `CASE_ANALYSIS_ONLY / NO-TRADE`; and
- leaves all production selection thresholds and execution paths unchanged.
