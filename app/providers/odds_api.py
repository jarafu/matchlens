import hashlib
import math
from datetime import timedelta
import httpx
from sqlalchemy import select
from app.domain import now, stamp, parse_time
from app.models import Fixture, Odds, AppSetting
from app.providers.base import get_json, ProviderError
from app.providers.football_data import utc_window

SPORT_KEYS={'PL':'soccer_epl','BL1':'soccer_germany_bundesliga','PD':'soccer_spain_la_liga','SA':'soccer_italy_serie_a','FL1':'soccer_france_ligue_one'}


def normalise_markets(event,fixture_id,region):
    rows=[]
    for bookmaker in event.get('bookmakers',[]):
        for market in bookmaker.get('markets',[]):
            updated=market.get('last_update') or bookmaker.get('last_update')
            if not updated: continue
            try: captured=parse_time(updated).isoformat()
            except ValueError: continue
            for out in market.get('outcomes',[]):
                name=out.get('name');point=out.get('point');key=None
                if market['key'] in {'totals','alternate_totals'}:
                    if name=='Over' and point==1.5: key='over15'
                    elif name=='Under' and point==4.5: key='under45'
                elif market['key']=='btts' and name in {'Yes','No'}: key='btts_yes' if name=='Yes' else 'btts_no'
                elif market['key'] in {'team_totals','alternate_team_totals'} and name=='Over' and point==.5:
                    team=out.get('description');key='home05' if team==event.get('home_team') else 'away05' if team==event.get('away_team') else None
                price=out.get('price')
                if not key or not isinstance(price,(float,int)) or not math.isfinite(price) or price<=1: continue
                identity=f'{fixture_id}|{key}|{bookmaker["key"]}|{captured}'
                rows.append({'id':hashlib.sha256(identity.encode()).hexdigest(),'fixture_id':fixture_id,'market':key,'price':price,
                             'bookmaker':bookmaker.get('title',bookmaker['key']),'captured_at':captured,'region':region,'verified':False})
    return rows


def refresh_reference_odds(db,key,day,competitions):
    if not key: raise ProviderError('Optional odds API key is not configured')
    # Budget is shared by local and scheduled callers through the database.
    month=now().strftime('%Y-%m');setting_key=f'odds-budget:{month}'
    budget=db.get(AppSetting,setting_key)
    spent=budget.value.get('credits',0) if budget else 0
    if spent>=400: raise ProviderError('Local monthly odds budget reached; 100 credits reserved')
    start,end=utc_window(day);total=0;unmatched=0
    with httpx.Client(timeout=25) as client:
        for code in competitions:
            if code not in SPORT_KEYS or spent+2>400: continue
            cache_key=f'odds-refresh:{code}:{day}'
            if db.get(AppSetting,cache_key): continue
            # Reserve credits before the request, including failures. One region, two markets.
            spent+=2
            if not budget: budget=AppSetting(key=setting_key,value={'credits':spent});db.add(budget)
            else: budget.value={'credits':spent}
            db.commit()
            data=get_json(client,f'https://api.the-odds-api.com/v4/sports/{SPORT_KEYS[code]}/odds',params={'apiKey':key,'regions':'uk','markets':'totals,h2h','oddsFormat':'decimal'})
            fixtures=list(db.scalars(select(Fixture).where(Fixture.competition==code,Fixture.kickoff>=start.isoformat(),Fixture.kickoff<end.isoformat())))
            def canonical(name): return name.removesuffix(' FC').casefold().strip()
            for event in data:
                matches=[f for f in fixtures if canonical(f.home)==canonical(event['home_team']) and canonical(f.away)==canonical(event['away_team']) and abs((parse_time(f.kickoff)-parse_time(event['commence_time'])).total_seconds())<60]
                if len(matches)!=1: unmatched+=1;continue
                for row in normalise_markets(event,matches[0].id,'uk'):
                    if not db.get(Odds,row['id']): db.add(Odds(**row));total+=1
            db.add(AppSetting(key=cache_key,value={'at':stamp()}));db.commit()
    return {'quotes':total,'unmatched_events':unmatched,'estimated_monthly_credits':spent,'scope':'Reference prices only; Nigeria availability unverified','limitation':'Standard totals feed may not include 1.5/4.5 lines; no price is substituted'}
