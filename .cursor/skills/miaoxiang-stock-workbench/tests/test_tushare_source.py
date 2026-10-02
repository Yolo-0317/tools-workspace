import unittest,importlib.util
from pathlib import Path
from test_v3 import fixture,load

class TushareSourceTests(unittest.TestCase):
    def test_tushare_source_accepted_by_v3(self):
        p=fixture();p['source']='tushare-daily'
        self.assertEqual(len(load().normalize(p)),150)
    def adapter(self):
        path=Path(__file__).resolve().parents[1]/'scripts/tushare_daily_input.py'
        self.assertTrue(path.exists(),'Tushare日线适配器尚未实现')
        spec=importlib.util.spec_from_file_location('tsadapter',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    def test_units_and_calendar_validation(self):
        m=self.adapter();rows=[dict(ts_code='000001',exch_code='SZ',trade_date='2026-09-15',open=10,high=11,low=9,close=10.5,vol=1234,amount=5678,pct_chg=5)]
        p=m.convert(rows,'000001.SZ','2026-09-15','db-export.json',['2026-09-15'])
        self.assertEqual(p['bars'][0]['volume_shares'],123400)
        self.assertEqual(p['bars'][0]['amount_yuan'],5678000)
        self.assertTrue(p['history_complete'])
        p=m.convert(rows,'000001.SZ','2026-09-15','db-export.json',['2026-09-14','2026-09-15'])
        self.assertFalse(p['history_complete'])
    def test_missing_calendar_never_implies_complete(self):
        p=self.adapter().convert([], '000001.SZ','2026-09-15','db-export.json',None)
        self.assertFalse(p['history_complete'])
    def test_wrong_entity_rejected(self):
        m=self.adapter()
        with self.assertRaises(ValueError):m.convert([{'ts_code':'600000','exch_code':'SH'}],'000001.SZ','2026-09-15','x',None)

    def test_legacy_missing_exchange_with_matching_code(self):
        m=self.adapter()
        row=dict(ts_code='000001',exch_code=None,trade_date='2026-03-19',open=10,high=11,low=9,close=10,vol=100,amount=100,pct_chg=0)
        p=m.convert([row],'000001.SZ','2026-03-19','raw.json',['2026-03-19'])
        self.assertTrue(p['history_complete'])

    def test_identical_legacy_duplicates_merge_conflicts_reject(self):
        m=self.adapter()
        a=dict(ts_code='000001',exch_code='SZ',trade_date='2026-05-18',open=10,high=11,low=9,close=10,vol=100,amount=100,pct_chg=0)
        b=dict(a,ts_code='000001.SZ')
        self.assertEqual(len(m.convert([a,b],'000001.SZ','2026-05-18','raw',['2026-05-18'])['bars']),1)
        b['close']=10.1
        with self.assertRaises(ValueError):m.convert([a,b],'000001.SZ','2026-05-18','raw',['2026-05-18'])
