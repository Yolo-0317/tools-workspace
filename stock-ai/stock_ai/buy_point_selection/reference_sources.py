"""Typed boundaries for external point-in-time reference providers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class IndustryCategory:
    code: str
    parent_code: str
    name: str
    level: int
    terminated_on: date | None


@dataclass(frozen=True)
class IndustryChange:
    code: str
    changed_on: date
    standard: str
    industry_code: str


@dataclass(frozen=True)
class SecurityStatus:
    code: str
    name: str
    trade_status: str
    trade_date: date


@dataclass(frozen=True)
class Announcement:
    code: str
    announcement_id: str
    title: str
    published_at: datetime | None
    official_url: str


@dataclass(frozen=True)
class AnnouncementPage:
    records: tuple[Announcement, ...]
    total_count: int
    page_no: int
    page_size: int
    page_count: int


class ProviderFailure(RuntimeError):
    """A provider error reduced to fields safe for audit and CLI output."""

    def __init__(self, provider: str, operation: str, error_code: str) -> None:
        self.provider = provider
        self.operation = operation
        self.error_code = error_code
        super().__init__(f"{provider}:{operation}:{error_code}")


class ReferenceProvider(Protocol):
    provider_name: str


class CninfoReferenceSource(ReferenceProvider, Protocol):
    def fetch_industry_categories(self) -> tuple[IndustryCategory, ...]: ...

    def fetch_industry_changes(
        self, code: str, start: date, end: date
    ) -> tuple[IndustryChange, ...]: ...

    def fetch_announcement_page(self, day: date, page_no: int) -> AnnouncementPage: ...


class BaoStockReferenceSource(ReferenceProvider, Protocol):
    def fetch_security_statuses(self, day: date) -> tuple[SecurityStatus, ...]: ...
