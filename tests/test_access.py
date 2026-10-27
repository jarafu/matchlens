import re
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.config import Settings
from app.main import create_app
from app.models import LoginSession, Fixture
from app.web.auth import hash_password


def make_client(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path}/app.db", password_hash=hash_password("a-test-password-long"))
    app = create_app(settings)
    return app, TestClient(app)


def login(client):
    page = client.get("/login")
    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    return client.post("/login", data={"password": "a-test-password-long", "csrf": csrf})


def test_protected_routes_reject_anonymous(tmp_path):
    _, client = make_client(tmp_path)
    assert client.get("/api/fixtures").status_code == 401
    assert client.post("/api/analyse-day").status_code == 401
    assert client.get("/", follow_redirects=False).status_code == 303


def test_session_expires_and_csrf_rejected(tmp_path):
    app, client = make_client(tmp_path)
    assert login(client).status_code == 200
    assert client.get("/api/fixtures").status_code == 200
    assert client.post("/api/analyse-day").status_code == 403
    with app.state.db() as db:
        sess = db.scalar(select(LoginSession))
        sess.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        db.commit()
    assert client.get("/api/fixtures").status_code == 401


def test_bad_login_csrf_and_throttle(tmp_path):
    _, client = make_client(tmp_path)
    assert client.post("/login", data={"password":"a-test-password-long", "csrf":"wrong"}).status_code == 403
    for _ in range(6):
        html = client.get("/login").text
        token = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
        response = client.post("/login", data={"password":"wrong", "csrf":token})
    assert response.status_code == 429


def test_storage_survives_restart_and_secrets_hidden(tmp_path):
    app, client = make_client(tmp_path)
    with app.state.db() as db:
        db.add(Fixture(id="f1", competition="PL", home="Arsenal", away="Chelsea", kickoff="2030-01-01T12:00:00+00:00", fetched_at="2030-01-01T08:00:00+00:00", status="SCHEDULED", source="test"))
        db.commit()
    app2 = create_app(app.state.settings)
    with app2.state.db() as db:
        assert db.get(Fixture,"f1").home == "Arsenal"
    login(client)
    assert app.state.settings.password_hash not in client.get("/").text
    assert "database_url" not in client.get("/healthz").text


def test_hosted_sqlite_rejected(tmp_path):
    import pytest
    with pytest.raises(ValueError, match="PostgreSQL"):
        create_app(Settings(database_url=f"sqlite:///{tmp_path}/a.db", secure_cookies=True, password_hash=hash_password("abc")))


def test_local_setup_and_token_storage(tmp_path):
    settings=Settings(database_url=f"sqlite:///{tmp_path}/setup.db",password_hash='',secrets_file=tmp_path/'.env')
    app=create_app(settings)
    client=TestClient(app,client=('127.0.0.1',50000))
    html=client.get('/login').text
    csrf=re.search(r'name="csrf" value="([^"]+)"',html).group(1)
    response=client.post('/setup',data={'password':'a-test-password-long','confirm':'a-test-password-long','csrf':csrf,'football_token':'fixture-secret-key'})
    assert response.status_code==200
    assert 'fixture-secret-key' not in response.text
    assert app.state.settings.football_token=='fixture-secret-key'
    assert settings.secrets_file.stat().st_mode & 0o077 == 0
    assert client.post('/setup',data={'password':'a-test-password-long','confirm':'a-test-password-long','csrf':csrf}).status_code==403


def test_remote_setup_rejected(tmp_path):
    app=create_app(Settings(database_url=f"sqlite:///{tmp_path}/remote.db",password_hash='',secrets_file=tmp_path/'.env'))
    client=TestClient(app,client=('203.0.113.9',12345))
    html=client.get('/login').text;csrf=re.search(r'name="csrf" value="([^"]+)"',html).group(1)
    assert client.post('/setup',data={'password':'a-test-password-long','confirm':'a-test-password-long','csrf':csrf}).status_code==403
