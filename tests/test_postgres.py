import os
import uuid
import pytest
from sqlalchemy import delete
from app.db import connect
from app.models import Prediction
from app.domain import stamp


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'),reason='Set TEST_POSTGRES_URL for real PostgreSQL integration')
def test_postgres_prediction_survives_reconnection():
    url=os.environ['TEST_POSTGRES_URL'];key=uuid.uuid4().hex
    first=connect(url)
    with first() as db:
        db.add(Prediction(id=key,fixture_id='test-only-fixture',market='over15',model_id='test-only-model',probability=.8,raw_probability=.79,created_at=stamp(),snapshot={'source':'synthetic-test'},valid=True));db.commit()
    second=connect(url)
    try:
        with second() as db:
            p=db.get(Prediction,key)
            assert p.probability==.8 and p.snapshot=={'source':'synthetic-test'}
    finally:
        with second() as db:
            db.execute(delete(Prediction).where(Prediction.id==key));db.commit()
