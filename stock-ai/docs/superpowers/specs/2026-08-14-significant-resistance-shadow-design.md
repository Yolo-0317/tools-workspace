# Significant Resistance Shadow Comparison Design

## Status

Approved in conversation on 2026-08-14. This document is awaiting written-spec review before implementation planning.

## Purpose

Extend the read-only short-window case review with a point-in-time comparison of three resistance definitions. The comparison tests whether the production `nearest_resistance_above` rule mistakes ordinary historical highs for meaningful resistance.

The first deduplicated case produced 15 representative opportunities rejected only for `INSUFFICIENT_TWO_R_SPACE`. Every opportunity had less than 1R of room under the legacy rule; the two successful opportunities had approximately 0.06R and 0.13R. That distribution cannot distinguish winners from losers and indicates a resistance-definition problem rather than a useful 1.5R threshold boundary.

This feature produces research evidence only. It does not modify `nearest_resistance_above`, `build_price_plan`, rule version `buy-point-selection-3.1.0`, formal candidate eligibility, position sizing, decision memory, or execution.

## Non-Goals

- Do not replace or bypass the production 2R gate.
- Do not admit a candidate to a formal or executable tier.
- Do not select model parameters from outcome-week winners or losses.
- Do not add probability calibration, promotion, scheduling, notification, or orders.
- Do not infer missing bars, holdings, announcements, market state, or outcomes.
- Do not claim one short case proves a profitable resistance definition.

## Comparison Universe

Profiles are computed only for deduplicated opportunity representatives whose raw candidate:

- is a zero-share `NEAR_MISS`;
- has `soft_reason == "INSUFFICIENT_TWO_R_SPACE"`;
- has a finite positive trigger price and risk distance; and
- has at least 60 point-in-time daily bars ending on the representative signal date.

Every calculation uses bars whose `trade_date <= signal_date`. Outcome bars cannot participate in resistance detection, clustering, ranking, or pass/fail labels.

## Resistance Variants

All variants inspect the final 60 signal-time bars and consider only resistance levels strictly above the representative trigger price.

### Legacy any-high

The legacy level is the minimum historical daily high above the trigger:

```text
legacy_level = min(bar.high for last_60_bars if bar.high > trigger)
```

This reproduces the current production rule for comparison only. The implementation continues to call or exactly reuse `nearest_resistance_above`; it does not fork the production formula.

### Local pivot high

A bar is a local pivot high when it has two earlier and two later bars within the signal-time window and:

- its high is greater than or equal to all four neighboring highs;
- it is strictly greater than at least one of the two earlier highs; and
- it is strictly greater than at least one of the two later highs.

The pivot level is the minimum qualifying pivot high above the trigger. End bars without two neighbors on both sides cannot be pivots. Equal double tops remain eligible when each top still dominates at least one neighbor on both sides.

### Repeated pivot cluster

Repeated resistance starts from the local pivot set. Two pivots belong to the same cluster when:

- their dates are separated by at least three trading sessions; and
- their highs differ by no more than the fixed point-in-time tolerance.

The tolerance is:

```text
tolerance = max(0.5 * ATR14, 0.005 * trigger_price)
```

A repeated cluster requires at least two distinct pivot dates. To make clustering deterministic, sort pivots by high and then date, enumerate every contiguous price-sorted window whose `max(high) - min(high) <= tolerance`, and retain only maximal windows whose member dates are pairwise separated by at least three trading-session indexes. Its level is the arithmetic mean of the clustered pivot highs. When more than one qualifying cluster lies above the trigger, select the lowest cluster mean; ties use the lexicographically earliest tuple of member dates. The report records its touch count.

This fixed definition is applied unchanged across setup types and cases. It is not tuned against the first case outcomes.

## Variant Metrics

For each available level:

```text
effective_resistance_r = (resistance_level - trigger_price) / risk_distance
passes_two_r = resistance_level >= target_2r
```

When any variant has no level, the profile records `level = null`, `effective_resistance_r = null`, and `passes_two_r = true`, meaning no resistance of that variant was found inside the 60-bar point-in-time window. The legacy function's `Decimal("Infinity")` result is normalized to this null representation. This is a research label only and cannot create a plan.

Malformed, non-finite, non-positive, or incomplete inputs produce `profile_complete = false`. An incomplete profile cannot be counted as passing any variant.

## Setup-Aware Comparison

The report groups representative opportunities by existing setup type:

- `PRE_BREAKOUT`;
- `FIRST_LAUNCH_PULLBACK`; and
- `TREND_PULLBACK`.

For each setup type and resistance variant, it reports:

- complete profile count;
- variant-pass count;
- triggered representative count among variant-pass opportunities;
- resolved and successful representative outcomes;
- stop-first count;
- mean fee-adjusted net return for outcomes with a net return;
- mean MFE and MAE; and
- raw opportunity codes and episode IDs for audit.

