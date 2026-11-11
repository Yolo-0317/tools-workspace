from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool
from zhouyi.config import Settings
from zhouyi.models import Base
from zhouyi.api import create_app
from zhouyi.interpretation import InterpretationError


@pytest.fixture
def client():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    def disabled_interpreter(*args, **kwargs):
        raise InterpretationError('测试模式未调用模型')

    app = create_app(Settings(make_url('sqlite://')), engine=engine,
                     interpretation_generator=disabled_interpreter)
    with TestClient(app) as client:
        yield client


def test_empty_question_rejected(client):
    assert client.post('/api/readings', json={'request_id':'r1','question':'   '}).status_code == 422


def test_create_and_repeat_keep_original_snapshot(client):
    body = {'request_id':'r1','question':'推进项目应注意什么？'}
    first = client.post('/api/readings', json=body)
    assert first.status_code == 201
    second = client.post('/api/readings', json=body)
    assert second.json()['id'] == first.json()['id']
    assert second.json()['cast'] == first.json()['cast']
    assert len(first.json()['materials']) >= 1
    assert first.json()['mode'] == 'classic'
    assert first.json()['calendar'] is None
    assert first.json()['najia'] is None
    body['question'] = '另一个问题'
    assert client.post('/api/readings', json=body).status_code == 409


def test_missing_record_and_pagination(client):
    assert client.get('/api/readings/missing').status_code == 404
    assert client.get('/api/readings?limit=5000').status_code == 422
    assert client.get('/api/classics/65').status_code == 422


def test_failure_retry_and_reflection(client):
    record = client.post('/api/readings',json={'request_id':'r2','question':'学习如何推进？'}).json()
    result = client.post(f"/api/readings/{record['id']}/interpretations",json={'request_id':'a1'})
    assert result.status_code == 202
    detail = client.get(f"/api/readings/{record['id']}").json()
    assert detail['interpretations'][0]['status'] == 'failed'
    assert detail['interpretations'][0]['error'] == '测试模式未调用模型'
    assert detail['cast'] == record['cast']
    assert client.post(f"/api/readings/{record['id']}/reflections",json={'text':'完成第一阶段'}).status_code == 201
    assert client.get(f"/api/readings/{record['id']}").json()['reflections'][0]['text'] == '完成第一阶段'


def test_api_never_falls_back_to_html_for_unknown_route(client):
    assert client.get('/api/unknown').status_code == 404


def test_cross_origin_write_rejected(client):
    assert client.post('/api/readings',headers={'Origin':'https://evil.example'},
                       json={'request_id':'r3','question':'测试？'}).status_code == 403


def test_create_najia_reading_with_versioned_beijing_chart(client):
    response = client.post('/api/readings', json={
        'request_id': 'najia-1',
        'question': '这项工作该如何推进？',
        'topic': 'work',
        'mode': 'najia',
        'cast_time': '2024-02-10T02:00:00Z',
        'location': '上海',
    })

    assert response.status_code == 201
    record = response.json()
    assert record['mode'] == 'najia'
    assert record['calendar']['beijing_time'] == '2024-02-10T10:00:00+08:00'
    assert record['calendar']['version'] == 'beijing-midnight-v1'
    assert record['najia']['version'] == 'jingfang-najia-v1'
    assert len(record['najia']['original_lines']) == 6
    assert record['question']['location'] == '上海'


def test_najia_rejects_time_without_timezone(client):
    response = client.post('/api/readings', json={
        'request_id': 'najia-bad-time',
        'question': '测试时间',
        'mode': 'najia',
        'cast_time': '2024-02-10T10:00:00',
    })

    assert response.status_code == 422
    assert '时区' in str(response.json())


def test_user_can_save_a_visible_najia_use_choice(client):
    record = client.post('/api/readings', json={
        'request_id': 'najia-use-1', 'question': '合作如何推进？',
        'mode': 'najia', 'topic': 'cooperation',
        'cast_time': '2024-02-10T10:00:00+08:00',
    }).json()

    response = client.post(f"/api/readings/{record['id']}/najia-use", json={'choice': '应爻'})

    assert response.status_code == 200
    assert response.json()['najia']['selected_use'] == '应爻'
    assert response.json()['najia']['use_selection_version'] == 'user-visible-v1'
    assert client.post(f"/api/readings/{record['id']}/najia-use", json={'choice': '随便'}).status_code == 422
