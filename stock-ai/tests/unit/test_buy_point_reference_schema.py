from pathlib import Path


SQL_DIR = Path(__file__).resolve().parents[3] / "stock-mysql" / "sql"


def test_point_in_time_reference_tables_are_additive_and_auditable() -> None:
    sql = (SQL_DIR / "015_buy_point_reference_history.sql").read_text(encoding="utf-8").lower()
    assert "create table if not exists buy_point_sector_memberships" in sql
    assert "valid_from" in sql and "valid_to" in sql
    assert "create table if not exists buy_point_risk_flags" in sql
    assert "create table if not exists buy_point_reference_sync_runs" in sql
    assert "drop table" not in sql


def test_advisor_link_migration_adds_nullable_plan_id_without_rewriting_cycles() -> None:
    sql = (SQL_DIR / "016_buy_point_advisor_link.sql").read_text(encoding="utf-8").lower()
    assert "selection_plan_id char(36)" in sql
    assert "information_schema.columns" in sql
    assert "idx_advisor_selection_plan" in sql
    assert "update advisor_decision_cycles" not in sql
    assert "delete from advisor_decision_cycles" not in sql


def test_provider_audit_migration_is_additive_and_has_checkpoints() -> None:
    """Catches a provider rollout without resumable, inspectable coverage state."""
    sql = (
        SQL_DIR / "017_buy_point_reference_provider_audit.sql"
    ).read_text(encoding="utf-8").lower()

    for column in ("provider", "expected_count", "coverage_ratio", "details_json"):
        assert column in sql
    assert "create table if not exists buy_point_reference_checkpoints" in sql
    assert "primary key (provider, dataset, partition_key)" in sql
    assert "information_schema.columns" in sql
    assert "drop table" not in sql
    assert "delete from" not in sql
