import pytest
from app.analysis.value import assess_value, rank


def test_high_probability_can_have_negative_value():
    v=assess_value(.8,1.2)
    assert v['expected_return']==pytest.approx(-.04)
    assert v['label']=='Negative value'
    assert assess_value(.8,None)['label']=='Value unavailable'


def test_probability_is_primary():
    items=[dict(probability=.8,value={'expected_return':.2}),dict(probability=.81,value={'expected_return':-.1})]
    assert rank(items)[0]['probability']==.81


@pytest.mark.parametrize('p,odds',[(1.1,2),(-.1,2),(.8,1),(.8,float('nan'))])
def test_invalid_value_inputs(p,odds):
    with pytest.raises(ValueError): assess_value(p,odds)
