"""Route tests. Audio generation is replaced, so these run offline."""

import base64
import re

import pytest

import app as app_module

PASSCODE = "测试 passcode"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module, "PASSCODE", "")
    return app_module.app.test_client()


@pytest.fixture
def locked_client(monkeypatch):
    monkeypatch.setattr(app_module, "PASSCODE", PASSCODE)
    return app_module.app.test_client()


@pytest.fixture
def fake_generate(monkeypatch):
    calls = []

    def fake(lines, voice_map, rate="+0%"):
        calls.append((lines, voice_map, rate))
        return b"\xff\xf3fake", [{"line": 0}]

    monkeypatch.setattr(app_module, "generate_audio", fake)
    return calls


def generate(client, **body):
    return client.post("/generate", json={"text": "A：你好", **body})


def test_page_script_carries_the_csp_nonce(client):
    resp = client.get("/")
    nonce = re.search(r"'nonce-([^']+)'", resp.headers["Content-Security-Policy"]).group(1)
    assert f'<script nonce="{nonce}">' in resp.text


def test_security_headers(client):
    headers = client.get("/").headers
    csp = headers["Content-Security-Policy"]
    assert "frame-ancestors 'self' https://huggingface.co" in csp
    assert "connect-src 'self' https://translate.googleapis.com" in csp
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_healthz(client):
    assert client.get("/healthz").json == {"status": "ok"}


def test_bad_request_bodies_do_not_crash(client):
    assert client.post("/parse", data="not json").json == {"speakers": [], "defaults": {}}
    assert client.post("/parse", json={"text": [1]}).status_code == 200


@pytest.mark.parametrize("body, error", [
    ({"voice_map": {"A": "evil"}}, "Unknown voice"),
    ({"voice_map": {"A": ["list"]}}, "Unknown voice"),
    ({"rate": "+80%"}, "Rate must be between"),
    ({"rate": "fast"}, "Rate must be between"),
    ({"text": ""}, "No dialogue lines found"),
])
def test_generate_rejects_invalid_input(client, fake_generate, body, error):
    resp = generate(client, **body)
    assert resp.status_code == 400
    assert resp.json["error"].startswith(error)
    assert fake_generate == []


def test_generate_returns_audio_inline(client, fake_generate):
    resp = generate(client, voice_map={"A": "zh-CN-YunxiNeural"}, rate="-10%")
    assert base64.b64decode(resp.json["audio"]) == b"\xff\xf3fake"
    assert resp.json["timing"] == [{"line": 0}]
    assert fake_generate == [([("A", "你好")], {"A": "zh-CN-YunxiNeural"}, "-10%")]


def test_speech_service_failure_is_a_json_502(client, monkeypatch):
    def broken(*args, **kwargs):
        raise ConnectionError("403 from Microsoft")

    monkeypatch.setattr(app_module, "generate_audio", broken)
    resp = generate(client)
    assert resp.status_code == 502
    assert "speech service failed" in resp.json["error"]


def test_pinyin_applies_tone_sandhi():
    html = app_module._annotate_pinyin("你好一个不是")
    for char, tone in [("你", "ní"), ("一", "yí"), ("不", "bú")]:
        assert f'{char}<rp>(</rp><rt class="sandhi">{tone}</rt>' in html


def test_pinyin_escapes_html(client):
    html = client.post("/pinyin", json={"text": "A：<img src=x onerror=alert(1)>你好"}).json["html"]
    assert "<img" not in html
    assert "&lt;img" in html


def test_unknown_routes_return_json(client):
    resp = client.get("/nope")
    assert resp.status_code == 404
    assert resp.is_json


def test_login_redirects_home_when_no_passcode_is_set(client):
    assert client.get("/login").status_code == 302


def test_passcode_gates_pages_and_api(locked_client):
    resp = locked_client.get("/")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/login"
    assert locked_client.post("/parse", json={"text": "A：你好"}).status_code == 401
    assert locked_client.get("/healthz").status_code == 200


def test_wrong_passcode_is_rejected(locked_client):
    assert locked_client.post("/login", data={"passcode": "nope"}).status_code == 401


def test_right_passcode_grants_access(locked_client):
    resp = locked_client.post("/login", data={"passcode": PASSCODE})
    assert resp.status_code == 302
    assert "HttpOnly" in resp.headers["Set-Cookie"]
    assert locked_client.get("/").status_code == 200
    assert locked_client.post("/parse", json={"text": "A：你好"}).status_code == 200


def test_cookie_works_in_the_hugging_face_iframe_over_https(locked_client):
    resp = locked_client.post(
        "/login", data={"passcode": PASSCODE}, headers={"X-Forwarded-Proto": "https"},
    )
    cookie = resp.headers["Set-Cookie"]
    assert "Secure" in cookie
    assert "SameSite=None" in cookie