The comparison never ranks variants as promoted, profitable, or production-ready. Zero denominators remain explicit zeros or null means rather than synthetic percentages.

## Architecture

Create a focused research module:

```text
stock_ai/buy_point_selection/resistance_research.py
```

It contains no database, browser, reporting, execution, or production-plan code. It consumes immutable bars and a frozen `CaseCandidate`, and returns immutable profile values.

```python
@dataclass(frozen=True)
class ResistanceVariantProfile:
    variant: str
    level: Decimal | None
    effective_resistance_r: Decimal | None
    passes_two_r: bool
    touch_count: int


@dataclass(frozen=True)
class SignificantResistanceProfile:
    episode_id: str
    code: str
    signal_date: date
    structure_id: str
    setup_type: str
    atr14: Decimal
    tolerance: Decimal
    complete: bool
    variants: tuple[ResistanceVariantProfile, ...]


def analyze_significant_resistance(
    episode: OpportunityEpisode,
    bars: Sequence[BuyPointBar],
) -> SignificantResistanceProfile: ...
```

The runtime computes profiles after episode construction, using `bars_by_code` already loaded from MySQL. `CaseReview` adds `resistance_profiles: tuple[SignificantResistanceProfile, ...] = ()` so existing fixtures and non-case consumers remain compatible.

## Data Flow

1. Existing point-in-time replay creates raw near misses and traces.
2. Existing episode construction selects the earliest active representative without outcomes.
3. The runtime truncates each representative's bar history at its signal date.
4. The research module computes legacy, pivot, and repeated-cluster profiles.
5. Existing representative outcomes are joined by code, signal date, tier, and `structure_id`.
6. The report compares variants and setup types without re-running a trade simulation.

The MySQL and external reference paths remain read-only. No additional market-data source is required.

## Reporting and Immutability

The JSON schema advances to `buy-point-case-review-v3`, which participates in case identity. Existing v2 and v1 artifacts remain immutable.

The v3 payload preserves every existing field and adds:

- `resistance_profiles` with all per-episode input metrics and variant results;
- `resistance_comparison` grouped by setup type and variant; and
- explicit profile completeness counts.

The Markdown report adds `显著阻力影子对照`. It explains that variant passes are hypothetical research labels with zero executable shares and cannot authorize a production plan.

Generated JSON and Markdown stay under the ignored case-output directory and are not committed.

## Integrity and Failure Handling

- Fewer than 60 signal-time bars makes the profile incomplete.
- The final bounded bar must equal the representative signal date; otherwise the profile is incomplete.
- Duplicate trade dates, non-positive prices, non-finite ATR, or non-positive risk distance make the profile incomplete.
- Pivot detection cannot inspect bars after the signal date.
- Repeated clusters require distinct dates and the exact fixed tolerance formula.
- A missing significant resistance is different from an incomplete profile: missing resistance passes the research variant; incomplete data does not.
- Missing exact representative outcomes exclude the opportunity from resolved outcome denominators but retain its profile row.
- All profile candidates keep `executable_shares = 0`, `CASE_ANALYSIS_ONLY`, and `NO-TRADE`.

## Tests

Unit tests must prove:

- legacy output matches `nearest_resistance_above` for the same bounded bars;
- future bars never change a signal-date profile;
- a valid 2-left/2-right pivot is detected;
- endpoint highs and one-sided highs are not pivots;
- an equal double top can create two pivots when each dominates neighboring bars;
- repeated pivots inside tolerance and at least three sessions apart form one cluster;
- pivots too close in time or outside tolerance do not form a repeated cluster;
- the lowest qualifying cluster above trigger is selected deterministically;
- no pivot or repeated cluster produces `level = null` and a research pass;
- incomplete input never produces a research pass;
- effective R and the 2R boundary are correct at, below, and above 2R;
- only deduplicated `INSUFFICIENT_TWO_R_SPACE` representatives receive profiles;
- exact representative outcomes are reused without a second simulation;
- setup-type comparison numerators, denominators, stop counts, and means use only variant-pass opportunities;
- v3 identity differs from v2 and preserves all v2 fields; and
- no formal plan, memory, holding, profile-promotion, or order mutation occurs.

## Acceptance Criteria

The feature is complete when the August short-window case can be regenerated as an immutable v3 revision that:

- displays legacy, pivot, and repeated-cluster resistance for every complete 2R near-miss episode;
- proves all computations use signal-time bars only;
- compares hypothetical 2R passes by setup type and representative outcomes;
- preserves every raw and v2 audit row;
- remains `CASE_ANALYSIS_ONLY / NO-TRADE`; and
- leaves production resistance detection and formal selection behavior unchanged.
