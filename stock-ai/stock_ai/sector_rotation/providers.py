from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from scripts.tools.fetch_eastmoney_quotes import (
    fetch_hot_industry_board_rows_opencli,
    fetch_industry_board_constituents,
)
from scripts.tools.portfolio_db import load_holding_codes, load_stock_daily_panel

from .models import NormalizedChain, RawSectorRow


class RotationDataProvider(Protocol):
    def fetch_ranked_sectors(self, limit: int) -> tuple[RawSectorRow, ...]: ...
    def fetch_chain_members(self, chains: Sequence[RawSectorRow | NormalizedChain]) -> dict[str, list[dict[str, Any]]]: ...
    def load_daily_panel(self, codes: Sequence[str], limit: int) -> dict[str, list[dict[str, Any]]]: ...
    def load_held_codes(self) -> set[str]: ...
    def load_previous_snapshots(self, chain_codes: Sequence[str]) -> Mapping[str, Sequence[Any]]: ...


class ProductionRotationDataProvider:
    def __init__(
        self,
        *,
        sector_fetcher: Callable[..., list[dict[str, Any]]] = fetch_hot_industry_board_rows_opencli,
        constituent_fetcher: Callable[..., list[dict[str, Any]]] = fetch_industry_board_constituents,
        daily_loader: Callable[..., dict[str, list[dict[str, Any]]]] = load_stock_daily_panel,
        holdings_loader: Callable[[], set[str]] = load_holding_codes,
        snapshot_loader: Callable[[Sequence[str]], Mapping[str, Sequence[Any]]] | None = None,
    ) -> None:
        self._sector_fetcher = sector_fetcher
        self._constituent_fetcher = constituent_fetcher
        self._daily_loader = daily_loader
        self._holdings_loader = holdings_loader
        self._snapshot_loader = snapshot_loader or (lambda _codes: {})
        self._warnings: list[str] = []

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(self._warnings)

    def fetch_ranked_sectors(self, limit: int) -> tuple[RawSectorRow, ...]:
        raw = self._sector_fetcher(top_n=limit)
        return tuple(
            RawSectorRow(
                board_code=str(value.get("board_code") or "").strip().upper(),
                sector_name=str(value.get("sector") or "").strip(),
                rank=index,
                change_pct=value.get("sector_chg") or 0,
                leader_code=str(value.get("code") or "").strip(),
                leader_name=str(value.get("leader_name") or "").strip(),
                leader_change_pct=value.get("leader_chg") or 0,
            )
            for index, value in enumerate(raw, start=1)
        )

    def fetch_chain_members(
        self, chains: Sequence[RawSectorRow | NormalizedChain]
    ) -> dict[str, list[dict[str, Any]]]:
        board_codes: list[str] = []
        for value in chains:
            if isinstance(value, RawSectorRow):
                board_codes.append(value.board_code)
            else:
                board_codes.extend(value.raw_sector_codes)
        output: dict[str, list[dict[str, Any]]] = {}
        for board_code in dict.fromkeys(board_codes):
            rows = self._constituent_fetcher(board_code)
            output[board_code] = [dict(row) for row in rows]
            if not rows:
                self._warnings.append(f"CONSTITUENTS_INCOMPLETE:{board_code}")
        return output

    def load_daily_panel(self, codes: Sequence[str], limit: int) -> dict[str, list[dict[str, Any]]]:
        return self._daily_loader(codes, limit=limit)

    def load_held_codes(self) -> set[str]:
        return {str(value).zfill(6) for value in self._holdings_loader()}

    def load_previous_snapshots(self, chain_codes: Sequence[str]) -> Mapping[str, Sequence[Any]]:
        return self._snapshot_loader(chain_codes)
