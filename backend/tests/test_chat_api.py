import pytest

import app as appmod
from agent.chat_agent import ChatUnavailable


@pytest.fixture
def client(monkeypatch, items):
    monkeypatch.setattr(appmod, "board", lambda refresh=False: {"items": items})
    calls = []

    def fake_ask(its, message, history, project=""):
        calls.append((message, history, project))
        return {"answer": "hi", "tools_used": ["get_kpis"]}

    monkeypatch.setattr(appmod, "ask", fake_ask)
    c = appmod.app.test_client()
    c.calls = calls
    return c


def post(c, **body):
    return c.post("/api/chat", json=body)


def test_chat_ok_returns_answer(client):
    r = post(client, message="hello")
    assert r.status_code == 200 and r.get_json() == {"answer": "hi", "tools_used": ["get_kpis"]}


@pytest.mark.parametrize("msg", ["", "   ", "x" * 1001, None, 5])
def test_chat_bad_message_400(client, msg):
    assert post(client, message=msg).status_code == 400


@pytest.mark.parametrize("hist", ["nope", [1], [{"role": "system", "content": "x"}],
                                  [{"role": "user", "content": 5}], [{"content": "x"}]])
def test_chat_bad_history_400(client, hist):
    assert post(client, message="hi", history=hist).status_code == 400


def test_chat_no_api_key_503(client, monkeypatch):
    def boom(*a, **k):
        raise ChatUnavailable("Chat needs GOOGLE_API_KEY")
    monkeypatch.setattr(appmod, "ask", boom)
    r = post(client, message="hi")
    assert r.status_code == 503 and r.get_json()["error"] == "Chat needs GOOGLE_API_KEY"


def test_chat_agent_error_502_no_traceback(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret")
    monkeypatch.setattr(appmod, "ask", boom)
    r = post(client, message="hi")
    assert r.status_code == 502 and "secret" not in r.get_data(as_text=True)


def test_chat_passes_project_to_ask(client):
    post(client, message="hi", project="Project A", history=[{"role": "user", "content": "a"}])
    assert client.calls == [("hi", [{"role": "user", "content": "a"}], "Project A")]


def test_chat_non_json_body_400(client):
    assert client.post("/api/chat", data="x", content_type="text/plain").status_code == 400
