#!/usr/bin/env python3
"""Apply short-term trading schema migrations with the configured MySQL root account."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.engine import make_url


PROJECT = Path(__file__).resolve().parents[1]
WORKSPACE = PROJECT.parent
SQL_DIR = PROJECT / "sql"
ENV_FILE = WORKSPACE / "stock-ai" / ".env"


class MigrationError(RuntimeError):
    """A migration failed; details are intentionally kept out of CLI output."""

    def __init__(self, filename: str) -> None:
        super().__init__(filename)
        self.filename = filename


def migration_files() -> list[Path]:
    return sorted(SQL_DIR.glob("[0-9][0-9][0-9]_*.sql"))


def split_statements(sql: str) -> Iterable[str]:
    """Split the simple migration SQL; migrations do not use stored-program delimiters."""

    for statement in sql.split(";"):
        cleaned = statement.strip()
        if cleaned:
            yield cleaned


def create_root_engine() -> Engine:
    load_dotenv(ENV_FILE, override=False)
    password = os.getenv("MYSQL_ROOT_PASSWORD")
    runtime_url = os.getenv("MYSQL_URL")
    if not password:
        raise RuntimeError("MYSQL_ROOT_PASSWORD is required")
    if not runtime_url:
        raise RuntimeError("MYSQL_URL is required to locate MySQL")

    parsed = make_url(runtime_url)
    root_url = URL.create(
        drivername="mysql+pymysql",
        username="root",
        password=password,
        host=parsed.host or "192.168.1.13",
        port=parsed.port or 3306,
        database=parsed.database or "stock_data",
        query={"charset": "utf8mb4"},
    )
    return create_engine(root_url, pool_pre_ping=True)


def apply_migrations(engine: Engine, *, emit: bool = False) -> None:
    raw_connection = engine.raw_connection()
    try:
        cursor = raw_connection.cursor()
        try:
            for path in migration_files():
                try:
                    for statement in split_statements(path.read_text(encoding="utf-8")):
                        cursor.execute(statement)
                    raw_connection.commit()
                except Exception as exc:
                    raw_connection.rollback()
                    raise MigrationError(path.name) from exc
                if emit:
                    print(f"{path.name} OK")
        finally:
            cursor.close()
    finally:
        raw_connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply short-term trading MySQL migrations")
    parser.add_argument("--dry-run", action="store_true", help="list migrations without connecting")
    args = parser.parse_args()

    if args.dry_run:
        for path in migration_files():
            print(f"{path.name} DRY-RUN")
        return 0

    try:
        engine = create_root_engine()
        apply_migrations(engine, emit=True)
    except MigrationError as exc:
        print(f"{exc.filename} FAILED")
        return 1
    except RuntimeError:
        print("configuration FAILED")
        return 1
    finally:
        if "engine" in locals():
            engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
