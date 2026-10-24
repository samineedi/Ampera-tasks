import pytest
from werkzeug.security import generate_password_hash

import app as appmod
import auth


@pytest.fixture
def client(monkeypatch, items):
    monkeypatch.setenv("AUTH_DISABLED", "false")
    monkeypatch.setenv("APP_USERNAME", "pmo")
    monkeypatch.setenv("APP_PASSWORD_HASH", generate_password_hash("s3cret"))
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.setattr(appmod, "board", lambda refresh=False: {"items": items})
    auth._fails.clear()
    return appmod.app.test_client()


def login(c, username="pmo", password="s3cret"):
    return c.post("/api/login", json={"username": username, "password": password})


def test_api_requires_login(client):
    for path in ("/api/dashboard", "/api/projects", "/api/digest", "/api/meta", "/api/trello-health"):
        assert client.get(path).status_code == 401
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 401
    assert client.post("/api/plan/create", json={"plan": [{"title": "x"}]}).status_code == 401
    assert client.post("/api/closure/archive", json={"dry_run": False, "confirm": True}).status_code == 401


def test_public_routes_stay_open(client):
    assert client.get("/ping").status_code == 200
    assert client.get("/api/session").get_json()["authenticated"] is False
    assert client.get("/dashboard").status_code in (200, 503)      # React shell, no data


def test_login_then_access_then_logout(client):
    assert login(client).status_code == 200
    assert client.get("/api/session").get_json() == {"authenticated": True, "user": "pmo", "auth_enabled": True}
    assert client.get("/api/projects").status_code == 200
    client.post("/api/logout")
    assert client.get("/api/projects").status_code == 401


@pytest.mark.parametrize("u,p", [("pmo", "wrong"), ("other", "s3cret"), ("", "")])
def test_bad_credentials_401(client, u, p):
    assert login(client, u, p).status_code == 401
    assert client.get("/api/projects").status_code == 401


@pytest.mark.parametrize("body", [None, {}, {"username": "pmo"}, {"username": 1, "password": 2}])
def test_malformed_login_400(client, body):
    assert client.post("/api/login", json=body).status_code == 400


def test_lockout_after_repeated_failures(client):
    for _ in range(auth.MAX_FAILS):
        assert login(client, password="nope").status_code == 401
    assert login(client).status_code == 429                         # even the right password is refused while locked


def test_plain_password_setting(client, monkeypatch):
    monkeypatch.delenv("APP_PASSWORD_HASH")
    monkeypatch.setenv("APP_PASSWORD", "plain-pw")
    assert login(client, password="plain-pw").status_code == 200
    assert login(client, password="s3cret").status_code == 401


def test_session_cookie_flags(client):
    cookie = login(client).headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_disabled_flag_opens_api(client, monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "true")
    assert client.get("/api/projects").status_code == 200
    assert client.get("/api/session").get_json()["auth_enabled"] is False


def test_check_config_requires_settings(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "false")
    for k in ("APP_USERNAME", "SECRET_KEY", "APP_PASSWORD", "APP_PASSWORD_HASH"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(SystemExit):
        auth.check_config()
