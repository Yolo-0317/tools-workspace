from pathlib import Path
import subprocess
import sys


PROJECT = Path(__file__).resolve().parents[1]
SQL_DIR = PROJECT / "sql"
EXPECTED_TABLES = {
    "stt_schema_versions",
    "stt_watchlist",
    "stt_market_states",
    "stt_candidates",
    "stt_evidence_snapshots",
    "stt_capture_attempts",
    "stt_source_health",
    "stt_daily_sync_runs",
    "stt_trade_plans",
    "stt_risk_decisions",
    "stt_decision_snapshots",
    "stt_intraday_decisions",
    "stt_outcome_observations",
    "stt_trade_journal",
    "stt_plan_evaluations",
}


def migration_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(SQL_DIR.glob("*.sql")))


def test_migrations_define_all_v11_tables_idempotently() -> None:
    sql = migration_text().lower()

    for table in EXPECTED_TABLES:
        assert f"create table if not exists {table}" in sql
    assert "values ('1.1', 'short-term trading v1.1 foundation')" in sql
    assert "on duplicate key update" in sql


def test_migrations_use_fixed_point_money_utc_timestamps_and_query_indexes() -> None:
    sql = migration_text().lower()

    assert "decimal(" in sql
    assert "float" not in sql
    assert "datetime(6)" in sql
    for fragment in ("index idx_code", "index idx_trading_date", "index idx_status", "index idx_as_of"):
        assert fragment in sql


def test_append_only_business_tables_have_uuid_primary_keys() -> None:
    sql = migration_text().lower()
    expected_keys = {
        "stt_evidence_snapshots": "evidence_id",
        "stt_market_states": "state_id",
        "stt_candidates": "candidate_id",
        "stt_trade_plans": "plan_id",
        "stt_risk_decisions": "risk_id",
        "stt_decision_snapshots": "decision_id",
        "stt_intraday_decisions": "intraday_id",
        "stt_outcome_observations": "observation_id",
        "stt_trade_journal": "journal_id",
        "stt_plan_evaluations": "evaluation_id",
    }

    for table, key in expected_keys.items():
        start = sql.index(f"create table if not exists {table}")
        end = sql.index("engine=innodb", start)
        definition = sql[start:end]
        assert f"{key} char(36) not null" in definition
        assert f"primary key ({key})" in definition


def test_broker_fact_migration_contains_every_compatibility_column() -> None:
    sql = (SQL_DIR / "004_portfolio_broker_facts.sql").read_text(encoding="utf-8").lower()
    expected_columns = {
        "available_shares",
        "current_price",
        "market_value",
        "position_pnl",
        "position_pnl_pct",
        "daily_pnl",
        "daily_pnl_pct",
        "broker_captured_at",
        "cash_balance",
        "withdrawable_cash",
        "frozen_cash",
    }

    for column in expected_columns:
        assert column in sql
    assert "information_schema.columns" in sql


def test_migrations_do_not_embed_credentials() -> None:
    sql = migration_text().lower()

    assert "mysql_root_password" not in sql
    assert "mysql://" not in sql
    assert "identified by" not in sql


def test_migration_cli_dry_run_lists_files_without_connecting() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT / "scripts" / "apply_migrations.py"), "--dry-run"],
        cwd=PROJECT.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "001_stt_daily_sync_runs.sql DRY-RUN",
        "002_stt_evidence_and_capture.sql DRY-RUN",
        "003_stt_core_schema.sql DRY-RUN",
        "004_portfolio_broker_facts.sql DRY-RUN",
    ]
    assert result.stderr == ""
