from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from short_term_trading.contracts.base import (
    ContractModel,
    DataStatus,
    EvidenceKind,
    MarketStatus,
    ReleaseMode,
    SignalStatus,
    utc_now,
    validate_code,
)


UTC_NOW = datetime(2026, 8, 10, 6, 30, tzinfo=timezone.utc)


class ExampleContract(ContractModel):
    code: str
    price: Decimal = Decimal("12.30")


def test_contract_has_exact_v11_schema_version_and_rejects_other_versions() -> None:
    value = ExampleContract(
        as_of=UTC_NOW,
        source="fixture",
        data_status="VALID",
        code="600000",
    )

    assert value.schema_version == "1.1"
    with pytest.raises(ValidationError):
        ExampleContract(
            schema_version="1.0",
            as_of=UTC_NOW,
            source="fixture",
            data_status="VALID",
            code="600000",
        )


def test_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ExampleContract(
            as_of=UTC_NOW,
            source="fixture",
            data_status="VALID",
            code="600000",
            extra="x",
        )


def test_contract_requires_aware_time_and_normalizes_it_to_utc() -> None:
    with pytest.raises(ValidationError):
        ExampleContract(
            as_of=datetime(2026, 8, 10, 14, 30),
            source="fixture",
            data_status="VALID",
            code="600000",
        )

    value = ExampleContract(
        as_of=datetime(2026, 8, 10, 14, 30, tzinfo=timezone(timedelta(hours=8))),
        source="fixture",
        data_status="VALID",
        code="600000",
    )
    assert value.as_of == UTC_NOW
    assert value.as_of.tzinfo is timezone.utc


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", "000001"), (" 600000 ", "600000"), ("000001.SZ", "000001")],
)
def test_validate_code_normalizes_six_digit_a_share_codes(raw: str, expected: str) -> None:
    assert validate_code(raw) == expected


@pytest.mark.parametrize("raw", ["", "60000A", "1234567", "000001.XYZ"])
def test_validate_code_rejects_malformed_codes(raw: str) -> None:
    with pytest.raises(ValueError):
        validate_code(raw)


def test_contract_serializes_decimal_as_string() -> None:
    value = ExampleContract(
        as_of=UTC_NOW,
        source="fixture",
        data_status="VALID",
        code="600000",
        price=Decimal("12.30"),
    )

    assert value.model_dump(mode="json")["price"] == "12.30"


@pytest.mark.parametrize(
    ("enum_type", "accepted"),
    [
        (DataStatus, "VALID"),
        (SignalStatus, "NO_TRADE"),
        (MarketStatus, "ALLOW"),
        (ReleaseMode, "SHADOW"),
        (EvidenceKind, "QUOTE"),
    ],
)
def test_contract_enums_accept_declared_values_and_reject_unknown_values(
    enum_type: type, accepted: str
) -> None:
    assert enum_type(accepted).value == accepted
    with pytest.raises(ValueError):
        enum_type("UNKNOWN")


def test_utc_now_returns_an_aware_utc_timestamp() -> None:
    value = utc_now()

    assert value.tzinfo is timezone.utc
