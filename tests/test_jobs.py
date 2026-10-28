import pytest
from datetime import timedelta
from app.domain import now
from app.jobs import job_lock, train_all
from app.models import JobLock, ModelVersion
from test_access import make_client


def test_job_lock_blocks_overlap_and_releases(tmp_path):
    app,_=make_client(tmp_path)
    with job_lock(app.state.db,'test'):
        with pytest.raises(RuntimeError):
            with job_lock(app.state.db,'test'): pass
    with job_lock(app.state.db,'test'): pass


def test_failed_job_releases_lock(tmp_path):
    app,_=make_client(tmp_path)
    with pytest.raises(ValueError):
        with job_lock(app.state.db,'test'): raise ValueError('simulated failure')
    with job_lock(app.state.db,'test'): pass


def test_insufficient_history_does_not_activate(tmp_path):
    app,_=make_client(tmp_path)
    report=train_all(app.state.db)
    assert report['competitions']=={}


@pytest.mark.parametrize('command,report',[
    ('sync-results',{'updated':0,'errors':{'PL':'Provider unavailable'}}),
    ('sync-results',{'updated':10,'unresolved':1,'errors':{}}),
    ('train',{'competitions':{'PL':{'error':'Insufficient history'}}}),
    ('train',{'competitions':{}}),
    ('history',{'count':0,'missing':['PL/2026-27']}),
])
def test_failed_or_partial_job_exits_nonzero(tmp_path,monkeypatch,command,report):
    import app.jobs as jobs
    app,_=make_client(tmp_path)
    monkeypatch.setattr(jobs,'connect',lambda _:app.state.db)
    monkeypatch.setattr(jobs,'sync_results',lambda *a:report)
    monkeypatch.setattr(jobs,'train_all',lambda *a:report)
    monkeypatch.setattr(jobs,'import_history',lambda *a:([],report))
    monkeypatch.setattr('sys.argv',['jobs',command])
    with pytest.raises(SystemExit) as exc: jobs.main()
    assert exc.value.code==1
