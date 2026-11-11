import importlib.util
import itertools
from collections import Counter
import pytest

def core():
    assert importlib.util.find_spec('zhouyi.core'), '起卦核心尚未实现'
    from zhouyi import core
    return core

def coins(values):
    return [{6:[2,2,2],7:[2,2,3],8:[2,3,3],9:[3,3,3]}[v] for v in values]

def test_known_casts_and_bottom_up_order():
    c=core()
    result=c.describe_cast(coins([9]*6))
    assert (result['original_id'],result['changed_id'],result['moving'])==(1,2,[1,2,3,4,5,6])
    assert c.describe_cast(coins([9,7,7,7,7,7]))['changed_id']==44
    assert c.describe_cast(coins([7,8,8,8,7,8]))['original_id']==3
    assert c.describe_cast(coins([8,7,8,8,8,7]))['original_id']==4

def test_coin_distribution_exercises_cast(monkeypatch):
    c=core()
    got=[]
    for combo in itertools.product((2,3),repeat=3):
        seq=iter(combo*6)
        monkeypatch.setattr(c.secrets,'choice',lambda options: next(seq))
        got.append(c.describe_cast(c.cast_coins())['values'][0])
    assert Counter(got)=={6:1,7:3,8:3,9:1}

@pytest.mark.parametrize('bad',[[],[[2,2,2]]*5,[[2,2]]*6,[[2,2,4]]*6,[[2,2,3.0]]*6,[[2,2,True]]*6,None])
def test_reject_invalid_coins(bad):
    with pytest.raises(ValueError): core().describe_cast(bad)
