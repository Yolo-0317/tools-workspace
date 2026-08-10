#!/usr/bin/env python3
"""Configure least-privilege MySQL access for the short-term trading runtime."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from apply_migrations import create_root_engine


PROJECT = Path(__file__).resolve().parents[1]
WORKSPACE = PROJECT.parent
ENV_FILE = WORKSPACE / "stock-ai" / ".env"
DATABASE = "stock_data"
ACCOUNT = "stt_app"
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
DDL_PRIVILEGES = ("CREATE", "DROP", "ALTER", "INDEX")
DML_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE")


def permission_plan() -> list[str]:
    return [
        "PRECHECK root connectivity",
        "PRECHECK 15 stt tables",
        "PRECHECK stt_app connectivity",
        "REVOKE CREATE, DROP, ALTER, INDEX ON stock_data.* FROM stt_app@%",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON stock_data.* TO stt_app@%",
    ]


def create_runtime_engine():
    load_dotenv(ENV_FILE, override=False)
    runtime_url = os.getenv("MYSQL_URL")
    if not runtime_url:
        raise RuntimeError("runtime configuration missing")
    parsed = make_url(runtime_url)
    if parsed.username != ACCOUNT or parsed.database != DATABASE:
        raise RuntimeError("runtime identity mismatch")
    return create_engine(parsed, pool_pre_ping=True)


def _validate_prerequisites(root_engine, runtime_engine) -> None:
    with root_engine.connect() as connection:
        connection.execute(text("SELECT 1")).scalar_one()
    tables = set(inspect(root_engine).get_table_names())
    if not EXPECTED_TABLES <= tables:
        raise RuntimeError("schema prerequisite failed")
    with runtime_engine.connect() as connection:
        connection.execute(text("SELECT 1")).scalar_one()


def _grant_text(connection) -> str:
    rows = connection.execute(text("SHOW GRANTS FOR 'stt_app'@'%'")).fetchall()
    return "\n".join(str(row[0]) for row in rows).upper()


def configure_permissions() -> None:
    root_engine = create_root_engine()
    runtime_engine = create_runtime_engine()
    try:
        _validate_prerequisites(root_engine, runtime_engine)
        with root_engine.begin() as connection:
            current = _grant_text(connection)
            database_scope = f"ON `{DATABASE.upper()}`.*"
            has_database_all = "ALL PRIVILEGES" in current and database_scope in current
            has_ddl = has_database_all or any(
                privilege in current and database_scope in current
                for privilege in DDL_PRIVILEGES
            )
            if has_ddl:
                connection.execute(
                    text(
                        "REVOKE CREATE, DROP, ALTER, INDEX ON `stock_data`.* "
                        "FROM 'stt_app'@'%'"
                    )
                )
            connection.execute(
                text(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON `stock_data`.* "
                    "TO 'stt_app'@'%'"
                )
            )

        with root_engine.connect() as connection:
            final = _grant_text(connection)
        if any(privilege not in final for privilege in DML_PRIVILEGES):
            raise RuntimeError("runtime DML verification failed")
        if any(privilege in final for privilege in DDL_PRIVILEGES):
            raise RuntimeError("runtime DDL verification failed")
    finally:
        runtime_engine.dispose()
        root_engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure stt_app MySQL permissions")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="print the plan without connecting")
    modes.add_argument("--apply", action="store_true", help="validate and apply the permission plan")
    args = parser.parse_args()

    if not args.apply:
        for line in permission_plan():
            print(line)
        return 0

    try:
        configure_permissions()
    except Exception:
        print("permission configuration FAILED")
        return 1
    for line in permission_plan():
        print(f"{line} OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
