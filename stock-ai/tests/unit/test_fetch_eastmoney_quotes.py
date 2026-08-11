from __future__ import annotations

import pytest

from scripts.tools.fetch_eastmoney_quotes import index_secid


@pytest.mark.parametrize(
    ("code", "expected"),
    [("000001", "1.000001"), ("399001", "0.399001"), ("000688", "1.000688")],
)
def test_index_secid_uses_the_exchange_specific_market_identifier(code: str, expected: str) -> None:
    assert index_secid(code) == expected


def test_index_secid_rejects_an_unconfigured_security_code() -> None:
    with pytest.raises(ValueError, match="不支持的大盘指数"):
        index_secid("603011")
