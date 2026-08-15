from __future__ import annotations

from dataclasses import replace

import pytest

from stock_ai.buy_point_selection.gate_shadow_research import (
    build_gate_shadow_profiles,
    gate_profile_matrix_hash,
    matching_gate_profile,
    validate_gate_shadow_profiles,
)


def test_gate_profile_matrix_is_exact_and_market_is_diagnostic_only() -> None:
    """Catches an unsafe gate reason becoming freeze-eligible or disappearing."""
    profiles = build_gate_shadow_profiles()

    assert [value.profile_id for value in profiles] == [
        "MARKET:AMOUNT_AND_BREADTH_WEAK:DIAGNOSTIC",
        "MARKET:INDEX_AND_BREADTH_WEAK:DIAGNOSTIC",
        "SECTOR:SECTOR_AMOUNT_WEAK:BYPASS",
        "SECTOR:SECTOR_BREADTH_WEAK:BYPASS",
        "SECTOR:SECTOR_NOT_RESONATING:BYPASS",
        "SECTOR:SECTOR_RELATIVE_STRENGTH_WEAK:BYPASS",
    ]
    assert all(not value.freeze_eligible for value in profiles[:2])
    assert all(value.freeze_eligible for value in profiles[2:])
    assert len(gate_profile_matrix_hash(profiles)) == 64


def test_only_one_supported_reason_matches_a_gate_profile() -> None:
    """Catches multi-failure or hard-boundary rows entering the shadow cohort."""
    profiles = build_gate_shadow_profiles()

    assert matching_gate_profile(
        "SECTOR", ("SECTOR_BREADTH_WEAK",), profiles
    ).profile_id == "SECTOR:SECTOR_BREADTH_WEAK:BYPASS"
    assert matching_gate_profile(
        "SECTOR",
        ("SECTOR_BREADTH_WEAK", "SECTOR_AMOUNT_WEAK"),
        profiles,
    ) is None
    assert matching_gate_profile(
        "SECTOR", ("SECTOR_SAMPLE_TOO_SMALL",), profiles
    ) is None
    assert matching_gate_profile(
        "MARKET", ("MARKET_DATA_INCOMPLETE",), profiles
    ) is None


def test_profile_validation_rejects_forged_or_reordered_matrices() -> None:
    """Catches callers silently changing the approved six-profile experiment."""
    profiles = build_gate_shadow_profiles()

    with pytest.raises(ValueError, match="unsupported gate profile matrix"):
        validate_gate_shadow_profiles(tuple(reversed(profiles)))
    with pytest.raises(ValueError, match="unsupported gate profile matrix"):
        validate_gate_shadow_profiles(
            (replace(profiles[0], freeze_eligible=True), *profiles[1:])
        )
