import hashlib
import json
from datetime import timedelta
from sqlalchemy import select
from app.domain import now, stamp, parse_time
from app.models import Fixture, ModelVersion, Prediction, Odds, Audit
from app.model.poisson import rates, score_grid
from app.model.markets import MARKETS, probabilities, settle
from app.data.identity import resolve
from app.analysis.value import assess_value, rank
from app.providers.football_data import utc_window


def fixture_dict(f):
    return {k:getattr(f,k) for k in ['id','competition','home','away','kickoff','fetched_at','status','source','hg','ag']}


def analyse_fixture(db,fixture_id):
    f=db.get(Fixture,fixture_id)
    if not f: return {'status':'withheld','reasons':['Fixture not found'],'markets':[]}
    reasons=[]
    if f.status!='SCHEDULED' or parse_time(f.kickoff)<=now(): reasons.append('Match has started or is not scheduled')
    if now()-parse_time(f.fetched_at)>timedelta(hours=12): reasons.append('Fixture data is stale')
    model=db.scalar(select(ModelVersion).where(ModelVersion.competition==f.competition,ModelVersion.active.is_(True)).order_by(ModelVersion.created_at.desc()))
    if not model: reasons.append('This competition has no validated model yet')
    elif now()-parse_time(model.created_at)>timedelta(days=14): reasons.append('Model needs a fresh validation run')
    if model and (now().date()-__import__('datetime').date.fromisoformat(model.parameters['cutoff'])).days>14:
        reasons.append('Recent results are missing; refresh history before analysis')
    if reasons: return {'status':'withheld','fixture':fixture_dict(f),'reasons':reasons,'markets':[]}
    home=resolve(f.home,model.parameters['teams']);away=resolve(f.away,model.parameters['teams'])
    if not home or not away: return {'status':'withheld','fixture':fixture_dict(f),'reasons':['Team identity or team history is unresolved'],'markets':[]}
    try: lh,la=rates(model.parameters,home,away,as_of=now().date().isoformat())
    except ValueError as exc: return {'status':'withheld','fixture':fixture_dict(f),'reasons':[str(exc)],'markets':[]}
    scale=model.parameters.get('scale',1.);raw=probabilities(score_grid(lh,la));cal=probabilities(score_grid(lh*scale,la*scale))
    rows=[];withheld=[]
    expires_at=min(now()+timedelta(minutes=5),parse_time(f.kickoff),parse_time(f.fetched_at)+timedelta(hours=12),parse_time(model.created_at)+timedelta(days=14)).isoformat()
    revision=db.scalar(select(Audit.id).where(Audit.kind=='fixture_revision',Audit.detail['id'].as_string()==f.id).order_by(Audit.id.desc()).limit(1)) or 0
    for key,p in cal.items():
        report=model.validation['markets'].get(key,{})
        band=report.get('bands',{}).get(str(min(int(p*10),9)),{})
        if not report.get('enabled') or band.get('n',0)<50:
            withheld.append(MARKETS[key][0]);continue
        quote=db.scalar(select(Odds).where(Odds.fixture_id==f.id,Odds.market==key).order_by(Odds.captured_at.desc()))
        usable=quote is not None and now()-parse_time(quote.captured_at)<=timedelta(hours=6)
        # Reference quotes may inform comparison but never establish local executable value.
        value=assess_value(p,quote.price if usable and quote.verified else None)
        if usable:
            value['reference']={'price':quote.price,'bookmaker':quote.bookmaker,'captured_at':quote.captured_at,'verified':quote.verified}
        evidence=[f'Expected goals: {lh*scale:.2f} home · {la*scale:.2f} away',
                  f"{model.parameters['counts'][home]} home-team and {model.parameters['counts'][away]} away-team matches in the training sample",
                  f"Historical test: {report['n']} matches; Brier score {report['brier']:.3f}",
                  f"This probability band: {band['n']} tests; observed {band['observed']:.0%} (95% interval {band['interval'][0]:.0%}–{band['interval'][1]:.0%})"]
        identity=json.dumps([f.id,key,model.id,f.kickoff,f.home,f.away,f.competition,revision])
        pid=hashlib.sha256(identity.encode()).hexdigest()
        prediction=db.get(Prediction,pid)
        if prediction and not prediction.valid:
            withheld.append(MARKETS[key][0]);continue
        if not prediction:
            values=dict(id=pid,fixture_id=f.id,market=key,model_id=model.id,probability=p,raw_probability=raw[key],created_at=stamp(),valid=True,
                snapshot={'fixture':fixture_dict(f),'home_rate':lh,'away_rate':la,'scale':scale,'model_id':model.id,'training_cutoff':model.parameters['cutoff'],'value':value,'evidence':evidence})
            if db.bind.dialect.name=='postgresql':
                from sqlalchemy.dialects.postgresql import insert
            else:
                from sqlalchemy.dialects.sqlite import insert
            db.execute(insert(Prediction).values(**values).on_conflict_do_nothing(index_elements=['id']))
            prediction=db.get(Prediction,pid)
        rows.append({'id':pid,'market':key,'label':MARKETS[key][0],'description':MARKETS[key][1],'probability':p,'raw_probability':raw[key],
                     'candidate':p>=.7,'value':value,'evidence':evidence,'model_id':model.id,'created_at':prediction.created_at,'fixture':fixture_dict(f),
                     'expires_at':expires_at,'band_n':band['n'],'band_interval':band['interval']})
    db.commit()
    return {'status':'ready' if rows else 'withheld','fixture':fixture_dict(f),'markets':rank(rows),'reasons':[] if rows else ['No market passes both validation and sample-size checks'],'withheld':withheld}


def analyse_day(db,day,timezone='Africa/Lagos'):
    start,end=utc_window(day,timezone)
    fixtures=list(db.scalars(select(Fixture).where(Fixture.kickoff>=start.isoformat(),Fixture.kickoff<end.isoformat()).order_by(Fixture.kickoff)))
    results=[analyse_fixture(db,f.id) for f in fixtures]
    candidates=rank([m for r in results for m in r['markets'] if m['candidate']])
    # Alternatives from the same match remain labelled, not multiplied as independent bets.
    return {'results':results,'candidates':candidates,'evaluated':len(fixtures),'qualifying':len({p['fixture']['id'] for p in candidates})}


def settle_predictions(db):
    count=0
    for p in db.scalars(select(Prediction)):
        f=db.get(Fixture,p.fixture_id)
        if not f or f.status!='FINISHED' or f.hg is None or f.ag is None: continue
        won=settle(p.market,f.hg,f.ag)
        if p.won!=won:
            db.add(Audit(kind='settlement',at=stamp(),detail={'prediction':p.id,'previous':p.won,'won':won,'score':[f.hg,f.ag]}))
            p.won=won;count+=1
    db.commit();return count
