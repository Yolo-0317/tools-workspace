from pathlib import Path


SQL = Path(__file__).parents[3] / "stock-mysql/sql/014_limit_up_research.sql"


def test_limit_up_research_schema_declares_four_idempotent_tables() -> None:
    ddl = SQL.read_text(encoding="utf-8")
    for table in (
        "limit_up_research_runs",
        "limit_up_research_pool",
        "limit_up_selection_attribution",
        "limit_up_forward_labels",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in ddl
    assert "UNIQUE KEY uk_pool_fact (trade_date, pool_kind, ts_code)" in ddl
    assert "UNIQUE KEY uk_attribution (trade_date, ts_code, strategy)" in ddl
    assert "PRIMARY KEY (signal_date, ts_code, horizon)" in ddl
