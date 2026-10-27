from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.models import Fixture, Prediction, ModelVersion, Result
from app.data.ingest import ingest_fixtures
from app.analysis.service import analyse_fixture, analyse_day, settle_predictions
from test_access import make_client


def fixture():
    now=datetime.now(timezone.utc)
    return dict(id='fd:1',competition='PL',home='Arsenal FC',away='Chelsea FC',kickoff=(now+timedelta(hours=2)).isoformat(),fetched_at=now.isoformat(),status='SCHEDULED',source='football-data.org',hg=None,ag=None)


def test_insufficient_evidence_is_not_a_percentage(tmp_path):
    app,_=make_client(tmp_path)
    with app.state.db() as db:
        ingest_fixtures(db,[fixture()])
        result=analyse_fixture(db,'fd:1')
        assert result['status']=='withheld'
        assert result['markets']==[]
        assert db.scalar(select(Prediction)) is None


def test_upsert_and_changed_fixture_invalidate_predictions(tmp_path):
    app,_=make_client(tmp_path)
    with app.state.db() as db:
        f=fixture();ingest_fixtures(db,[f]);ingest_fixtures(db,[f])
        assert len(list(db.scalars(select(Fixture))))==1
        db.add(Prediction(id='p1',fixture_id=f['id'],market='over15',probability=.8,raw_probability=.8,model_id='m1',created_at=datetime.now(timezone.utc).isoformat(),snapshot={},valid=True))
        db.commit()
        f['status']='POSTPONED';ingest_fixtures(db,[f])
        assert db.get(Prediction,'p1').valid is False
        assert analyse_fixture(db,'fd:1')['status']=='withheld'


def test_stale_and_started_fixtures_withheld(tmp_path):
    app,_=make_client(tmp_path)
    with app.state.db() as db:
        f=fixture();f['fetched_at']=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
        ingest_fixtures(db,[f]);assert 'stale' in ' '.join(analyse_fixture(db,f['id'])['reasons']).lower()
        f=fixture();f['kickoff']=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
        ingest_fixtures(db,[f]);assert analyse_fixture(db,f['id'])['status']=='withheld'


def test_settlement_corrections_preserve_original_probability(tmp_path):
    app,_=make_client(tmp_path)
    with app.state.db() as db:
        f=fixture();ingest_fixtures(db,[f])
        db.add(Prediction(id='p1',fixture_id=f['id'],market='over15',probability=.8,raw_probability=.8,model_id='m1',created_at=datetime.now(timezone.utc).isoformat(),snapshot={},valid=True))
        db.commit()
        f.update(status='FINISHED',hg=1,ag=1);ingest_fixtures(db,[f]);settle_predictions(db)
        assert db.get(Prediction,'p1').won is True
        f.update(hg=0,ag=1);ingest_fixtures(db,[f]);settle_predictions(db)
        assert db.get(Prediction,'p1').won is False
        assert db.get(Prediction,'p1').probability == .8


def add_valid_model(db,cutoff=None):
    cutoff=cutoff or (datetime.now(timezone.utc).date()-timedelta(days=1)).isoformat()
    params={'teams':['Arsenal FC','Chelsea FC'],'coefficients':[.4,.2,0.,0.,0.,0.],'counts':{'Arsenal FC':40,'Chelsea FC':40},'cutoff':cutoff,'scale':1.,'n':80}
    bands={str(i):{'n':80,'observed':.8,'interval':[.7,.9]} for i in range(10)}
    validation={'markets':{'over15':{'enabled':True,'n':240,'brier':.15,'bands':bands}}}
    db.add(ModelVersion(id='valid-model',competition='PL',parameters=params,validation=validation,created_at=datetime.now(timezone.utc).isoformat(),active=True));db.commit()


def test_eligible_analysis_saved_once_and_returns_evidence(tmp_path):
    app,_=make_client(tmp_path)
    with app.state.db() as db:
        ingest_fixtures(db,[fixture()]);add_valid_model(db)
        first=analyse_fixture(db,'fd:1');again=analyse_fixture(db,'fd:1')
        assert first['status']=='ready' and first['markets'][0]['probability']>.7
        assert first['markets'][0]['value']['label']=='Value unavailable'
        assert first['markets'][0]['evidence']
        assert first['markets'][0]['created_at']==again['markets'][0]['created_at']
        assert len(list(db.scalars(select(Prediction))))==1


def test_old_training_results_cannot_create_current_candidate(tmp_path):
    app,_=make_client(tmp_path)
    with app.state.db() as db:
        ingest_fixtures(db,[fixture()]);add_valid_model(db,(datetime.now(timezone.utc).date()-timedelta(days=30)).isoformat())
        assert analyse_fixture(db,'fd:1')['status']=='withheld'
