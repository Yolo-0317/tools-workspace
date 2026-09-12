import importlib.util
import itertools
import hashlib
from zhouyi.core import describe_cast
from zhouyi.rules import select_passages
from test_core import coins

def corpus():
    assert importlib.util.find_spec('zhouyi.corpus'), '古籍资料库尚未实现'
    from zhouyi import corpus
    return corpus

def test_full_corpus_has_real_text_and_provenance():
    c=corpus()
    hs=c.list_hexagrams()
    assert len(hs)==64 and len({h['bits'] for h in hs})==64
    for h in hs:
        detail=c.get_hexagram(h['id'])
        assert len(detail['lines'])==6 and detail['judgment']['text']
        assert detail['tuan']['text'] and detail['xiang']['text']
        assert len(detail['xiaoxiang'])==6
        for p in [detail['judgment'],*detail['lines']]:
            assert p['source_url'].startswith('https://')
            assert p['checksum']==hashlib.sha256(p['text'].encode()).hexdigest()
            assert p['verification']=='source-extracted/structure-checked'
    assert '潛龍勿用' in c.get_hexagram(1)['lines'][0]['text']
    assert '用九' in c.get_hexagram(1)['use']['text']
    assert '用六' in c.get_hexagram(2)['use']['text']

def test_all_4096_cast_states_resolve_actual_passages():
    c=corpus()
    for values in itertools.product((6,7,8,9),repeat=6):
        cast=describe_cast(coins(values))
        assert 1<=cast['original_id']<=64 and 1<=cast['changed_id']<=64
        selected=select_passages(cast)
        materials=c.load_materials(selected)
        main=[m for m in materials if m['role'] in ('primary','secondary')]
        assert len(main)==len(selected['primary'])+len(selected['secondary'])
        for role in ('primary','secondary'):
            actual=[m for m in main if m['role']==role]
            for ref,m in zip(selected[role],actual,strict=True):
                assert (m['hexagram_id'],m['kind'],m['position']) == (ref['hexagram_id'],ref['kind'],ref['position'])
                h=c.get_hexagram(ref['hexagram_id'])
                expected=h['lines'][ref['position']-1] if ref['kind']=='line' else h[ref['kind']]
                assert m['text']==expected['text'] and m['checksum']==expected['checksum']
        assert all(m['text'] and m['id'] for m in materials)

def test_main_commentary_is_available_for_every_hexagram():
    c=corpus()
    for h in c.list_hexagrams():
        comments=c.get_hexagram(h['id'])['commentaries']
        assert any(m['book']=='周易本義' and len(m['text'])>100 for m in comments)
    assert any(m['book']=='周易正義' for m in c.get_hexagram(1)['commentaries'])

def test_truncated_benyi_body_is_rejected():
    import pytest
    from pathlib import Path
    path=Path(__file__).resolve().parents[2]/'scripts/import_classics.py'
    spec=importlib.util.spec_from_file_location('import_classics',path)
    importer=importlib.util.module_from_spec(spec);spec.loader.exec_module(importer)
    body=corpus().get_hexagram(64)['commentaries'][0]['text']
    assert hasattr(importer,'validate_benyi_body'), '本义正文完整性检查尚未实现'
    with pytest.raises(ValueError): importer.validate_benyi_body(64,body[:220])
    with pytest.raises(ValueError): importer.validate_benyi_body(64,body[:-5])
    importer.validate_benyi_body(64,body)
