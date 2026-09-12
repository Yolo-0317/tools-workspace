"""Transactions and immutable reading snapshots; no model calls here."""
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .models import Attempt, ClassicalEntry, Reading, Reflection


class Conflict(ValueError):
    pass


class NotFound(LookupError):
    pass


def serialize(row):
    return {c.name: (getattr(row, c.name).isoformat() + 'Z'
                     if isinstance(getattr(row, c.name), datetime) else getattr(row, c.name))
            for c in row.__table__.columns}


class Repository:
    def __init__(self, engine):
        self.engine = engine

    def create_reading(self, request_id, question, cast, selection, materials, *,
                       mode='classic', calendar=None, najia=None):
        try:
            with Session(self.engine) as session, session.begin():
                existing = session.scalar(select(Reading).where(Reading.request_id == request_id))
                if existing:
                    if existing.question != question or existing.mode != mode:
                        raise Conflict('同一请求编号对应的问题已变化，请重新提交')
                    identifier = existing.id
                else:
                    identifier = str(uuid4())
                    session.add(Reading(id=identifier, request_id=request_id, question=question,
                                        cast=cast, selection=selection, materials=materials,
                                        mode=mode, calendar=calendar, najia=najia))
        except IntegrityError:
            with Session(self.engine) as session:
                existing = session.scalar(select(Reading).where(Reading.request_id == request_id))
                if existing is None:
                    raise
                if existing.question != question or existing.mode != mode:
                    raise Conflict('同一请求编号对应的问题已变化，请重新提交') from None
                identifier = existing.id
        return self.get_reading(identifier)

    def get_reading(self, identifier):
        with Session(self.engine) as session:
            reading = session.get(Reading, identifier)
            if reading is None:
                raise NotFound('未找到这次起卦记录')
            result = serialize(reading)
            result['interpretations'] = [serialize(x) for x in session.scalars(
                select(Attempt).where(Attempt.reading_id == identifier).order_by(Attempt.sequence))]
            result['reflections'] = [serialize(x) for x in session.scalars(
                select(Reflection).where(Reflection.reading_id == identifier).order_by(Reflection.created_at, Reflection.id))]
            return result

    def list_readings(self, offset, limit):
        with Session(self.engine) as session:
            total = session.scalar(select(func.count()).select_from(Reading))
            rows = session.scalars(select(Reading).order_by(Reading.created_at.desc(), Reading.id)
                                   .offset(offset).limit(limit))
            return {'total': total, 'items': [
                {'id':r.id, 'question':r.question, 'cast':r.cast, 'mode':r.mode,
                 'created_at':r.created_at.isoformat()+'Z'} for r in rows]}

    def add_reflection(self, identifier, text):
        with Session(self.engine) as session, session.begin():
            if session.get(Reading, identifier) is None:
                raise NotFound('未找到这次起卦记录')
            row = Reflection(id=str(uuid4()), reading_id=identifier, text=text)
            session.add(row)
            session.flush()
            return serialize(row)

    def set_najia_use(self, identifier, choice):
        with Session(self.engine) as session, session.begin():
            reading = session.scalar(select(Reading).where(Reading.id == identifier).with_for_update())
            if reading is None:
                raise NotFound('未找到这次起卦记录')
            if reading.mode != 'najia' or not reading.najia:
                raise Conflict('这条记录不是六爻纳甲模式')
            snapshot = dict(reading.najia)
            snapshot['selected_use'] = choice
            snapshot['use_selection_version'] = 'user-visible-v1'
            reading.najia = snapshot
        return self.get_reading(identifier)

    def begin_attempt(self, identifier, request_id, model, prompt_version, lease_seconds):
        with Session(self.engine) as session, session.begin():
            # Parent row serializes all attempts for the same reading in MySQL.
            reading = session.scalar(select(Reading).where(Reading.id == identifier).with_for_update())
            if reading is None:
                raise NotFound('未找到这次起卦记录')
            attempts = list(session.scalars(select(Attempt).where(Attempt.reading_id == identifier)))
            cutoff = datetime.utcnow() - timedelta(seconds=lease_seconds)
            for old in attempts:
                if old.status == 'running' and old.started_at < cutoff:
                    old.status, old.error, old.finished_at = 'failed', '上次解读已中断，可以重新解读', datetime.utcnow()
            for old in attempts:
                if old.request_id == request_id or old.status == 'running':
                    session.flush()
                    return serialize(old), False
            row = Attempt(id=str(uuid4()), reading_id=identifier, request_id=request_id,
                          model=model, prompt_version=prompt_version, status='running',
                          sequence=max((a.sequence for a in attempts),default=0)+1)
            session.add(row)
            session.flush()
            return serialize(row), True

    def finish_attempt(self, identifier, result=None, error=None):
        with Session(self.engine) as session, session.begin():
            row = session.scalar(select(Attempt).where(Attempt.id == identifier).with_for_update())
            if row is None or row.status != 'running':
                return
            row.status = 'failed' if error else 'succeeded'
            row.error, row.result, row.finished_at = error, result, datetime.utcnow()

    def sync_classics(self, entries):
        with Session(self.engine) as session, session.begin():
            for item in entries:
                current = session.get(ClassicalEntry, item['id'])
                if current is None:
                    session.add(ClassicalEntry(id=item['id'], hexagram_id=item['hexagram_id'],
                                               payload=item, checksum=item['checksum']))
                elif current.checksum != item['checksum']:
                    current.payload, current.checksum = item, item['checksum']
