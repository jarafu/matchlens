from datetime import date
from app.providers.odds_api import normalise_markets


def test_only_exact_market_lines_accepted_and_reference_labelled():
    event={'id':'e1','home_team':'Arsenal','away_team':'Chelsea','commence_time':'2026-10-27T15:00:00Z',
           'bookmakers':[{'key':'example','title':'Example','last_update':'2026-10-27T08:00:00Z','markets':[
               {'key':'totals','outcomes':[{'name':'Over','point':1.5,'price':1.3},{'name':'Over','point':2.5,'price':1.8},{'name':'Under','point':4.5,'price':1.2}]},
               {'key':'btts','outcomes':[{'name':'Yes','price':1.7},{'name':'No','price':2.1}]}]}]}
    result=normalise_markets(event,'fd:1','uk')
    assert {r['market'] for r in result}=={'over15','under45','btts_yes','btts_no'}
    assert not any(r['verified'] for r in result)
    assert all(r['captured_at']=='2026-10-27T08:00:00+00:00' for r in result)


def test_missing_quote_timestamp_is_not_invented():
    event={'bookmakers':[{'key':'example','markets':[{'key':'totals','outcomes':[{'name':'Over','point':1.5,'price':1.3}]}]}]}
    assert normalise_markets(event,'fd:1','uk')==[]
