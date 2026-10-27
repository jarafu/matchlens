from datetime import date, datetime, timezone
import httpx
import pytest
from app.providers.football_data import parse_fixture, fetch_fixtures, utc_window, fetch_season_results
from app.providers.openfootball import parse_history
from app.providers.base import ProviderError


def test_lagos_calendar_boundary():
    start,end=utc_window(date(2026,10,27),'Africa/Lagos')
    assert start.isoformat() == '2026-10-26T23:00:00+00:00'
    assert end.isoformat() == '2026-10-27T23:00:00+00:00'


def sample():
    return dict(id=1,utcDate='2026-10-26T23:30:00Z',status='TIMED',competition={'code':'PL'},homeTeam={'id':57,'name':'Arsenal FC'},awayTeam={'id':61,'name':'Chelsea FC'},score={'duration':'REGULAR','fullTime':{'home':None,'away':None}})


def test_valid_and_malformed_fixture():
    f=parse_fixture(sample())
    assert f['home']=='Arsenal FC' and f['status']=='SCHEDULED'
    bad=sample();bad['utcDate']='not a date'
    with pytest.raises(ValueError): parse_fixture(bad)
    bad=sample();bad['homeTeam']['id']=None
    with pytest.raises(ValueError): parse_fixture(bad)


def test_quota_and_auth_errors_hide_token():
    for status in [401,429,500]:
        client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'message':'secret-token'})))
        with pytest.raises(ProviderError) as e:
            fetch_fixtures('secret-token',date(2026,10,27),client=client)
        assert 'secret-token' not in str(e.value)


def test_parse_history_excludes_unplayed_extra_time_and_invalid():
    payload={'matches':[
        {'date':'2024-01-01','team1':'A','team2':'B','score':{'ft':[2,1]}},
        {'date':'2024-01-02','team1':'A','team2':'B'},
        {'date':'2024-01-03','team1':'A','team2':'B','score':{'et':[3,2]}},
        {'date':'2024-01-04','team1':'A','team2':'B','score':{'ft':[-1,2]}}]}
    rows=parse_history(payload,'PL','revision')
    assert len(rows)==1 and rows[0]['hg']==2


def test_current_season_results_are_regulation_only():
    regular=sample();regular['status']='FINISHED';regular['score']['fullTime']={'home':2,'away':1}
    extra=sample();extra['id']=2;extra['status']='FINISHED';extra['score']={'duration':'EXTRA_TIME','fullTime':{'home':3,'away':2}}
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'matches':[regular,extra]})))
    result=fetch_season_results('test-token','PL',client=client)
    assert len(result)==1 and result[0]['hg']==2
