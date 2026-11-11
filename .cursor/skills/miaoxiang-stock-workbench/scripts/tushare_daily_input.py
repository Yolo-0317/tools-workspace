"""Read existing Tushare stock_daily, converting lots/thousand yuan to shares/yuan."""
from datetime import date,timedelta
import json,re
from pathlib import Path


def convert(rows,code,as_of,source_file,expected_dates=None):
    if not re.fullmatch(r'(?:60\d{4}|68\d{4})\.SH|(?:00\d{4}|30\d{4})\.SZ',code):
        raise ValueError('需要标准沪深A股代码')
    end=date.fromisoformat(as_of);start=end-timedelta(days=450);bars=[]
    for r in rows:
        raw=str(r['ts_code']);exchange=r.get('exch_code')
        if exchange in (None,'','None') and raw.zfill(6)==code.split('.')[0]:
            exchange=code.split('.')[1]
        actual=raw if '.' in raw else raw.zfill(6)+'.'+str(exchange)
        if actual!=code:raise ValueError('日线实体不一致')
        d=str(r['trade_date'])[:10]
        if not str(start)<=d<=as_of:continue
        bars.append({'date':d,**{k:float(r[k]) for k in ['open','high','low','close']},
                     'volume_shares':float(r['vol'])*100,'amount_yuan':float(r['amount'])*1000,
                     'pct_change':float(r['pct_chg'])})
    unique={}
    for bar in bars:
        d=bar['date']
        if d in unique and unique[d]!=bar:raise ValueError('重复日线数值冲突')
        unique[d]=bar
    bars=sorted(unique.values(),key=lambda b:b['date']);dates=[b['date'] for b in bars]
    expected={d for d in (expected_dates or []) if str(start)<=d<=as_of}
    complete=bool(expected and as_of in expected and set(dates)==expected)
    return {'source':'tushare-daily','source_file':str(source_file),'code':code,'as_of':as_of,
            'adjustment':'unadjusted','history_complete':complete,'bars':bars,
            'coverage':{'missing':sorted(expected-set(dates)),'unexpected':sorted(set(dates)-expected) if expected else [],
                        'calendar_provided':bool(expected),'note':'停牌或新股缺口需单独核验，不能补零'}}


def main():
    import argparse,os
    from dotenv import dotenv_values
    from sqlalchemy import create_engine,text,bindparam
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codes',nargs='+',required=True)
    parser.add_argument('--as-of',required=True)
    parser.add_argument('--env',required=True)
    parser.add_argument('--calendar',help='JSON array of verified expected YYYY-MM-DD dates covering the full requested window')
    parser.add_argument('--output',required=True)
    args=parser.parse_args();end=date.fromisoformat(args.as_of);start=end-timedelta(days=450)
    for code in args.codes:convert([],code,args.as_of,'check')
    dates=json.loads(Path(args.calendar).read_text()) if args.calendar else None
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    raw_path=target.with_name(target.stem+'-raw.json')
    if target.exists() or raw_path.exists():raise SystemExit('输出已存在，请选择新的运行文件名')
    url=dotenv_values(args.env).get('MYSQL_URL') or os.environ.get('MYSQL_URL')
    if not url:raise SystemExit('MYSQL_URL未配置')
    engine=create_engine(url.replace('host.docker.internal','127.0.0.1'),pool_pre_ping=True)
    query=text('SELECT ts_code, exch_code, trade_date, open, high, low, close, pct_chg, vol, amount FROM stock_daily WHERE ts_code IN :codes AND trade_date BETWEEN :start AND :end ORDER BY ts_code, trade_date').bindparams(bindparam('codes',expanding=True))
    try:
        with engine.connect() as conn:
            rows=[dict(r) for r in conn.execute(query,{'codes':list(set(args.codes+[c.split('.')[0] for c in args.codes])),'start':start,'end':end}).mappings()]
    except Exception:
        raise SystemExit('日线库读取失败；未输出连接信息，请检查本地数据库可用性')
    finally:engine.dispose()
    raw_path.write_text(json.dumps(rows,ensure_ascii=False,default=str))
    stocks=[]
    for code in args.codes:
        selected=[r for r in rows if str(r['ts_code']).split('.')[0]==code.split('.')[0]]
        stocks.append(convert(selected,code,args.as_of,str(raw_path.resolve()),dates))
    target.write_text(json.dumps({'stocks':stocks},ensure_ascii=False,indent=2,allow_nan=False))
    print(json.dumps({'output':str(target.resolve()),'stocks':len(stocks),'complete':sum(p['history_complete'] for p in stocks)},ensure_ascii=False))

if __name__=='__main__':main()
