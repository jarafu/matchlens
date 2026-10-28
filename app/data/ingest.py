from sqlalchemy import select
from app.domain import stamp
from app.models import Fixture, Result, Prediction, Audit


def ingest_fixtures(db,rows):
    for row in rows:
        existing=db.get(Fixture,row['id'])
        if existing:
            identity_changed=any(getattr(existing,k)!=row[k] for k in ['kickoff','competition','home','away'])
            changed=identity_changed or existing.status!=row['status']
            score_changed=existing.hg!=row.get('hg') or existing.ag!=row.get('ag')
            if identity_changed or row['status'] in {'POSTPONED','CANCELLED','SUSPENDED'}:
                for p in db.scalars(select(Prediction).where(Prediction.fixture_id==existing.id)): p.valid=False
            if changed or score_changed:
                db.add(Audit(kind='fixture_revision',at=stamp(),detail={'id':existing.id,'old':{'kickoff':existing.kickoff,'status':existing.status,'hg':existing.hg,'ag':existing.ag},'new':row}))
            for k,v in row.items(): setattr(existing,k,v)
        else: db.add(Fixture(**row))
    db.add(Audit(kind='fixtures_ingested',at=stamp(),detail={'count':len(rows)}));db.commit()


def ingest_history(db,rows):
    count=0
    for row in rows:
        current=db.get(Result,row['id'])
        if current:
            if current.hg!=row['hg'] or current.ag!=row['ag']:
                db.add(Audit(kind='result_revision',at=stamp(),detail={'id':current.id,'old':[current.hg,current.ag],'new':[row['hg'],row['ag']],'revision':row['revision']}))
            for k,v in row.items(): setattr(current,k,v)
        else: db.add(Result(**row));count+=1
    db.add(Audit(kind='history_ingested',at=stamp(),detail={'count':count}));db.commit();return count
