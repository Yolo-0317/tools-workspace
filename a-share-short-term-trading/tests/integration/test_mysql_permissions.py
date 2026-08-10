from __future__ import annotations

import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.engine import make_url
from dotenv import load_dotenv


pytestmark = pytest.mark.skipif(
    os.getenv("STT_MYSQL_INTEGRATION") != "1",
    reason="set STT_MYSQL_INTEGRATION=1 to use the configured household MySQL",
)

PROJECT = Path(__file__).resolve().parents[2]
WORKSPACE = PROJECT.parent


def runtime_engine():
    load_dotenv(WORKSPACE / "stock-ai" / ".env", override=False)
    url = make_url(os.environ["MYSQL_URL"])
    assert url.username == "stt_app"
    assert url.database == "stock_data"
    return create_engine(url, pool_pre_ping=True)


def test_stt_app_has_runtime_dml_and_cannot_create_tables() -> None:
    migration_scripts = PROJECT / "scripts"
    sys.path.insert(0, str(migration_scripts))
    from apply_migrations import create_root_engine

    root_engine = create_root_engine()
    with root_engine.connect() as root:
        grants = "\n".join(
            row[0] for row in root.execute(text("SHOW GRANTS FOR 'stt_app'@'%'")).fetchall()
        ).upper()
    root_engine.dispose()

    for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        assert privilege in grants
    for privilege in ("CREATE", "DROP", "ALTER", "INDEX"):
        assert privilege not in grants

    engine = runtime_engine()
    watch_id = str(uuid4())
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(
            text(
                """
                INSERT INTO stt_watchlist
                    (watch_id, code, trading_date, status, source, created_at, updated_at)
                VALUES
                    (:watch_id, '600000', '2026-08-10', 'ACTIVE', 'permission-test',
                     UTC_TIMESTAMP(6), UTC_TIMESTAMP(6))
                """
            ),
            {"watch_id": watch_id},
        )
        connection.execute(
            text("UPDATE stt_watchlist SET status = 'CHECKED' WHERE watch_id = :watch_id"),
            {"watch_id": watch_id},
        )
        connection.execute(
            text("DELETE FROM stt_watchlist WHERE watch_id = :watch_id"),
            {"watch_id": watch_id},
        )
        transaction.rollback()

    with engine.connect() as connection:
        with pytest.raises(DBAPIError):
            connection.execute(
                text("CREATE TABLE stt_permission_probe (id INT PRIMARY KEY)")
            )
        connection.rollback()
    engine.dispose()
