import argparse
import getpass
import hashlib
import json
import sys
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from app.config import Settings
from app.db import connect
from app.domain import now, stamp
from app.models import JobLock, Result, ModelVersion, Audit
from app.providers.openfootball import import_history
from app.providers.football_data import fetch_fixtures, fetch_season_results
from app.providers.base import ProviderError
from app.data.ingest import ingest_history, ingest_fixtures
from app.model.validation import evaluate_model
from app.analysis.service import analyse_day, settle_predictions


@contextmanager
def job_lock(factory,name,minutes=120):
    expiry=(now()+timedelta(minutes=minutes)).isoformat()
    with factory() as db:
        db.execute(delete(JobLock).where(JobLock.name==name,JobLock.expires_at<stamp()));db.commit()
        try:
            db.add(JobLock(name=name,expires_at=expiry));db.commit()
        except IntegrityError:
            db.rollback();raise RuntimeError('This job is already running') from None
    try: yield
    finally:
        with factory() as db:
            db.execute(delete(JobLock).where(JobLock.name==name,JobLock.expires_at==expiry));db.commit()


def train_all(factory):
    report={'created_at':stamp(),'competitions':{}}
    with job_lock(factory,'train'):
        with factory() as db:
            codes=list(db.scalars(select(Result.competition).distinct()))
        for code in codes:
            with factory() as db:
                history=[{k:getattr(r,k) for k in ['home','away','date','hg','ag']} for r in db.scalars(select(Result).where(Result.competition==code,Result.date<now().date().isoformat()).order_by(Result.date))]
            try:
                params,validation=evaluate_model(history)
                mid=hashlib.sha256(json.dumps({'competition':code,'parameters':params,'validation':validation},sort_keys=True).encode()).hexdigest()
                enabled=any(v['enabled'] for v in validation['markets'].values())
                with factory() as db:
                    if not db.get(ModelVersion,mid):
                        if enabled:
                            for old in db.scalars(select(ModelVersion).where(ModelVersion.competition==code)): old.active=False
                        db.add(ModelVersion(id=mid,competition=code,created_at=stamp(),parameters=params,validation=validation,active=enabled))
                    db.add(Audit(kind='model_evaluated',at=stamp(),detail={'competition':code,'model_id':mid,'enabled':enabled}));db.commit()
                report['competitions'][code]=validation
            except ValueError as exc:
                report['competitions'][code]={'error':str(exc)}
            print(f'Evaluated {code}',file=sys.stderr,flush=True)
    return report


def sync_results(factory,token,competitions):
    from app.data.identity import resolve
    from app.domain import parse_time
    from zoneinfo import ZoneInfo
    import time
    report={'updated':0,'unresolved':0,'errors':{}}
    zones={'PL':'Europe/London','BL1':'Europe/Berlin','PD':'Europe/Madrid','SA':'Europe/Rome','FL1':'Europe/Paris'}
    with job_lock(factory,'sync-results'):
        for index,code in enumerate(competitions):
            if index: time.sleep(6.2)  # shared free-provider rate allowance
            try: fixtures=fetch_season_results(token,code)
            except ProviderError as exc: report['errors'][code]=str(exc);continue
            with factory() as db:
                known={name for r in db.scalars(select(Result).where(Result.competition==code)) for name in (r.home,r.away)}
                rows=[]
                for f in fixtures:
                    home,away=resolve(f['home'],known),resolve(f['away'],known)
                    if not home or not away: report['unresolved']+=1;continue
                    day=parse_time(f['kickoff']).astimezone(ZoneInfo(zones.get(code,'UTC'))).date().isoformat()
                    rid=hashlib.sha256(f'{code}|{day}|{home}|{away}'.encode()).hexdigest()
                    rows.append({'id':rid,'competition':code,'home':home,'away':away,'date':day,'hg':f['hg'],'ag':f['ag'],'revision':f'football-data.org:{f["id"]}:{f["fetched_at"]}'})
                ingest_fixtures(db,fixtures)
                report['updated']+=ingest_history(db,rows)
    return report


def main():
    parser=argparse.ArgumentParser(description='MatchLens data and model jobs')
    parser.add_argument('command',choices=['setup','init','history','sync-results','train','ingest','predict','settle','check-coverage','odds'])
    parser.add_argument('--seasons',default='2022-23,2023-24,2024-25,2025-26,2026-27')
    parser.add_argument('--competitions',default='PL,BL1,PD,SA,FL1')
    parser.add_argument('--date',type=date.fromisoformat,default=None)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args();settings=Settings()
    from zoneinfo import ZoneInfo
    day=args.date or now().astimezone(ZoneInfo(settings.timezone)).date()
    try:
        if args.command=='setup':
            from app.web.auth import hash_password,save_secret
            if settings.password_hash: raise ValueError('Owner already configured; use hosting secrets or edit local configuration to rotate credentials')
            password=getpass.getpass('Create owner password (12+ characters): ')
            if len(password)<12 or password!=getpass.getpass('Repeat password: '): raise ValueError('Passwords must match and contain at least 12 characters')
            token=getpass.getpass('Football-data API key (blank to add later): ').strip()
            save_secret(settings,'OWNER_PASSWORD_HASH',hash_password(password))
            if token: save_secret(settings,'FOOTBALL_DATA_TOKEN',token)
            print('Local owner configured. Keep .env private.');return
        factory=connect(settings.database_url)
        if args.command=='init': report={'database':'ready'}
        elif args.command=='history':
            with job_lock(factory,'history'):
                rows,report=import_history(args.seasons.split(','),args.competitions.split(','))
                with factory() as db: report['inserted']=ingest_history(db,rows)
        elif args.command=='train': report=train_all(factory)
        elif args.command=='sync-results': report=sync_results(factory,settings.football_token,args.competitions.split(','))
        elif args.command=='ingest':
            with job_lock(factory,'refresh'):
                rows=fetch_fixtures(settings.football_token,day,settings.timezone)
                with factory() as db: ingest_fixtures(db,rows)
                report={'fixtures':len(rows),'day':str(day)}
        elif args.command=='predict':
            with job_lock(factory,'predict'):
                with factory() as db: report=analyse_day(db,day,settings.timezone)
        elif args.command=='settle':
            with factory() as db: report={'settled_or_corrected':settle_predictions(db)}
        elif args.command=='odds':
            from app.providers.odds_api import refresh_reference_odds
            with job_lock(factory,'odds'):
                with factory() as db: report=refresh_reference_odds(db,settings.odds_key,day,args.competitions.split(','))
        else:
            with factory() as db:
                report={'api_configured':bool(settings.football_token),'models':[{'competition':m.competition,'id':m.id,'active':m.active} for m in db.scalars(select(ModelVersion))]}
        if args.report:
            args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2))
            print(f'Report saved to {args.report}')
        else: print(json.dumps(report,indent=2))
    except (ValueError,RuntimeError,ProviderError) as exc:
        print(str(exc),file=sys.stderr);sys.exit(1)


if __name__=='__main__': main()
