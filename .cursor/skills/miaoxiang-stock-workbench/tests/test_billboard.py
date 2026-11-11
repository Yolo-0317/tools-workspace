import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[1]/'scripts/billboard_input.py'
spec=importlib.util.spec_from_file_location('billboard_input',PATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fixture():
    tables=[]
    for side in ['买入','卖出']:
        tables.append({'code':'002185.SZ','inputTitle':f'华天科技龙虎榜单前5{side}营业部(2026-09-18，上榜原因：测试)',
        'field':{'startDate':'2026-09-18 00:00:00','endDate':'2026-09-18 00:00:00'},
        'nameMap':{'0':'机构专用','1':'机构专用'},'indicatorOrder':['0','1'],
        'rawTable':{'headName':[side+'金额(万元)'],'0':['1234.56789'],'1':['2345.67891']},
        'table':{'headName':[side+'金额(万元)'],'0':['1234.57'],'1':['2345.68']}})
    return {'status':0,'data':{'data':{'searchDataResultDTO':{'dataTableDTOList':tables}}}}

class BillboardTests(unittest.TestCase):
    def test_duplicate_seats_and_raw_precision(self):
        rows=m.parse(fixture(),'002185.SZ','2026-09-18')
        self.assertEqual(len(rows),4)
        self.assertEqual([x['seat_id'] for x in rows[:2]],['0','1'])
        self.assertEqual(rows[0]['amount_wan'],'1234.56789')
        self.assertEqual(rows[0]['name'],rows[1]['name'])
        self.assertFalse(rows[0]['top5_complete'])
    def test_wrong_date_and_entity_rejected(self):
        for code,day in [('600000.SH','2026-09-18'),('002185.SZ','2026-09-17')]:
            with self.assertRaises(ValueError):m.parse(fixture(),code,day)
    def test_missing_and_business_failure_not_no_listing(self):
        for data in [{}, {'status':113,'message':'limit'}, {'status':0,'data':{}}]:
            with self.assertRaises(ValueError):m.parse(data,'002185.SZ','2026-09-18')
    def test_incomplete_amount_rejected(self):
        r=fixture();r['data']['data']['searchDataResultDTO']['dataTableDTOList'][0]['rawTable']['1'][0]='-'
        with self.assertRaises(ValueError):m.parse(r,'002185.SZ','2026-09-18')

if __name__=='__main__':unittest.main()
