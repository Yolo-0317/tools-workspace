import importlib.util
import sys
from pathlib import Path
import unittest
import pandas as pd

BASE = Path(__file__).resolve().parents[1]

def load():
    path = BASE / 'scripts/v3_miaoxiang.py'
    assert path.exists(), '妙想 V3 规则计算器尚未实现'
    spec = importlib.util.spec_from_file_location('v3_mx', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod

def fixture():
    dates = pd.bdate_range('2025-01-01', periods=150)
    rows=[]
    for i,d in enumerate(dates):
        close=10 + (i % 7)*0.02
        rows.append(dict(date=str(d.date()),open=close,high=close+.1,low=close-.1,close=close,volume_shares=10000,amount_yuan=6000000,pct_change=0))
    rows[-1].update(close=11,open=10.1,high=11.1,low=10,volume_shares=40000,pct_change=8)
    return dict(source='mx-finance-data',source_file='original.xlsx',as_of=rows[-1]['date'],adjustment='unadjusted',history_complete=True,code='600000.SH',bars=rows)

class MigrationTests(unittest.TestCase):
    def test_amount_conversion_preserves_old_thousand_yuan_gate(self):
        m=load(); p=fixture(); frame=m.normalize(p)
        self.assertEqual(frame.iloc[-1]['amount'],6000)
        p['bars'][-1]['amount_yuan']=4999999
        self.assertIsNone(m.score_one_stock(m.normalize(p)))
    def test_rejects_stale_duplicate_missing_and_wrong_adjustment(self):
        m=load()
        for kind in ['stale','duplicate','missing','adjustment','nan','coverage']:
            p=fixture()
            if kind=='stale': p['as_of']='2026-09-15'
            if kind=='duplicate': p['bars'].append(p['bars'][-1])
            if kind=='missing': del p['bars'][-1]['volume_shares']
            if kind=='adjustment': p['adjustment']='qfq'
            if kind=='nan': p['bars'][-1]['close']=float('nan')
            if kind=='coverage': p['history_complete']=False
            with self.subTest(kind=kind), self.assertRaises(ValueError): m.normalize(p)
    def test_breakout_gate_and_scored_output(self):
        m=load(); p=fixture(); result=m.evaluate(p)
        self.assertIsNotNone(result['score'])
        self.assertEqual(result['score']['metrics']['成交额(元)'],6000000)
        self.assertNotIn('成交额(万)',result['score']['metrics'])
        p['bars'][-1]['volume_shares']=10000
        self.assertIsNone(m.evaluate(p)['score'])
    def test_market_exclusion(self):
        m=load();p=fixture();p['code']='920001.BJ'
        with self.assertRaises(ValueError): m.normalize(p)


class LegacyParityTests(unittest.TestCase):
    def test_same_scores_as_legacy_on_diverse_daily_paths(self):
        # Load only arithmetic AST nodes: importing legacy would load .env and SQL.
        import ast, types, random
        source=BASE.parents[2]/'stock-ai/core_v3/stock_selection_five_factor_mysql.py'
        tree=ast.parse(source.read_text())
        m=load()
        names={'FactorScore','ema','calc_rsi','calc_kdj','calc_obv','choose_support_pressure','score_one_stock'}
        nodes=[]
        for n in tree.body:
            if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names:
                nodes.append(n)
            elif isinstance(n,ast.Assign) and all(isinstance(t,ast.Name) and t.id.isupper() for t in n.targets):
                try: ast.literal_eval(n.value)
                except (ValueError,TypeError): continue
                nodes.append(n)
        oracle=types.ModuleType('legacy_arithmetic');sys.modules[oracle.__name__]=oracle
        oracle.__dict__.update({k:v for k,v in m.__dict__.items() if k in ['pd','dataclass','Dict','List','Optional','Tuple'] or k.isupper()})
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),oracle.__dict__)
        from dataclasses import asdict
        matched=0
        for seed in range(40):
            p=fixture();rng=random.Random(seed);price=10.0
            for bar in p['bars']:
                previous=price;price*=1+rng.uniform(-.025,.03)
                bar.update(open=previous,close=price,high=max(previous,price)*1.01,low=min(previous,price)*.99,pct_change=(price/previous-1)*100,volume_shares=rng.randrange(5000,40000))
            frame=m.normalize(p)
            for gate in [False,True]:
                a=m.score_one_stock(frame,strict_breakout=gate)
                b=oracle.score_one_stock(frame,strict_breakout=gate)
                self.assertEqual(asdict(a) if a else None,asdict(b) if b else None)
                if a: matched+=1
        self.assertGreater(matched,30)

if __name__=='__main__': unittest.main()
