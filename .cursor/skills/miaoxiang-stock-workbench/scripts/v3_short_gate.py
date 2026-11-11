"""Check necessary V3 gates before fetching 450-day history. No API calls."""
import json
import math
from datetime import date
from pathlib import Path


def check(payload):
    result={'code':payload.get('code'),'as_of':payload.get('as_of'),'status':'pending'}
    try:
        if payload.get('source') not in {'mx-finance-data','tushare-daily'} or not payload.get('source_file'):
            raise ValueError('缺Tushare或妙想来源')
        if payload.get('adjustment')!='unadjusted' or payload.get('history_complete') is not True:
            raise ValueError('复权或所请求区间的历史完整性未核验')
        bars=sorted(payload['bars'],key=lambda b:b['date'])
        dates=[date.fromisoformat(b['date']) for b in bars]
        if len(dates)!=len(set(dates)) or len(bars)<61 or str(dates[-1])!=payload['as_of']:
            raise ValueError('至少需要61根连续有效日线，日期不得重复且截止日一致')
        bars=bars[-61:]
        for b in bars:
            for k in ['close','high','volume_shares']:
                if not math.isfinite(float(b[k])) or float(b[k])<=0:
                    raise ValueError('短窗口指标缺失或无效')
            if float(b['high'])<float(b['close']):raise ValueError('最高价低于收盘')
        last=bars[-1];close=float(last['close']);prev=float(bars[-2]['close'])
        pct=float(last['pct_change']);amount=float(last['amount_yuan'])
        if not math.isfinite(pct) or not math.isfinite(amount) or amount<0:
            raise ValueError('涨幅或成交额无效')
        ma60=sum(float(b['close']) for b in bars[-60:])/60
        prev_ma60=sum(float(b['close']) for b in bars[-61:-1])/60
        ratio=float(last['volume_shares'])/(sum(float(b['volume_shares']) for b in bars[-5:])/5)
        gates={'price':3<=close<=200,'amount':amount>=5000000,'pct_change':pct>=3,
               'volume_ratio':ratio>=1.5,'breakout_ma60':close>ma60 and prev<=prev_ma60,
               'breakout_20high':close>max(float(b['high']) for b in bars[-21:-1])}
        passed=all(gates[k] for k in ['price','amount','pct_change','volume_ratio']) and (gates['breakout_ma60'] or gates['breakout_20high'])
        result.update(status='pass' if passed else 'reject',checks=gates,volume_ratio=ratio,
                      note='pass仅表示需完整历史评分；不提供五因子总分或入选资格')
    except (ValueError,TypeError,KeyError,IndexError) as exc:
        result['reason']=str(exc)
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input');args=p.parse_args()
    data=json.loads(Path(args.input).read_text())
    print(json.dumps({'results':[check(s) for s in data['stocks']]},ensure_ascii=False,indent=2,allow_nan=False))
