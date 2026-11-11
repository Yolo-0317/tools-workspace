from zhouyi.presentation import present_material, present_reading, simplify


def test_material_displays_simplified_but_preserves_original_provenance():
    original={'id':'周易本義:6:commentary:0','book':'周易本義','chapter':'訟·經傳注釋',
              'text':'訟：有孚窒惕，中吉，終凶。','source_url':'https://zh.wikisource.org/wiki/周易/訟',
              'checksum':'original-hash','edition':'四庫全書本'}
    shown=present_material(original)
    assert shown['book']=='周易本义'
    assert shown['chapter']=='讼·经传注释'
    assert shown['text']=='讼：有孚窒惕，中吉，终凶。'
    assert shown['source_text']==original['text']
    assert shown['source_checksum']=='original-hash'
    assert shown['source_url']==original['source_url']
    assert shown['id']==original['id']
    assert original['text'].startswith('訟')


def test_historical_ai_output_and_quotes_convert_without_breaking_reference_ids():
    record={'materials':[], 'interpretations':[{'result':{'summary':{'text':'謙遜守正','source_ids':['周易本義:6:commentary:0']},
             'citations':[{'source_id':'周易本義:6:commentary:0','quote':'終凶'}]}}]}
    shown=present_reading(record)
    assert shown['interpretations'][0]['result']['summary']['text']=='谦逊守正'
    assert shown['interpretations'][0]['result']['summary']['source_ids']==['周易本義:6:commentary:0']
    assert shown['interpretations'][0]['result']['citations'][0]['quote']=='终凶'
