"""只读取已入库、可追溯的古籍原文。"""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

@lru_cache(maxsize=1)
def _corpus():
    return json.loads((Path(__file__).resolve().parents[2]/'data/classics.json').read_text())

def list_hexagrams():
    return [{k:h[k] for k in ('id','name','bits')} for h in _corpus()]

def get_hexagram(hexagram_id):
    if type(hexagram_id) is not int or not 1<=hexagram_id<=64:
        raise ValueError('卦序须为 1 至 64')
    return deepcopy(_corpus()[hexagram_id-1])

def load_materials(selection):
    materials=[]; backgrounds=set(); seen=set()
    for role in ('primary','secondary'):
        for ref in selection[role]:
            h=get_hexagram(ref['hexagram_id']); kind=ref['kind']
            if kind=='line': m=h['lines'][ref['position']-1]
            elif kind in ('judgment','use'): m=h[kind]
            else: raise ValueError('未知经文类型')
            if m is None: raise ValueError('此卦没有用辞')
            materials.append(dict(m,role=role))
            for background in (h['tuan'],h['xiang'],*(h['xiaoxiang'][ref['position']-1:ref['position']] if kind=='line' else [])):
                if background['id'] not in backgrounds:
                    materials.append(dict(background,role='background')); backgrounds.add(background['id'])
            for m in h['commentaries']:
                if m['id'] not in seen:
                    materials.append(dict(m,role='commentary'));seen.add(m['id'])
    return materials
