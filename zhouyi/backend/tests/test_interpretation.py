import json
import httpx
import pytest
from sqlalchemy.engine import make_url
from zhouyi.config import Settings
from zhouyi.interpretation import validate_interpretation, generate_interpretation, InterpretationError

MATERIALS = [{'id':'p1', 'text':'元亨利贞', 'book':'周易', 'role':'primary'}]


def valid():
    paragraph = {'text':'应结合条件理解', 'source_ids':['p1']}
    return {'summary':paragraph,'traditional':[paragraph], 'application':paragraph,
            'actions':[paragraph], 'citations':[{'source_id':'p1','quote':'元亨利贞'}]}


def test_rejects_unknown_references_and_fabricated_quotes():
    data = valid()
    data['summary'] = {'text':'解释','source_ids':['invented']}
    with pytest.raises(ValueError): validate_interpretation(data, MATERIALS)
    data = valid()
    data['citations'][0]['quote'] = '三日必成'
    with pytest.raises(ValueError): validate_interpretation(data, MATERIALS)
    assert validate_interpretation(valid(), MATERIALS)['summary']['source_ids'] == ['p1']


def test_retries_temporary_server_failure_and_returns_verified_result():
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1: return httpx.Response(503)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(valid())}}]})
    settings = Settings(make_url('sqlite://'), api_key='secret')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = generate_interpretation({'question':'推进项目？'}, MATERIALS, settings, client=client, sleep=lambda _:None)
    assert result == valid()
    assert len(calls) == 2
    assert calls[0]['model'] == 'deepseek-flash'
    assert '推进项目' in calls[0]['messages'][1]['content']


def test_auth_failure_not_retried_or_exposed():
    calls = []
    def handler(request):
        calls.append(1)
        return httpx.Response(401,text='secret authorization failed')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(InterpretationError) as error:
            generate_interpretation({}, MATERIALS, Settings(make_url('sqlite://'),api_key='secret'), client=client)
    assert len(calls) == 1
    assert 'secret' not in str(error.value)


def test_incomplete_or_non_json_response_rejected():
    with pytest.raises(ValueError): validate_interpretation({'summary':'伪造'}, MATERIALS)
    def handler(request): return httpx.Response(200,json={'choices':[{'message':{'content':'not json'}}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(InterpretationError):
            generate_interpretation({}, MATERIALS, Settings(make_url('sqlite://'),api_key='k'), client=client)


@pytest.mark.parametrize('text', ['《周易》说：“三日必成”。', '《周易》说：‘三日必成’。', "《周易》说：'三日必成'。", '来源 https://invented.example/zhouyi'])
def test_fabricated_inline_quote_or_url_is_rejected(text):
    data=valid()
    data['traditional'][0]={'text':text,'source_ids':['p1']}
    with pytest.raises(ValueError): validate_interpretation(data, MATERIALS)


def test_summary_must_include_primary_material():
    data=valid()
    data['summary']={'text':'另一段解读','source_ids':['p2']}
    with pytest.raises(ValueError):
        validate_interpretation(data, MATERIALS+[{'id':'p2','text':'补充','role':'secondary'}])


def test_default_thinking_cannot_exhaust_json_output_budget():
    def handler(request):
        body=json.loads(request.content)
        if body.get('thinking')!={'type':'disabled'}:
            return httpx.Response(200,json={'choices':[{'finish_reason':'length','message':{'content':'{"summary":'}}]})
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(valid())}}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert generate_interpretation({},MATERIALS,Settings(make_url('sqlite://'),api_key='k'),client=client)==valid()


def test_one_bounded_repair_for_invalid_inline_quote():
    calls=[]
    def handler(request):
        calls.append(1)
        output=valid()
        if len(calls)==1: output['summary']={'text':'“三日必成”','source_ids':['p1']}
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(output)}}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert generate_interpretation({},MATERIALS,Settings(make_url('sqlite://'),api_key='k'),client=client)==valid()
    assert len(calls)==2
