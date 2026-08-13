from __future__ import annotations

from datetime import date

import pytest

from stock_ai.limit_up_research.models import normalize_topic_pools


TRADE_DATE = date(2026, 8, 13)


def _pools():
    return {
        "zt": [
            {
                "c": "601991",
                "n": "大唐发电",
                "zdp": 10.02,
                "amount": 812_000_000,
                "lbc": 2,
                "hybk": "电力行业",
                "fbt": "093125",
                "lbt": "145702",
                "zbc": 1,
                "fund": 92_500_000,
            }
        ],
        "zb": [],
        "dt": [],
    }


def test_normalize_limit_up_fact_preserves_raw_and_board_height() -> None:
    result = normalize_topic_pools(_pools(), TRADE_DATE)

    fact = result.facts[0]
    assert (fact.pool_kind, fact.code, fact.board_height) == (
        "LIMIT_UP",
        "601991",
        2,
    )
    assert fact.amount_wan == 81_200.0
    assert fact.seal_amount_wan == 9_250.0
    assert fact.first_seal_time == "09:31:25"
    assert fact.last_seal_time == "14:57:02"
    assert fact.raw_json["c"] == "601991"


def test_normalization_rejects_missing_pool() -> None:
    with pytest.raises(ValueError, match="missing topic pool"):
        normalize_topic_pools({"zt": [], "zb": []}, TRADE_DATE)


def test_normalization_rejects_invalid_code() -> None:
    with pytest.raises(ValueError, match="invalid A-share code"):
        normalize_topic_pools(
            {"zt": [{"c": "bad", "n": "坏数据"}], "zb": [], "dt": []},
            TRADE_DATE,
        )


def test_hash_is_stable_when_source_order_changes() -> None:
    first = _pools()
    first["zt"].append({"c": "600821", "n": "金开新能", "zttj": {"ct": 1}})
    second = {**first, "zt": list(reversed(first["zt"]))}

    assert normalize_topic_pools(first, TRADE_DATE).snapshot_hash == normalize_topic_pools(
        second, TRADE_DATE
    ).snapshot_hash


def test_missing_optional_fields_are_none_and_disclosed() -> None:
    result = normalize_topic_pools(
        {"zt": [{"c": "600821", "n": "金开新能", "zttj": {"ct": 1}}], "zb": [], "dt": []},
        TRADE_DATE,
    )

    fact = result.facts[0]
    assert fact.board_height == 1
    assert fact.reopen_count is None
    assert "reopen_count" in fact.missing_fields
