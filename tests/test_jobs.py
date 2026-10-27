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
