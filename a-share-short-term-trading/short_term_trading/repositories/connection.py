"""Shared SQLAlchemy connection and serialization helpers."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import json
from typing import Any, Iterator, Mapping, TypeVar

from pydantic import BaseModel
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import Connection


DatabaseHandle = Engine | Connection
ModelT = TypeVar("ModelT", bound=BaseModel)


def create_mysql_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("database timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("JSON timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def json_dumps(value: Any) -> str:
    return json.dumps(_json_value(value), ensure_ascii=False, separators=(",", ":"))


def contract_values(model: BaseModel, json_fields: Mapping[str, str] | None = None) -> dict[str, Any]:
    values = model.model_dump(mode="python")
    for field, column in (json_fields or {}).items():
        values[column] = json_dumps(values.pop(field))
    for key, value in tuple(values.items()):
        if isinstance(value, Enum):
            values[key] = value.value
        elif isinstance(value, datetime):
            values[key] = utc_naive(value)
    return values


def restore_contract(
    model_type: type[ModelT],
    row: Mapping[str, Any],
    json_fields: Mapping[str, str] | None = None,
) -> ModelT:
    values = dict(row)
    for field, column in (json_fields or {}).items():
        raw = values.pop(column)
        values[field] = json.loads(raw) if isinstance(raw, str) else raw
    allowed = model_type.model_fields
    for key, value in tuple(values.items()):
        if key not in allowed:
            values.pop(key)
        elif isinstance(value, datetime) and value.tzinfo is None:
            values[key] = value.replace(tzinfo=timezone.utc)
    return model_type.model_validate(values)


@contextmanager
def write_connection(handle: DatabaseHandle) -> Iterator[Connection]:
    if isinstance(handle, Connection) or (
        hasattr(handle, "execute") and not hasattr(handle, "begin")
    ):
        yield handle  # type: ignore[misc]
        return
    with handle.begin() as connection:  # type: ignore[union-attr]
        yield connection


@contextmanager
def read_connection(handle: DatabaseHandle) -> Iterator[Connection]:
    if isinstance(handle, Connection) or hasattr(handle, "execute"):
        yield handle  # type: ignore[misc]
        return
    with handle.connect() as connection:  # type: ignore[union-attr]
        yield connection
