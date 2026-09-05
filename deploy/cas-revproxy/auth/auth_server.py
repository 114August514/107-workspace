"""USTC CAS session service for the 107 Workspace reverse proxy.

The browser only talks to Nginx. This process answers internal auth_request,
login callback, and logout. CAS protocol details stay here; the frontend never
handles tickets or session cookies.
"""

from __future__ import annotations

import hmac
import os
import uuid
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener, urlopen
from xml.etree import ElementTree

from flask import Flask, abort, current_app, make_response, redirect, request, session
from werkzeug.security import check_password_hash, generate_password_hash

CAS_NS = "{http://www.yale.edu/tp/cas}"
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or not str(value).strip():
        raise RuntimeError(f"{name} is required")
    return str(value).rstrip()


def login_service_url(session_id: str) -> str:
    return f"{current_app.config['PUBLIC_ORIGIN']}/login?{urlencode({'id': session_id})}"


def header_safe(value: str) -> bool:
    """HTTP/1.1 header values are latin-1. Skip names the wire cannot carry."""
    try:
        value.encode("latin-1")
    except UnicodeEncodeError:
        return False
    return True


def origin_allowed() -> bool:
    expected = current_app.config["PUBLIC_ORIGIN"]
    origin = (request.headers.get("Origin") or "").rstrip("/")
    if origin:
        return origin == expected
    referer = request.headers.get("Referer") or ""
    return referer == expected or referer.startswith(f"{expected}/")


def open_cas(url: str):
    timeout = 15
    proxy = current_app.config["HTTPS_PROXY"]
    if proxy:
        opener = build_opener(ProxyHandler({"http": proxy, "https": proxy}))
        return opener.open(url, timeout=timeout)
    return urlopen(url, timeout=timeout)


def check_ticket(ticket: str, service: str) -> str | None:
    validate = (
        f"{current_app.config['CAS_VALIDATE_URL']}?{urlencode({'service': service, 'ticket': ticket})}"
    )
    try:
        with open_cas(validate) as resp:
            body = resp.read()
    except (URLError, TimeoutError, OSError):
        return None
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        return None
    success = root.find(f"{CAS_NS}authenticationSuccess")
    if success is None and len(root):
        first = root[0]
        if first.tag == f"{CAS_NS}authenticationSuccess":
            success = first
    if success is None:
        return None
    user_el = success.find(f"{CAS_NS}user")
    if user_el is None or not (user_el.text or "").strip():
        return None
    return user_el.text.strip()


_DUMMY_PASSWORD_HASH = generate_password_hash("not-used")


def _local_password_hash() -> str:
    configured = os.environ.get("LOCAL_ADMIN_PASSWORD_HASH", "").strip()
    if configured:
        return configured
    raw = os.environ.get("LOCAL_ADMIN_PASSWORD", "")
    if raw:
        return generate_password_hash(raw)
    return ""


def _password_matches(app: Flask, username: str, password: str) -> bool:
    expected_user = app.config["LOCAL_ADMIN_USERNAME"]
    password_hash = app.config["LOCAL_ADMIN_PASSWORD_HASH"]
    if not expected_user or not password_hash:
        check_password_hash(_DUMMY_PASSWORD_HASH, password)
        return False
    selected = (
        password_hash if hmac.compare_digest(username, expected_user) else _DUMMY_PASSWORD_HASH
    )
    return check_password_hash(selected, password)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=_env("SECRET_KEY"),
        SESSION_COOKIE_NAME="workspace107_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
        SESSION_COOKIE_PATH="/",
        PUBLIC_ORIGIN=_env("PUBLIC_ORIGIN"),
        CAS_LOGIN_URL=_env("CAS_LOGIN_URL", "https://passport.ustc.edu.cn/login"),
        CAS_VALIDATE_URL=_env("CAS_VALIDATE_URL", "https://passport.ustc.edu.cn/serviceValidate"),
        HTTPS_PROXY=os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "",
        LOCAL_ADMIN_USERNAME=os.environ.get("LOCAL_ADMIN_USERNAME", "platform-admin").strip(),
        LOCAL_ADMIN_DISPLAY_NAME=os.environ.get("LOCAL_ADMIN_DISPLAY_NAME", "平台管理员").strip(),
        LOCAL_ADMIN_PASSWORD_HASH=_local_password_hash(),
    )

    @app.after_request
    def _no_store(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response

    @app.get("/auth")
    def auth():
        user = session.get("user")
        if not user:
            abort(401)
        method = (request.headers.get("X-Original-Method") or request.method).upper()
        if method in WRITE_METHODS and not origin_allowed():
            abort(403)
        response = make_response("", 200)
        response.headers["X-User-ID"] = user
        if session.get("provider") == "local":
            response.headers["X-User-Provider"] = "local"
            name = session.get("name")
            if name and header_safe(name):
                response.headers["X-User-Name"] = name
        return response

    @app.get("/login")
    def login():
        if session.get("user"):
            return redirect(f"{app.config['PUBLIC_ORIGIN']}/", code=303)
        if "id" not in session:
            session["id"] = uuid.uuid4().hex
        service = login_service_url(session["id"])
        ticket = request.args.get("ticket")
        if not ticket:
            return redirect(f"{app.config['CAS_LOGIN_URL']}?{urlencode({'service': service})}")
        if request.args.get("id") != session.get("id"):
            abort(401)
        user = check_ticket(ticket, service)
        if not user:
            abort(401)
        session["user"] = user
        session.pop("provider", None)
        session.pop("name", None)
        return redirect(f"{app.config['PUBLIC_ORIGIN']}/", code=303)

    @app.post("/login/password")
    def password_login():
        if not origin_allowed():
            abort(403)
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not _password_matches(app, username, password):
            return redirect(f"{app.config['PUBLIC_ORIGIN']}/?login_error=1", code=303)
        session.clear()
        session["user"] = app.config["LOCAL_ADMIN_USERNAME"]
        session["provider"] = "local"
        session["name"] = app.config["LOCAL_ADMIN_DISPLAY_NAME"]
        return redirect(f"{app.config['PUBLIC_ORIGIN']}/", code=303)

    @app.post("/logout")
    def logout():
        if not origin_allowed():
            abort(403)
        session.clear()
        response = redirect(f"{app.config['PUBLIC_ORIGIN']}/", code=303)
        response.delete_cookie(
            app.config["SESSION_COOKIE_NAME"],
            path=app.config["SESSION_COOKIE_PATH"],
        )
        return response

    return app
