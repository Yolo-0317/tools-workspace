import importlib.util
import pytest
from zhouyi.core import describe_cast
from test_core import coins

def select(values):
    assert importlib.util.find_spec('zhouyi.rules'), '变占规则尚未实现'
    from zhouyi.rules import select_passages
    return select_passages(describe_cast(coins(values)))

@pytest.mark.parametrize('values,primary,secondary',[
 ([7]*6,(1,'judgment',None),None),
 ([9,7,7,7,7,7],(1,'line',1),None),
 ([9,7,7,7,7,9],(1,'line',6),(1,'line',1)),
 ([9,7,7,7,9,9],(1,'judgment',None),(32,'judgment',None)),
 ([7,9,9,9,7,7],(42,'judgment',None),(1,'judgment',None)),
 ([6,7,7,7,9,9],(44,'judgment',None),(34,'judgment',None)),
 ([8,9,9,9,7,7],(20,'judgment',None),(44,'judgment',None)),
 ([9,9,7,7,9,9],(62,'line',3),(62,'line',4)),
 ([9,9,9,9,9,7],(23,'line',6),None),
 ([9]*6,(1,'use',None),None),
 ([6]*6,(2,'use',None),None),
 ([6,9,9,9,9,9],(24,'judgment',None),None),
])
def test_passage_selection(values,primary,secondary):
    selected=select(values)
    def item(t): return {'hexagram_id':t[0],'kind':t[1],'position':t[2]}
    assert selected['primary']==[item(primary)]
    assert selected['secondary']==([item(secondary)] if secondary else [])
    assert selected['version'] and selected['reason']
