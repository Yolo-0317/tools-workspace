"""Read tested mx-data single-day top-five tables without merging unnamed seats."""
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


def parse(response, code, day):
    if response.get('status') != 0:
        raise ValueError('龙虎榜业务失败，不能解释为未上榜')
    tables=response.get('data',{}).get('data',{}).get('searchDataResultDTO',{}).get('dataTableDTOList',[])
    result=[]
    for index,t in enumerate(tables):
        title=t.get('inputTitle') or t.get('title','')
        if '龙虎榜' not in title:continue
        field=t.get('field',{})
        if t.get('code')!=code or any(str(field.get(k,''))[:10]!=day for k in ['startDate','endDate']):
            raise ValueError('证券或单日区间不匹配；连续三日榜需独立适配')
        raw=t.get('rawTable') or t.get('table') or {}
        heads=raw.get('headName',[])
        sides=[(side,heads.index(label)) for side,label in [('buy','买入金额(万元)'),('sell','卖出金额(万元)')] if label in heads]
        if len(sides)!=1:raise ValueError('非已验证的单侧金额表或单位不符')
        side,position=sides[0]
        keys=[k for k in raw if k!='headName']
        order=[str(k) for k in t.get('indicatorOrder',[]) if str(k) in keys]
        order+= [k for k in keys if k not in order]
        if len(order)!=len(set(order)):raise ValueError('重复原始列ID')
        for rank,key in enumerate(order,1):
            values=raw[key]
            if not isinstance(values,list) or len(values)<=position:raise ValueError('金额缺失')
            amount=str(values[position])
            try:number=Decimal(amount)
            except InvalidOperation:raise ValueError('金额无效') from None
            if not number.is_finite() or number<0:raise ValueError('金额无效')
            name=t.get('nameMap',{}).get(key)
            if not name:raise ValueError('席位名称缺失')
            result.append({'code':code,'date':day,'table_id':index,'title':title,'side':side,
                           'rank':rank,'seat_id':key,'name':name,'amount_wan':amount,
                           'top5_complete':len(order)==5})
    if not result:raise ValueError('未返回可核验龙虎榜表，不等于确认未上榜')
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input');p.add_argument('--code',required=True);p.add_argument('--date',required=True)
    args=p.parse_args()
    print(json.dumps({'rows':parse(json.loads(Path(args.input).read_text()),args.code,args.date),
                     'scope':'单侧前五金额；不可推断全榜净额或同名机构身份'},ensure_ascii=False,indent=2))
