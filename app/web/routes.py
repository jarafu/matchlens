from datetime import date
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select, func
from app.models import Fixture, Result, ModelVersion, Prediction, Audit
from app.domain import now
from app.providers.football_data import utc_window, fetch_fixtures
from app.providers.base import ProviderError
from app.data.ingest import ingest_fixtures
from app.analysis.service import fixture_dict, analyse_fixture, analyse_day
from app.providers.openfootball import COMPETITIONS

router=APIRouter(prefix='/api')


@router.post('/settings/token')
async def token_settings(request: Request):
    from app.web.auth import require_local, save_secret
    require_local(request)
    payload=await request.json();token=str(payload.get('token','')).strip()
    if not token.isascii() or not token.replace('-','').replace('_','').isalnum() or not 8<=len(token)<=200: raise HTTPException(422,'Enter the API key exactly as provided, with no spaces')
    save_secret(request.app.state.settings,'FOOTBALL_DATA_TOKEN',token)
    request.app.state.settings.football_token=token
    return {'saved':True}


def chosen_day(request,day):
    if not day: return now().astimezone(ZoneInfo(request.app.state.settings.timezone)).date()
    try: return date.fromisoformat(day)
    except ValueError: raise HTTPException(422,'Use a YYYY-MM-DD date')


@router.get('/fixtures')
def fixtures(request: Request,day: str|None=None):
    target=chosen_day(request,day);start,end=utc_window(target,request.app.state.settings.timezone)
    with request.app.state.db() as db:
        rows=list(db.scalars(select(Fixture).where(Fixture.kickoff>=start.isoformat(),Fixture.kickoff<end.isoformat()).order_by(Fixture.kickoff)))
        return {'date':str(target),'fixtures':[fixture_dict(f) for f in rows],'api_configured':bool(request.app.state.settings.football_token)}


@router.post('/fixtures/{fixture_id}/analyse')
def analyse(request: Request,fixture_id: str):
    with request.app.state.db() as db: return analyse_fixture(db,fixture_id)


@router.post('/analyse-day')
def analyse_all(request: Request,day: str|None=None):
    with request.app.state.db() as db: return analyse_day(db,chosen_day(request,day),request.app.state.settings.timezone)


@router.post('/refresh')
def refresh(request: Request,day: str|None=None):
    from app.jobs import job_lock
    settings=request.app.state.settings
    try:
        with job_lock(request.app.state.db,'refresh',minutes=5):
            with request.app.state.db() as db:
                latest=db.scalar(select(Audit).where(Audit.kind=='fixtures_ingested').order_by(Audit.at.desc()))
                from app.domain import parse_time
                if latest and (now()-parse_time(latest.at)).total_seconds()<600:
                    raise HTTPException(429,'Fixtures were refreshed recently. Please wait 10 minutes to preserve the free quota.')
                data=fetch_fixtures(settings.football_token,chosen_day(request,day),settings.timezone)
                ingest_fixtures(db,data)
                return {'count':len(data)}
    except ProviderError as exc: raise HTTPException(503,str(exc))
    except RuntimeError as exc: raise HTTPException(409,str(exc))


@router.get('/coverage')
def coverage(request: Request):
    with request.app.state.db() as db:
        counts=dict(db.execute(select(Result.competition,func.count()).group_by(Result.competition)).all())
        models=list(db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())))
        items=[]
        for code,(file,name) in COMPETITIONS.items():
            model=next((m for m in models if m.competition==code),None)
            active=next((m for m in models if m.competition==code and m.active),None)
            items.append({'code':code,'name':name,'history_count':counts.get(code,0),'enabled_markets':[k for k,v in active.validation['markets'].items() if v['enabled']] if active else [],
                          'validation':model.validation if model else None,'model_date':active.created_at if active else None})
        recent=list(db.scalars(select(Audit).order_by(Audit.id.desc()).limit(8)))
        return {'competitions':items,'api_configured':bool(request.app.state.settings.football_token),'odds_configured':bool(request.app.state.settings.odds_key),
                'timezone':request.app.state.settings.timezone,'events':[{'kind':a.kind,'at':a.at,'detail':a.detail} for a in recent]}


@router.post('/model-refresh')
def model_refresh(request: Request):
    from app.jobs import sync_results,train_all,job_lock,report_failed
    if not request.app.state.settings.football_token: raise HTTPException(422,'Connect your API key first')
    try:
        with job_lock(request.app.state.db,'model-refresh'):
            sync=sync_results(request.app.state.db,request.app.state.settings.football_token,['PL','BL1','PD','SA','FL1'])
            report=train_all(request.app.state.db)
            partial=report_failed('sync-results',sync) or report_failed('train',report)
            return {'sync':sync,'evaluated':len(report['competitions']),'status':'partial' if partial else 'complete'}
    except RuntimeError as exc: raise HTTPException(409,str(exc))


@router.get('/history')
def history(request: Request):
    with request.app.state.db() as db:
        rows=list(db.scalars(select(Prediction).order_by(Prediction.created_at.desc()).limit(200)))
        return {'predictions':[{'id':p.id,'fixture':fixture_dict(db.get(Fixture,p.fixture_id)),'market':p.market,'probability':p.probability,'created_at':p.created_at,'won':p.won,'valid':p.valid,'model_id':p.model_id} for p in rows if db.get(Fixture,p.fixture_id)]}
