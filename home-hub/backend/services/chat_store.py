"""聊天会话与消息 SQLite 存储。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from backend.config import DB_PATH, DATA_DIR


class Base(DeclarativeBase):
    pass


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="新对话")
    cursor_agent_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


DATA_DIR.mkdir(parents=True, exist_ok=True)
_engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(_engine)


def create_session(title: str = "新对话") -> dict[str, Any]:
    now = _utcnow()
    row = ChatSession(
        id=str(uuid.uuid4()),
        title=title[:200],
        created_at=now,
        updated_at=now,
    )
    with Session(_engine) as db:
        db.add(row)
        db.commit()
        db.refresh(row)
    return _session_to_dict(row)


def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    with Session(_engine) as db:
        rows = db.scalars(
            select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(limit)
        ).all()
    return [_session_to_dict(r) for r in rows]


def get_session(session_id: str) -> dict[str, Any] | None:
    with Session(_engine) as db:
        row = db.get(ChatSession, session_id)
    return _session_to_dict(row) if row else None


def delete_session(session_id: str) -> bool:
    with Session(_engine) as db:
        row = db.get(ChatSession, session_id)
        if not row:
            return False
        for msg in db.scalars(
            select(ChatMessage).where(ChatMessage.session_id == session_id)
        ).all():
            db.delete(msg)
        db.delete(row)
        db.commit()
    return True


def touch_session(session_id: str, *, title: str | None = None) -> None:
    with Session(_engine) as db:
        row = db.get(ChatSession, session_id)
        if not row:
            return
        row.updated_at = _utcnow()
        if title:
            row.title = title[:200]
        db.commit()


def set_cursor_agent_id(session_id: str, agent_id: str) -> None:
    with Session(_engine) as db:
        row = db.get(ChatSession, session_id)
        if not row:
            return
        row.cursor_agent_id = agent_id
        row.updated_at = _utcnow()
        db.commit()


def add_message(session_id: str, role: str, content: str) -> dict[str, Any]:
    now = _utcnow()
    row = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role=role,
        content=content,
        created_at=now,
    )
    with Session(_engine) as db:
        db.add(row)
        sess = db.get(ChatSession, session_id)
        if sess:
            sess.updated_at = now
            if role == "user" and sess.title == "新对话":
                sess.title = content.strip()[:40] or "新对话"
        db.commit()
        db.refresh(row)
    return _message_to_dict(row)


def list_messages(session_id: str) -> list[dict[str, Any]]:
    with Session(_engine) as db:
        rows = db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        ).all()
    return [_message_to_dict(r) for r in rows]


def _session_to_dict(row: ChatSession) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "cursor_agent_id": row.cursor_agent_id,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _message_to_dict(row: ChatMessage) -> dict[str, Any]:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "role": row.role,
        "content": row.content,
        "created_at": row.created_at.isoformat(),
    }
