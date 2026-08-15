# Buy-Point Case Revision Identity Design

## Goal

Allow one logical v5 buy-point case window to produce multiple immutable, auditable revisions when point-in-time inputs are repaired, while preserving deterministic reruns and backward compatibility with existing artifacts.

## Confirmed Problem

The current `case_identity` hashes only schema, signal dates, outcome cutoff, rule version, and policy hash. Rebuilding the same window after announcement coverage changes therefore targets the same filename. The exclusive writer correctly refuses to overwrite the old artifact, but the workflow cannot record the corrected revision. Writing to another directory would not solve the lineage collision because both payloads would still expose the same identity.

## Identity Model

Two identities have different responsibilities:

- `case_identity` remains the stable logical identity of a case window under one schema, rule version, and policy hash.
- `revision_identity` identifies one exact normalized report revision. It is the first 16 hexadecimal characters of SHA-256 over the canonical JSON payload before `revision_identity` is inserted, using sorted keys and compact separators.

The canonical payload already contains every serialized candidate, outcome, winner, diagnostic, metric, completeness flag, and safety field. Any material input repair that changes report evidence therefore changes `revision_identity`. Reordering equivalent in-memory inputs does not change it because all payload collections are deterministically sorted before hashing.

## Artifact Behavior

- Add `revision_identity` to new `buy-point-case-review-v5` JSON payloads.
- Keep `case_identity` unchanged for logical grouping and compatibility.
- Use `revision_identity` as the filename suffix for new JSON and Markdown revisions.
- Rewriting identical content resolves to the same paths and verifies byte-for-byte equality.
- Different content for the same logical case resolves to different paths; old files remain untouched.
- Do not delete, rename, or edit existing v5 artifacts.

## Consumer Compatibility

`load_v5_recall_lineage` validates `revision_identity` when present and uses it as downstream lineage. Existing v5 artifacts without the field remain valid and fall back to `case_identity`.

For a new artifact, the loader recomputes the revision hash from the payload after removing `revision_identity`. Missing, malformed, or mismatched new revision identities fail closed. The existing schema, safety labels, window validation, daily-winner reconciliation, and recursive zero-share requirements remain unchanged.

The existing `V5RecallLineage.case_identity` attribute remains unchanged at the Python interface boundary for compatibility, but its value becomes the strongest available artifact lineage: `revision_identity` for new revisions and `case_identity` for legacy v5 artifacts.

## Files and Boundaries

- `stock_ai/buy_point_selection/case_report.py` owns canonical revision hashing, payload insertion, and revision-based filenames.
- `scripts/analysis/review_buy_point_threshold_shadows.py` owns strict v5 lineage loading and backward-compatible fallback.
- `tests/unit/test_buy_point_case_report.py` proves deterministic identities, same-window distinct revisions, immutable old files, and tamper rejection helpers where appropriate.
- `tests/unit/test_review_buy_point_threshold_shadows_cli.py` proves new revision lineage preference, hash validation, and legacy fallback.

Do not modify production selection rules, setup or gate thresholds, portfolio state, advisor memory, notifications, schedules, orders, or MySQL data in this code task.

## Error Handling

- A new payload whose `revision_identity` is not 16 lowercase hexadecimal characters fails validation.
- A new payload whose recomputed canonical hash differs from `revision_identity` fails validation.
- A content mismatch at an already existing revision path remains an immutable-content error.
- Legacy v5 artifacts without `revision_identity` continue through existing validation and use `case_identity` as lineage.

## Testing and Acceptance

The change is accepted only when:

- the same logical case with identical normalized content produces identical case and revision identities;
- changing only risk coverage or another serialized evidence field preserves `case_identity` but changes `revision_identity` and output paths;
- both immutable revisions coexist and the first file remains byte-for-byte unchanged;
- tampering with a new revision payload is rejected by the v5 lineage loader;
- an existing legacy v5 fixture without `revision_identity` still loads with its original lineage;
- focused case-report and v5-lineage tests pass;
- the complete buy-point unit regression passes; and
- the corrected July 20–24 case can be regenerated as a new local ignored revision without overwriting the old artifact.
