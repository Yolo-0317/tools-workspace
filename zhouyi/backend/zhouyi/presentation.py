"""Simplified display is derived; original text, identifiers and URLs stay intact."""
from copy import deepcopy
from functools import lru_cache
import hashlib
from opencc import OpenCC

_converter=OpenCC('t2s')


@lru_cache(maxsize=4096)
def simplify(value: str) -> str:
    return _converter.convert(value)


def present_material(material):
    shown=deepcopy(material)
    shown['source_text']=material.get('source_text',material['text'])
    shown['source_checksum']=material.get('source_checksum',material.get('checksum',''))
    for key in ('book','chapter','text','edition','coverage'):
        if key in shown:
            shown[key]=simplify(shown[key])
    shown['checksum']=hashlib.sha256(shown['text'].encode()).hexdigest()
    shown['display_note']='简体转换展示，底本原文及来源保留供核对'
    return shown


def present_result(value):
    if isinstance(value,list):
        return [present_result(x) for x in value]
    if isinstance(value,dict):
        return {k:(simplify(v) if k in ('text','quote') and isinstance(v,str) else present_result(v))
                for k,v in value.items()}
    return value


def present_reading(record):
    shown=deepcopy(record)
    shown['materials']=[present_material(m) for m in shown.get('materials',[])]
    for attempt in shown.get('interpretations',[]):
        if attempt.get('result'):
            attempt['result']=present_result(attempt['result'])
    return shown


def present_hexagram(hexagram):
    shown=deepcopy(hexagram)
    shown['name']=simplify(shown['name'])
    for key in ('judgment','use','tuan','xiang'):
        if shown.get(key): shown[key]=present_material(shown[key])
    for key in ('lines','xiaoxiang','commentaries'):
        shown[key]=[present_material(m) for m in shown[key]]
    return shown
