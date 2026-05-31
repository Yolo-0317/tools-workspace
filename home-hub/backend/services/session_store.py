"""Hub 登录会话（SQLite）。"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from backend.config import DB_PATH, DATA_DIR, settings
from backend.services.hub_auth import HubRole


class Base(DeclarativeBase):
    pass


class HubSessionRow(Base):
    __tablename__ = "hub_sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


DATA_DIR.mkdir(parents=True, exist_ok=True)
_engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(_engine)


def create_session(username: str, role: HubRole) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    now = _utcnow()
    expires = now + timedelta(hours=settings.session_ttl_hours)
    row = HubSessionRow(
        token=token,
        username=username,
        role=role,
        created_at=now,
        expires_at=expires,
    )
    with SessionLocal() as db:
        db.add(row)
        db.commit()
    return token, expires


def get_session(token: str) -> dict[str, str] | None:
    if not token:
        return None
    now = _utcnow()
    with SessionLocal() as db:
        row = db.get(HubSessionRow, token)
        if not row or _normalize_utc(row.expires_at) <= now:
            if row:
                db.delete(row)
                db.commit()
            return None
        return {
            "username": row.username,
            "role": row.role,
        }


def delete_session(token: str) -> None:
    with SessionLocal() as db:
        row = db.get(HubSessionRow, token)
        if row:
            db.delete(row)
            db.commit()


def purge_expired() -> int:
    now = _utcnow()
    with SessionLocal() as db:
        rows = db.scalars(select(HubSessionRow)).all()
        n = 0
        for row in rows:
            if _normalize_utc(row.expires_at) <= now:
                db.delete(row)
                n += 1
        db.commit()
        return n
