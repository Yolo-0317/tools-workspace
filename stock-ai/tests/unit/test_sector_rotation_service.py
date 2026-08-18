from datetime import date, datetime, timedelta, timezone

from stock_ai.sector_rotation.models import RawSectorRow, RotationPolicy
from stock_ai.sector_rotation.repository import MemoryRotationRepository
from stock_ai.sector_rotation.service import detect_sector_rotation


class FixtureProvider:
    warnings: tuple[str, ...] = ()

    def fetch_ranked_sectors(self, limit: int):
        names = ("半导体", "机器人", "黄金", "零售", "化工", "储能")
        return tuple(
            RawSectorRow(f"BK{index}", name, index, 3 - index / 10,
                         f"600{index:03d}", f"样本{index}", 4)
            for index, name in enumerate(names[:limit], start=1)
        )

    def fetch_chain_members(self, chains):
        return {
            board: [
                {"code": f"60{index:04d}", "name": f"样本{index}", "price": 11,
                 "change_pct": 2 + index / 10, "amount": 240000 + index,
                 "turnover_rate": 2}
                for index in range(offset, offset + 4)
            ]
            for offset, board in enumerate(
                [code for chain in chains for code in chain.raw_sector_codes], start=1
            )
        }

    def load_daily_panel(self, codes, limit):
        start = date(2026, 5, 1)
        return {
            code: [
                {"trade_date": (start + timedelta(days=index)).isoformat(),
                 "open": 9 + index * 0.02, "high": 9.3 + index * 0.02,
                 "low": 8.8 + index * 0.02, "close": 9.1 + index * 0.02,
                 "pct_chg": 0.3, "vol": 100000, "amount": 200000 + index * 1000}
                for index in range(limit)
            ]
            for code in codes
        }

    def load_held_codes(self):
        return {"600001"}

    def load_previous_snapshots(self, chain_codes):
        return {}


def test_service_persists_and_reports_a_complete_manual_run(tmp_path) -> None:
    repository = MemoryRotationRepository()
    result = detect_sector_rotation(
        provider=FixtureProvider(), repository=repository, policy=RotationPolicy(),
        observed_at=datetime(2026, 8, 18, 14, 40, tzinfo=timezone.utc),
        edition="intraday", top_sectors=6, stocks_per_sector=10,
        output_path=tmp_path / "rotation.md",
    )

    assert len(result.chains) <= 6
    assert all(sum(c.chain_code == chain.chain_code for c in result.candidates) <= 10
               for chain in result.chains)
    assert repository.load_latest_result().run_id == result.run_id
    assert result.report_path and result.report_path.exists()


class PartialProvider(FixtureProvider):
    warnings = ("CONSTITUENTS_INCOMPLETE:BK1",)

    def fetch_ranked_sectors(self, limit: int):
        del limit
        return (RawSectorRow("BK1", "半导体", 1, 2.9, "600001", "样本1", 4),)


def test_incomplete_constituents_never_produce_formal_prices(tmp_path) -> None:
    result = detect_sector_rotation(
        provider=PartialProvider(), repository=None, policy=RotationPolicy(),
        observed_at=datetime(2026, 8, 18, 14, 40, tzinfo=timezone.utc),
        edition="intraday", top_sectors=6, stocks_per_sector=10,
        output_path=tmp_path / "partial.md",
    )
    affected = [value for value in result.candidates if value.chain_code == "semiconductors"]

    assert affected
    assert all(not value.formal_eligible and value.levels is None for value in affected)
