#!/usr/bin/env python3
"""从保留的公开古籍网页抽取快照重建资料库；不生成经文。"""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from zhouyi.core import NAMES,ID_TO_BITS,BITS_TO_ID

def clean(text):
    text=re.sub(r'cite[^†]*†([^]*)',lambda m:m[1].split('†')[0],text)
    return text.strip()

def material(h,kind,position,text,raw,book='周易',source_url=None):
    text=clean(text)
    return {'id':f'{book}:{h}:{kind}:{position or 0}','hexagram_id':h,'kind':kind,'position':position,
            'book':book,'edition':'维基文库电子文本（保留页面修订号）','chapter':f'{NAMES[h-1]}·'+{'judgment':'卦辞','line':f'第{position}爻','use':'用九' if h==1 else '用六','tuan':'彖传','xiang':'大象','xiaoxiang':f'第{position}爻小象','commentary':'经传注释'}[kind],
            'text':text,'source_url':source_url or re.search(r'https://zh.wikisource.org/w/index.php\?title=[^\s]+',raw)[0],
            'checksum':hashlib.sha256(text.encode()).hexdigest(),'verification':'source-extracted/structure-checked'}

def parse_page(h,path):
    raw=path.read_text()
    lines=[clean(v) for v in re.split(r'L\d+: ',raw)[1:]]
    start=next(i for i,v in enumerate(lines) if '易經：' in v)
    tuan=next(i for i,v in enumerate(lines[start:],start) if v.startswith('* 彖曰：'))
    xiang=next(i for i,v in enumerate(lines[tuan:],tuan) if v.startswith('* 象曰：'))
    end=next((i for i,v in enumerate(lines[xiang+1:],xiang+1) if v.startswith('* 文言曰：') or v.startswith('Image') or '检索自' in v),len(lines))
    def vals(items): return [re.sub(r'^(?:\*|\d+\.)\s*','',v) for v in items if v and (v.startswith('*') or re.match(r'\d+\.',v))]
    base_lines=lines[start+1:tuan]
    numbered=[re.sub(r'^\d+\.\s*','',v) for v in base_lines if re.match(r'\d+\.',v)]
    judgment='\n'.join(re.sub(r'^\*\s*','',v) for v in base_lines if v.startswith('*'))
    base=[judgment,*numbered]; xs=vals(lines[xiang+1:end]); ts=vals(lines[tuan+1:xiang])
    assert len(base)==(8 if h in (1,2) else 7),(h,'经文数量',base)
    assert len(xs)>6,(h,'象传数量',xs)
    mk=lambda kind,p,text:material(h,kind,p,text,raw)
    return {'id':h,'name':NAMES[h-1],'bits':ID_TO_BITS[h],
            'judgment':mk('judgment',None,base[0]),'lines':[mk('line',i+1,t) for i,t in enumerate(base[1:7])],
            'use':mk('use',None,base[7]) if h in (1,2) else None,
            'tuan':mk('tuan',None,'\n'.join(ts)),'xiang':mk('xiang',None,xs[0]),
            'xiaoxiang':[mk('xiaoxiang',i+1,t) for i,t in enumerate(xs[1:7])],'commentaries':[]}

def extract_numbered_lines(paths):
    lines={}
    for path in paths:
        for match in re.finditer(r'L(\d+): ([\s\S]*?)(?=L\d+: |$)',path.read_text()):
            n=int(match[1]); text=match[2].strip()
            if len(text)>len(lines.get(n,'')): lines[n]=text
    return lines

def validate_benyi_body(hexagram_id,body):
    from zhouyi.core import ID_TO_BITS
    plain=re.sub(r'〈[^〈〉]*〉','',body)
    bits=ID_TO_BITS[hexagram_id]
    labels=[('初'+('九' if bits[0]=='1' else '六'))]
    labels += [('九' if bits[i]=='1' else '六')+'二三四五'[i-1] for i in range(1,5)]
    labels += [('上'+('九' if bits[5]=='1' else '六'))]
    cursor=0
    for label in labels:
        pos=plain.find(label,cursor)
        if pos<0: raise ValueError(f'第{hexagram_id}卦本义缺少完整六爻结构')
        cursor=pos+len(label)
    if '象曰' not in plain[cursor:] or body.count('〈')!=body.count('〉') or not body.endswith(('也','〉')):
        raise ValueError(f'第{hexagram_id}卦本义末段可能截断')

def add_commentaries(data,sources):
    paths=sorted((ROOT/'data').glob('benyi-*.txt'))
    lines=extract_numbered_lines(paths)
    text='\n'.join(t for n,t in sorted(lines.items()) if 136<=n<=263)
    headers=list(re.finditer(r'[䷀-䷿]〈([^〈〉]+)下([^〈〉]+)上〉',text))
    assert len(headers)==64
    trigrams=dict(zip('乾兌離震巽坎艮坤',('111','110','101','100','011','010','001','000')))
    url='https://zh.wikisource.org/wiki/周易本義_(四庫全書本)/全覽'
    for i,header in enumerate(headers):
        low,high=(v.replace('兑','兌') for v in header.groups())
        h=BITS_TO_ID[trigrams[low]+trigrams[high]]
        assert h==i+1,(h,i+1)
        body=text[header.end():headers[i+1].start() if i<63 else len(text)].strip()
        # 卷一结束与卷二题署不属于离卦正文。
        body=clean(body).split('周易本義卷一')[0].strip()
        validate_benyi_body(h,body)
        m=material(h,'commentary',None,body,'','周易本義',url)
        m['edition']='四库全书本·维基文库电子转录'
        m['verification']='source-extracted/structure-checked'
        m['coverage']='本卦经传与本义合录，未逐字校影印本；缺字图片保留标记'
        data[h-1]['commentaries'].append(m)
    path=ROOT/'data/zhengyi-277.txt'
    lines=extract_numbered_lines([path])
    # 仅收录明确可辨认的乾卦首段；不冒充全卦或全书覆盖。
    m=material(1,'commentary',None,lines[277],'','周易正義','https://zh.wikisource.org/wiki/周易正義_(四庫全書本)/全覽')
    m['edition']='四库全书本·维基文库电子转录'
    m['chapter']='卷一·乾卦开篇（节录）'
    m['coverage']='乾卦开篇节录，包含卦辞及部分爻辞注疏；其他卦暂无正义补注'
    data[0]['commentaries'].append(m)
    for path in [*paths,path]: sources.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})

def main():
    data=[]; sources=[]
    for h in range(1,65):
        path=ROOT/'data'/('source-32-heng.txt' if h==32 else f'source-{h}.txt')
        data.append(parse_page(h,path))
        sources.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    add_commentaries(data,sources)
    (ROOT/'data/classics.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'data/sources.json').write_text(json.dumps({'extracted_on':'2026-09-12','verification':'网页抽取与结构检查，未逐字对照影印本','license':'古代经传为公版；维基文库整理文本依页面 CC BY-SA 4.0 条款','sources':sources},ensure_ascii=False,indent=2)+'\n')
    print(f'已导入 {len(data)} 卦、{sum(len(h["lines"]) for h in data)} 爻、2 条用辞。')

if __name__=='__main__': main()
