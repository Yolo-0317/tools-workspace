from __future__ import annotations

import importlib.util
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from stock_ai.buy_point_selection.models import BuyPointBar, MarketSnapshot, SelectionPolicy
from stock_ai.buy_point_selection.planning import RiskBudget
from stock_ai.buy_point_selection.reference_data import (
    ReferenceCoverage,
    SectorMembership,
)
from stock_ai.buy_point_selection.service import LegacyShadow


SCRIPT = Path(__file__).parents[3] / "a-share-short-term-trading" / "scripts" / "select_short_term_candidates.py"
SPEC = importlib.util.spec_from_file_location("buy_point_full_universe_cli", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self.rows)


class _Connection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, statement, parameters):
        self.calls.append((str(statement), parameters))
        return _Rows(self.rows)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class _Engine:
    def __init__(self, rows):
        self.connection = _Connection(rows)

    def connect(self):
        return self.connection


def test_panel_loader_uses_one_bounded_query_and_keeps_latest_120_main_board_bars() -> None:
    """Catches N+1 symbol queries or ChiNext rows entering the production universe."""
    analysis_date = date(2026, 8, 10)
    rows = []
    for index in range(130):
        trade_date = analysis_date - timedelta(days=129 - index)
        rows.append(
            {
                "ts_code": "600001.SH",
                "trade_date": trade_date,
                "open": Decimal("10"),
                "high": Decimal("10.2"),
                "low": Decimal("9.8"),
                "close": Decimal("10"),
                "pct_chg": Decimal("0"),
                "amount": Decimal("150000"),
            }
        )
        rows.append({**rows[-1], "ts_code": "300001.SZ"})
    engine = _Engine(rows)
    panel = MODULE.load_main_board_panel(engine, analysis_date)
    assert len(engine.connection.calls) == 1
    statement, parameters = engine.connection.calls[0]
    assert "BETWEEN :start_date AND :analysis_date" in statement
    assert parameters["analysis_date"] == analysis_date
    assert set(panel) == {"600001"}
    assert len(panel["600001"]) == 120
    assert panel["600001"][-1].trade_date == analysis_date


def _platform_bars(code_offset: int = 0) -> tuple[BuyPointBar, ...]:
    start = date(2026, 4, 1)
    closes = [Decimal("9.60") + Decimal(index) * Decimal("0.01") for index in range(30)]
    closes.extend(
        Decimal(value)
        for value in (
            "9.85", "10.05", "9.90", "10.20", "9.95", "10.25", "10.00", "10.30", "10.05", "10.20",
            "9.95", "10.15", "10.00", "10.25", "10.10", "10.28", "10.12", "10.30", "10.18", "10.26",
            "10.18", "10.21", "10.20", "10.24", "10.23", "10.27", "10.25", "10.29", "10.28", "10.31",
        )
    )
    bars = []
    for index, close in enumerate(closes):
        previous = closes[index - 1] if index else close
        bar = BuyPointBar(
            trade_date=start + timedelta(days=index),
            open=close,
            high=close + Decimal("0.08"),
            low=close - Decimal("0.08"),
            close=close,
            pct_chg=(close / previous - Decimal("1")) * Decimal("100"),
            amount_qian=Decimal("120000" if index >= 55 else "150000"),
        )
        if 30 <= index < 40:
            bar = replace(bar, high=Decimal("10.42"), low=Decimal("9.75"))
        elif 40 <= index < 50:
            bar = replace(bar, high=close + Decimal("0.12"), low=close - Decimal("0.12"))
        elif index >= 50:
            bar = replace(bar, high=close + Decimal("0.06"), low=close - Decimal("0.06"))
        bars.append(bar)
    return tuple(bars)


def test_missing_point_in_time_coverage_downgrades_valid_setups_and_legacy_stays_shadow() -> None:
    """Catches technical strength or legacy research overriding missing historical facts."""
    analysis_date = _platform_bars()[-1].trade_date
    panel = {f"60000{index}": _platform_bars(index) for index in range(1, 7)}
    memberships = {
        code: SectorMembership(code, "S1", "虚构行业", date(2025, 1, 1), None, "test")
        for code in panel
    }
    shadow = LegacyShadow("600099", "旧策略", "legacy-three-up", ("RESEARCH_ONLY",))
    result = MODULE.scan_buy_point_universe(
        panel=panel,
        analysis_date=analysis_date,
        holding_codes=set(),
        risk_flags_by_code={},
        memberships=memberships,
        coverage=ReferenceCoverage(analysis_date, True, False, False),
        market_snapshot=MarketSnapshot(2, 55.0, 0.95, True),
        risk_budget=RiskBudget(Decimal("500"), Decimal("4000"), Decimal("40000")),
        account_fresh=True,
        existing_structure_ids=frozenset(),
        legacy_shadow=(shadow,),
        policy=SelectionPolicy(),
    )
    assert result.qualified == ()
    assert result.observe
    assert all("RISK_COVERAGE" in item.missing_fields for item in result.observe)
    assert result.shadow == (shadow,)


def test_symbol_without_analysis_date_bar_cannot_form_a_new_plan() -> None:
    """Catches suspended or stale symbols being evaluated as if their last bar were current."""
    last_bar_date = _platform_bars()[-1].trade_date
    analysis_date = last_bar_date + timedelta(days=1)
    panel = {f"60000{index}": _platform_bars(index) for index in range(1, 7)}
    memberships = {
        code: SectorMembership(code, "S1", "虚构行业", date(2025, 1, 1), None, "test")
        for code in panel
    }
    result = MODULE.scan_buy_point_universe(
        panel=panel,
        analysis_date=analysis_date,
        holding_codes=set(),
        risk_flags_by_code={},
        memberships=memberships,
        coverage=ReferenceCoverage(analysis_date, True, True, True),
        market_snapshot=MarketSnapshot(2, 55.0, 0.95, True),
        risk_budget=RiskBudget(Decimal("500"), Decimal("4000"), Decimal("40000")),
        account_fresh=True,
        existing_structure_ids=frozenset(),
        legacy_shadow=(),
        policy=SelectionPolicy(),
    )
    assert result.qualified == ()
    assert result.rejection_counts["LATEST_BAR_MISSING"] == 6


def test_missing_market_evidence_becomes_freeze_snapshot_instead_of_crashing() -> None:
    """Catches absent index evidence aborting the whole report instead of failing closed."""
    snapshot = MODULE.market_snapshot_from_view(
        SimpleNamespace(
            trading_date=date(2026, 8, 10),
            indexes_above_ma20=None,
            breadth_pct=None,
            amount_ratio=None,
            evidence_refs=(),
        ),
        date(2026, 8, 10),
    )
    assert not snapshot.complete
    assert snapshot.indexes_above_ma20 == 0
