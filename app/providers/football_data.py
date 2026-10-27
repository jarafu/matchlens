from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import httpx
from app.domain import stamp, parse_time
from app.providers.base import get_json, ProviderError


def utc_window(day,tz='Africa/Lagos'):
    start=datetime.combine(day,time.min,ZoneInfo(tz));end=start+timedelta(days=1)
    return start.astimezone(timezone.utc),end.astimezone(timezone.utc)


def parse_fixture(row):
    kickoff=parse_time(row['utcDate'])
    if not row.get('id') or not row['homeTeam'].get('id') or not row['awayTeam'].get('id'): raise ValueError('Missing fixture identity')
    status=row['status'];status='SCHEDULED' if status in {'TIMED','SCHEDULED'} else status
    score=row.get('score') or {};ft=score.get('fullTime') or {};hg,ag=ft.get('home'),ft.get('away')
    if score.get('duration')!='REGULAR': hg=ag=None
    if hg is not None and (type(hg)!=int or type(ag)!=int or hg<0 or ag<0): raise ValueError('Invalid score')
    return {'id':f"fd:{row['id']}",'competition':row['competition']['code'],'home':row['homeTeam']['name'],'away':row['awayTeam']['name'],
            'kickoff':kickoff.isoformat(),'fetched_at':stamp(),'status':status,'source':'football-data.org','hg':hg,'ag':ag}


def fetch_fixtures(token,day,timezone_name='Africa/Lagos',client=None):
    if not token: raise ProviderError('Football-data API key is not configured')
    start,end=utc_window(day,timezone_name)
    own=client is None;client=client or httpx.Client(timeout=25)
    try:
        payload=get_json(client,'https://api.football-data.org/v4/matches',headers={'X-Auth-Token':token},params={'dateFrom':start.date().isoformat(),'dateTo':end.date().isoformat()})
        if not isinstance(payload.get('matches'),list): raise ProviderError('Provider returned no valid fixture list')
        fixtures=[]
        for row in payload['matches']:
            try: parsed=parse_fixture(row)
            except (KeyError,ValueError,TypeError): continue
            if start<=parse_time(parsed['kickoff'])<end: fixtures.append(parsed)
        return fixtures
    finally:
        if own: client.close()


def fetch_season_results(token,competition,client=None):
    if not token: raise ProviderError('Football-data API key is not configured')
    if not competition.isalnum(): raise ValueError('Invalid competition code')
    own=client is None;client=client or httpx.Client(timeout=30)
    try:
        payload=get_json(client,f'https://api.football-data.org/v4/competitions/{competition}/matches',headers={'X-Auth-Token':token},params={'status':'FINISHED'})
        if not isinstance(payload.get('matches'),list): raise ProviderError('Provider returned no valid result list')
        result=[]
        for row in payload['matches']:
            try: parsed=parse_fixture(row)
            except (ValueError,KeyError,TypeError): continue
            if parsed['status']=='FINISHED' and parsed['hg'] is not None and parsed['ag'] is not None: result.append(parsed)
        return result
    finally:
        if own: client.close()
