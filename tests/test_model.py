import math
import numpy as np
import pytest
from app.model.poisson import score_grid, fit_model, rates
from app.model.markets import probabilities, settle
from app.model.validation import metrics, split_history, activation


def test_market_math_and_coherence():
    grid = score_grid(1.7, 0.9)
    p = probabilities(grid)
    assert p["over15"] == pytest.approx(1-math.exp(-2.6)*3.6, abs=1e-8)
    assert p["home05"] == pytest.approx(1-math.exp(-1.7), abs=1e-8)
    assert p["btts_yes"] + p["btts_no"] == pytest.approx(1)
    assert p["btts_yes"] <= min(p["home05"],p["away05"],p["over15"])
    assert p["dc_1x"] == pytest.approx(1 - np.triu(grid,1).sum())
    assert grid.sum() == pytest.approx(1,abs=1e-8)
    assert all(0 <= v <= 1 for v in p.values())


@pytest.mark.parametrize("market,home,away,want",[("over15",1,1,True),("under45",3,2,False),("dc_12",1,1,False),("btts_no",0,2,True),("home05",0,2,False),("away05",0,2,True),("dc_x2",1,1,True)])
def test_settlement(market,home,away,want):
    assert settle(market,home,away) is want


@pytest.mark.parametrize("a,b",[(float('nan'),1),(-1,2),(float('inf'),2),(1000,1)])
def test_invalid_rates_refused(a,b):
    with pytest.raises(ValueError): score_grid(a,b)


def test_leakage_and_unknown_team():
    rows=[dict(home="A",away="B",hg=2,ag=1,date=f"2020-01-{i:02d}") for i in range(1,20)]
    fit1=fit_model(rows,"2020-02-01")
    fit2=fit_model(rows+[dict(home="A",away="B",hg=9,ag=0,date="2030-01-01")],"2020-02-01")
    assert rates(fit1,"A","B") == pytest.approx(rates(fit2,"A","B"))
    with pytest.raises(ValueError, match="history"): rates(fit1,"New","B")


def test_validation_and_splits():
    report=metrics([.8,.8,.8,.8,.8],[1,1,1,1,0])
    assert report['brier'] == pytest.approx(.16)
    assert report['ece'] == pytest.approx(0)
    assert activation(dict(n=10,ece=0,brier=.1,logloss=.2,baseline_brier=.2,baseline_logloss=.4)) is False
    rows=[dict(date=f"2020-{i//28+1:02d}-{i%28+1:02d}") for i in range(100)]
    a,b,c=split_history(rows)
    assert max(x['date'] for x in a)<min(x['date'] for x in b)<min(x['date'] for x in c)


def test_date_groups_never_cross_splits():
    rows=[dict(date=f"2020-01-{i//10+1:02d}") for i in range(100)]
    a,b,c=split_history(rows)
    assert not ({r['date'] for r in a} & {r['date'] for r in b})
    assert not ({r['date'] for r in b} & {r['date'] for r in c})
