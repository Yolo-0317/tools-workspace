from sqlalchemy import create_engine, text

from scripts.tools.portfolio_db import load_stock_daily_panel
from stock_ai.sector_rotation.providers import ProductionRotationDataProvider


def test_provider_converts_objective_rows_without_inventing_missing_amount() -> None:
    provider = ProductionRotationDataProvider(
        sector_fetcher=lambda **_: [
            {"board_code": "BK1", "sector": "铜", "sector_chg": 1.2, "code": "600001",
             "leader_name": "甲", "leader_chg": 5.0}
        ],
        constituent_fetcher=lambda *_args, **_kwargs: [
            {"code": "600001", "name": "甲", "price": 10.2, "change_pct": 5.0,
             "amount": None, "turnover_rate": 2.1}
        ],
        daily_loader=lambda *_args, **_kwargs: {},
        holdings_loader=lambda: set(),
    )

    rows = provider.fetch_ranked_sectors(20)
    members = provider.fetch_chain_members(rows)

    assert rows[0].sector_name == "铜"
    assert members["BK1"][0]["amount"] is None


def test_batch_daily_loader_returns_ascending_bars_per_code() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE stock_daily (ts_code TEXT, trade_date TEXT, open REAL, high REAL, "
            "low REAL, close REAL, pct_chg REAL, vol REAL, amount REAL)"
        ))
        for code in ("000001", "600001"):
            for day in ("2026-08-15", "2026-08-18"):
                connection.execute(text(
                    "INSERT INTO stock_daily VALUES (:code,:day,10,11,9,10.5,1,100,200)"
                ), {"code": code, "day": day})

    panel = load_stock_daily_panel(["600001", "000001"], limit=60, engine=engine)

    assert list(panel) == ["000001", "600001"]
    assert panel["000001"][0]["trade_date"] < panel["000001"][-1]["trade_date"]
