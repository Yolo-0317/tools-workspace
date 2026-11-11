from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from zhouyi.models import Base, Attempt
from zhouyi.repository import Repository, Conflict


@pytest.fixture
def repo():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    return Repository(engine)


def make_record(repo, request='req1', question='项目推进应注意什么？'):
    return repo.create_reading(request, dict(question=question, topic='', background='', horizon=''),
                               dict(values=[7]*6), dict(version='v1'), [{'id':'p1','text':'元亨利贞'}])


def test_duplicate_request_returns_original_snapshot(repo):
    first = make_record(repo)
    second = repo.create_reading('req1', first['question'], {'values':[8]*6}, {}, [])
    assert first['id'] == second['id']
    assert second['cast'] == {'values':[7]*6}
    assert repo.list_readings(0, 20)['total'] == 1


def test_record_defaults_keep_old_classic_shape(repo):
    record = make_record(repo)

    assert record['mode'] == 'classic'
    assert record['calendar'] is None
    assert record['najia'] is None


def test_conflicting_id_cannot_change_question(repo):
    make_record(repo)
    with pytest.raises(Conflict):
        make_record(repo, question='其他问题')


def test_attempt_failure_keeps_cast_and_allows_new_version(repo):
    record = make_record(repo)
    attempt, claimed = repo.begin_attempt(record['id'], 'a1', 'ds', 'p1', 600)
    assert claimed
    duplicate, claimed = repo.begin_attempt(record['id'], 'a2', 'ds', 'p1', 600)
    assert not claimed and duplicate['id'] == attempt['id']
    repo.finish_attempt(attempt['id'], error='解读暂时不可用')
    next_attempt, claimed = repo.begin_attempt(record['id'], 'a2', 'ds', 'p1', 600)
    assert claimed and next_attempt['id'] != attempt['id']
    repo.finish_attempt(next_attempt['id'], result={'summary':'请先看条件'})
    detail = repo.get_reading(record['id'])
    assert detail['cast'] == record['cast']
    assert [a['status'] for a in detail['interpretations']] == ['failed','succeeded']


def test_expired_lease_can_be_recovered_and_late_worker_cannot_overwrite(repo):
    record = make_record(repo)
    attempt, _ = repo.begin_attempt(record['id'], 'a1', 'ds', 'p1', 600)
    with Session(repo.engine) as s:
        s.get(Attempt, attempt['id']).started_at = datetime.utcnow() - timedelta(hours=1)
        s.commit()
    new, claimed = repo.begin_attempt(record['id'], 'a2', 'ds', 'p1', 600)
    assert claimed and new['id'] != attempt['id']
    repo.finish_attempt(attempt['id'], result={'late':True})
    assert repo.get_reading(record['id'])['interpretations'][0]['status'] == 'failed'


def test_reflections_append_without_rewriting_question(repo):
    record = make_record(repo)
    repo.add_reflection(record['id'], '资源已有着落')
    repo.add_reflection(record['id'], '完成第一阶段')
    detail = repo.get_reading(record['id'])
    assert [r['text'] for r in detail['reflections']] == ['资源已有着落','完成第一阶段']
    assert detail['question'] == record['question']


def test_attempts_keep_creation_order_when_database_timestamps_tie(repo):
    record=make_record(repo)
    old,_=repo.begin_attempt(record['id'],'a1','ds','p1',600)
    repo.finish_attempt(old['id'],error='失败')
    new,_=repo.begin_attempt(record['id'],'a2','ds','p1',600)
    repo.finish_attempt(new['id'],result={'summary':'成功'})
    with Session(repo.engine) as s:
        first=s.get(Attempt,old['id']);second=s.get(Attempt,new['id'])
        first.started_at=second.started_at=datetime(2026,9,12,12,0,0)
        first.id='ffffffff-0000-0000-0000-000000000000'
        second.id='00000000-0000-0000-0000-000000000000'
        s.commit()
    assert [a['status'] for a in repo.get_reading(record['id'])['interpretations']]==['failed','succeeded']
