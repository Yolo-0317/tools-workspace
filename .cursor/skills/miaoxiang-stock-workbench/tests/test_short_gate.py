import unittest,importlib.util
from pathlib import Path
from test_v3 import fixture

class ShortGateTests(unittest.TestCase):
    def run_gate(self,p):
        path=Path(__file__).resolve().parents[1]/'scripts/v3_short_gate.py'
        self.assertTrue(path.exists(),'短窗口硬条件检查尚未实现')
        spec=importlib.util.spec_from_file_location('shortgate',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        return m.check(p)
    def test_short_window_preserves_breakout(self):
        p=fixture();p['bars']=p['bars'][-61:]
        self.assertEqual(self.run_gate(p)['status'],'pass')
    def test_insufficient_or_unconfirmed_is_pending_not_rejected(self):
        p=fixture();p['bars']=p['bars'][-60:]
        self.assertEqual(self.run_gate(p)['status'],'pending')
        p=fixture();p['adjustment']='unknown'
        self.assertEqual(self.run_gate(p)['status'],'pending')
    def test_current_volume_is_in_five_day_average(self):
        p=fixture();p['bars'][-1]['volume_shares']=16000
        # 16000 / ((4*10000+16000)/5) = 1.42857, not 1.6.
        self.assertEqual(self.run_gate(p)['status'],'reject')
    def test_previous_high_excludes_today(self):
        p=fixture();p['bars'][-1]['high']=20
        self.assertTrue(self.run_gate(p)['checks']['breakout_20high'])
    def test_amount_and_pct_boundaries(self):
        p=fixture();p['bars'][-1].update(amount_yuan=5000000,pct_change=3)
        self.assertEqual(self.run_gate(p)['status'],'pass')
        p['bars'][-1]['amount_yuan']=4999999
        self.assertEqual(self.run_gate(p)['status'],'reject')
