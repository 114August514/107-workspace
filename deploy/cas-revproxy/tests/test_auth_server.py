from __future__ import annotations

import os
from urllib.parse import parse_qs, urlparse

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("PUBLIC_ORIGIN", "http://127.0.0.1:8107")
os.environ.setdefault("SESSION_COOKIE_SECURE", "0")
os.environ.setdefault("HTTPS_PROXY", "http://127.0.0.1:27997")

from auth.auth_server import create_app  # noqa: E402


@pytest.fixture
def app(monkeypatch):
    application = create_app()
    application.config["TESTING"] = True
    monkeypatch.setattr("auth.auth_server.check_ticket", lambda ticket, service: "ustcuser")
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def test_auth_unauthenticated_is_401(client):
    response = client.get("/auth")
    assert response.status_code == 401
    assert response.headers.get("Cache-Control") == "no-store"


def test_login_redirects_to_fixed_cas_service(client):
    response = client.get("/login")
    assert response.status_code == 302
    location = urlparse(response.headers["Location"])
    assert location.netloc == "passport.ustc.edu.cn"
    service = parse_qs(location.query)["service"][0]
    parsed = urlparse(service)
    assert parsed.scheme == "http"
    assert parsed.netloc == "127.0.0.1:8107"
    assert parsed.path == "/login"
    assert "id" in parse_qs(parsed.query)


def test_login_id_mismatch_does_not_create_session(client):
    start = client.get("/login")
    service = parse_qs(urlparse(start.headers["Location"]).query)["service"][0]
    session_id = parse_qs(urlparse(service).query)["id"][0]
    response = client.get(f"/login?ticket=ST-1&id=not-{session_id}")
    assert response.status_code == 401
    assert client.get("/auth").status_code == 401


def test_login_ticket_failure_does_not_create_session(client, monkeypatch):
    monkeypatch.setattr("auth.auth_server.check_ticket", lambda ticket, service: None)
    start = client.get("/login")
    service = parse_qs(urlparse(start.headers["Location"]).query)["service"][0]
    session_id = parse_qs(urlparse(service).query)["id"][0]
    response = client.get(f"/login?ticket=ST-bad&id={session_id}")
    assert response.status_code == 401
    assert client.get("/auth").status_code == 401


def test_login_success_sets_session_and_redirects_home(client):
    start = client.get("/login")
    service = parse_qs(urlparse(start.headers["Location"]).query)["service"][0]
    session_id = parse_qs(urlparse(service).query)["id"][0]
    response = client.get(f"/login?ticket=ST-ok&id={session_id}")
    assert response.status_code == 303
    assert response.headers["Location"] == "http://127.0.0.1:8107/"
    auth = client.get("/auth")
    assert auth.status_code == 200
    assert auth.headers["X-User-ID"] == "ustcuser"
    assert "X-User-Name" not in auth.headers
    assert "X-User-Email" not in auth.headers


def test_auth_write_without_origin_is_403(client):
    start = client.get("/login")
    service = parse_qs(urlparse(start.headers["Location"]).query)["service"][0]
    session_id = parse_qs(urlparse(service).query)["id"][0]
    client.get(f"/login?ticket=ST-ok&id={session_id}")
    response = client.get("/auth", headers={"X-Original-Method": "POST"})
    assert response.status_code == 403


def test_auth_write_with_origin_is_ok(client):
    start = client.get("/login")
    service = parse_qs(urlparse(start.headers["Location"]).query)["service"][0]
    session_id = parse_qs(urlparse(service).query)["id"][0]
    client.get(f"/login?ticket=ST-ok&id={session_id}")
    response = client.get(
        "/auth",
        headers={"X-Original-Method": "POST", "Origin": "http://127.0.0.1:8107"},
    )
    assert response.status_code == 200
    assert response.headers["X-User-ID"] == "ustcuser"


def test_logout_requires_origin_and_clears_session(client):
    start = client.get("/login")
    service = parse_qs(urlparse(start.headers["Location"]).query)["service"][0]
    session_id = parse_qs(urlparse(service).query)["id"][0]
    client.get(f"/login?ticket=ST-ok&id={session_id}")
    denied = client.post("/logout")
    assert denied.status_code == 403
    assert client.get("/auth").status_code == 200

    response = client.post("/logout", headers={"Origin": "http://127.0.0.1:8107"})
    assert response.status_code == 303
    assert response.headers["Location"] == "http://127.0.0.1:8107/"
    assert client.get("/auth").status_code == 401


def test_logout_does_not_redirect_to_cas(client):
    start = client.get("/login")
    service = parse_qs(urlparse(start.headers["Location"]).query)["service"][0]
    session_id = parse_qs(urlparse(service).query)["id"][0]
    client.get(f"/login?ticket=ST-ok&id={session_id}")
    response = client.post("/logout", headers={"Origin": "http://127.0.0.1:8107"})
    assert "passport.ustc.edu.cn" not in response.headers["Location"]


def test_session_cookie_flags(client):
    response = client.get("/login")
    set_cookie = ";".join(response.headers.getlist("Set-Cookie"))
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie
    assert "Secure" not in set_cookie


def test_password_login_requires_origin_and_sets_local_provider(monkeypatch):
    monkeypatch.setenv("LOCAL_ADMIN_PASSWORD", "s3cret")
    application = create_app()
    client = application.test_client()
    denied = client.post(
        "/login/password",
        data={"username": "platform-admin", "password": "s3cret"},
    )
    assert denied.status_code == 403

    response = client.post(
        "/login/password",
        data={"username": "platform-admin", "password": "s3cret"},
        headers={"Origin": "http://127.0.0.1:8107"},
    )
    assert response.status_code == 303
    assert response.headers["Location"] == "http://127.0.0.1:8107/"
    auth = client.get("/auth")
    assert auth.status_code == 200
    assert auth.headers["X-User-ID"] == "platform-admin"
    assert auth.headers["X-User-Provider"] == "local"
    assert "X-User-Name" not in auth.headers


def test_password_login_ascii_display_name_is_forwarded(monkeypatch):
    monkeypatch.setenv("LOCAL_ADMIN_PASSWORD", "s3cret")
    monkeypatch.setenv("LOCAL_ADMIN_DISPLAY_NAME", "Platform Admin")
    application = create_app()
    client = application.test_client()
    response = client.post(
        "/login/password",
        data={"username": "platform-admin", "password": "s3cret"},
        headers={"Origin": "http://127.0.0.1:8107"},
    )
    assert response.status_code == 303
    auth = client.get("/auth")
    assert auth.status_code == 200
    assert auth.headers["X-User-Name"] == "Platform Admin"


def test_password_login_failure_does_not_create_session(monkeypatch):
    monkeypatch.setenv("LOCAL_ADMIN_PASSWORD", "s3cret")
    application = create_app()
    client = application.test_client()
    response = client.post(
        "/login/password",
        data={"username": "platform-admin", "password": "wrong"},
        headers={"Origin": "http://127.0.0.1:8107"},
    )
    assert response.status_code == 303
    assert "login_error=1" in response.headers["Location"]
    assert client.get("/auth").status_code == 401
