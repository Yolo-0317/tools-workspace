from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Reading(Base):
    __tablename__ = 'readings'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(80), unique=True)
    question: Mapped[dict] = mapped_column(JSON)
    cast: Mapped[dict] = mapped_column(JSON)
    selection: Mapped[dict] = mapped_column(JSON)
    materials: Mapped[list] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String(20), default='classic')
    calendar: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    najia: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Attempt(Base):
    __tablename__ = 'interpretations'
    __table_args__ = (UniqueConstraint('reading_id', 'request_id'), UniqueConstraint('reading_id','sequence',name='uq_reading_sequence'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    reading_id: Mapped[str] = mapped_column(ForeignKey('readings.id'), index=True)
    request_id: Mapped[str] = mapped_column(String(80))
    sequence: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(20), default='running')
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(60))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Reflection(Base):
    __tablename__ = 'reflections'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    reading_id: Mapped[str] = mapped_column(ForeignKey('readings.id'), index=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ClassicalEntry(Base):
    __tablename__ = 'classical_entries'
    id: Mapped[str] = mapped_column(String(180), primary_key=True)
    hexagram_id: Mapped[int] = mapped_column(index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
