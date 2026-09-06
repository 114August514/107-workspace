"""Nginx contract tests. Require a local nginx binary; skipped otherwise."""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import textwrap
import threading
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("PUBLIC_ORIGIN", "http://127.0.0.1:8107")

from auth.auth_server import create_app  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _BackendHandler(BaseHTTPRequestHandler):
    def _echo(self) -> None:
        payload = {
            "method": self.command,
            "path": self.path,
            "x_user": self.headers.get("X-User"),
            "x_user_id": self.headers.get("X-User-ID"),
            "x_user_name": self.headers.get("X-User-Name"),
            "x_user_email": self.headers.get("X-User-Email"),
        }
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self._echo()

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self._echo()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _direct() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(CookieJar()),
        _NoRedirect(),
    )


def _open(opener: urllib.request.OpenerDirector, url: str, **kwargs):
    request = urllib.request.Request(url, **kwargs)
    try:
        return opener.open(request)
    except urllib.error.HTTPError as error:
        return error


def _status(response) -> int:
    return int(getattr(response, "status", None) or response.code)


@pytest.fixture(scope="module")
def nginx_bin():
    candidates = [
        os.environ.get("NGINX_BIN"),
        shutil.which("nginx"),
        str(Path.home() / "opt/nginx/usr/sbin/nginx"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    pytest.skip("nginx is not installed")


def test_nginx_public_home_and_api_contract(nginx_bin, monkeypatch, tmp_path):
    from werkzeug.serving import make_server

    auth_port = _free_port()
    backend_port = _free_port()
    nginx_port = _free_port()
    public_origin = f"http://127.0.0.1:{nginx_port}"
    monkeypatch.setenv("PUBLIC_ORIGIN", public_origin)
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    app = create_app()
    monkeypatch.setattr("auth.auth_server.check_ticket", lambda ticket, service: "ustcuser")

    backend = ThreadingHTTPServer(("127.0.0.1", backend_port), _BackendHandler)
    threading.Thread(target=backend.serve_forever, daemon=True).start()
    auth_server = make_server("127.0.0.1", auth_port, app)
    threading.Thread(target=auth_server.serve_forever, daemon=True).start()

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>public-home</body></html>", encoding="utf-8")
    (dist / "assets").mkdir()
    (dist / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")

    prefix = tmp_path / "nginx"
    (prefix / "logs").mkdir(parents=True)
    (prefix / "temp").mkdir()
    (prefix / "conf").mkdir()
    mime = Path("/etc/nginx/mime.types")
    mime_line = f"include {mime};" if mime.exists() else "types { text/html html; application/javascript js; }"
    conf_path = prefix / "conf" / "nginx.conf"
    conf_path.write_text(
        textwrap.dedent(
            f"""
            worker_processes 1;
            error_log logs/error.log warn;
            pid logs/nginx.pid;
            events {{ worker_connections 32; }}
            http {{
                {mime_line}
                default_type application/octet-stream;
                access_log logs/access.log;
                client_body_temp_path temp/client_body;
                proxy_temp_path temp/proxy;
                fastcgi_temp_path temp/fastcgi;
                uwsgi_temp_path temp/uwsgi;
                scgi_temp_path temp/scgi;
                server {{
                    listen 127.0.0.1:{nginx_port};
                    server_name 127.0.0.1;
                    root {dist};
                    index index.html;
                    absolute_redirect off;
                    location = /login {{
                        proxy_pass http://127.0.0.1:{auth_port};
                        proxy_set_header Host 127.0.0.1:{nginx_port};
                        proxy_set_header Cookie $http_cookie;
                    }}
                    location = /logout {{
                        limit_except POST {{ deny all; }}
                        proxy_pass http://127.0.0.1:{auth_port};
                        proxy_set_header Host 127.0.0.1:{nginx_port};
                        proxy_set_header Cookie $http_cookie;
                        proxy_set_header Origin $http_origin;
                        proxy_set_header Referer $http_referer;
                    }}
                    location = /auth {{
                        internal;
                        proxy_pass http://127.0.0.1:{auth_port};
                        proxy_pass_request_body off;
                        proxy_set_header Content-Length "";
                        proxy_set_header Cookie $http_cookie;
                        proxy_set_header X-Original-Method $request_method;
                        proxy_set_header Origin $http_origin;
                        proxy_set_header Referer $http_referer;
                        proxy_set_header Host 127.0.0.1:{nginx_port};
                    }}
                    location /api/ {{
                        auth_request /auth;
                        auth_request_set $user_id $upstream_http_x_user_id;
                        error_page 401 = @api_unauthorized;
                        error_page 403 = @api_forbidden;
                        proxy_pass http://127.0.0.1:{backend_port};
                        proxy_set_header X-User "";
                        proxy_set_header X-User-ID $user_id;
                        proxy_set_header X-User-Name "";
                        proxy_set_header X-User-Email "";
                        add_header Cache-Control "no-store" always;
                    }}
                    location @api_unauthorized {{
                        default_type application/json;
                        add_header Cache-Control "no-store" always;
                        return 401 '{{"code":"authentication_required","message":"需要登录。","problems":[],"request_id":""}}';
                    }}
                    location @api_forbidden {{
                        default_type application/json;
                        add_header Cache-Control "no-store" always;
                        return 403 '{{"code":"permission_denied","message":"请求来源不被允许。","problems":[],"request_id":""}}';
                    }}
                    location /assets/ {{
                        try_files $uri =404;
                    }}
                    location / {{
                        try_files $uri $uri/ /index.html;
                    }}
                }}
            }}
            """
        ),
        encoding="utf-8",
    )

    proc = subprocess.Popen(
        [nginx_bin, "-p", str(prefix), "-c", str(conf_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        for _ in range(50):
            with socket.socket() as sock:
                if sock.connect_ex(("127.0.0.1", nginx_port)) == 0:
                    break
            time.sleep(0.05)
        else:
            stderr = proc.stderr.read().decode() if proc.stderr else ""
            raise RuntimeError(f"nginx failed to listen: {stderr}")

        home = _direct().open(f"{public_origin}/")
        assert home.status == 200
        assert b"public-home" in home.read()
        assert _direct().open(f"{public_origin}/assets/app.js").status == 200

        with pytest.raises(urllib.error.HTTPError) as unauth:
            _direct().open(f"{public_origin}/api/v1/me")
        assert unauth.value.code == 401
        assert json.loads(unauth.value.read().decode())["code"] == "authentication_required"

        opener = _opener()
        login = _open(opener, f"{public_origin}/login")
        assert _status(login) in {302, 303}
        service = parse_qs(urlparse(login.headers["Location"]).query)["service"][0]
        session_id = parse_qs(urlparse(service).query)["id"][0]
        callback = _open(opener, f"{public_origin}/login?ticket=ST-ok&id={session_id}")
        assert _status(callback) in {302, 303}

        me = json.loads(opener.open(f"{public_origin}/api/v1/me").read().decode())
        assert me["x_user_id"] == "ustcuser"
        assert me["x_user"] in {None, ""}
        assert me["x_user_name"] in {None, ""}

        forged = urllib.request.Request(
            f"{public_origin}/api/v1/me",
            headers={"X-User-ID": "attacker", "X-User": "attacker"},
        )
        forged_body = json.loads(opener.open(forged).read().decode())
        assert forged_body["x_user_id"] == "ustcuser"
        assert forged_body["x_user"] in {None, ""}

        denied = _open(
            opener,
            f"{public_origin}/api/v1/projects",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        assert _status(denied) == 403

        allowed = json.loads(
            opener.open(
                urllib.request.Request(
                    f"{public_origin}/api/v1/projects",
                    data=b"{}",
                    method="POST",
                    headers={"Content-Type": "application/json", "Origin": public_origin},
                )
            ).read().decode()
        )
        assert allowed["x_user_id"] == "ustcuser"

        logout = _open(
            opener,
            f"{public_origin}/logout",
            method="POST",
            headers={"Origin": public_origin},
        )
        assert _status(logout) in {302, 303}

        after = _open(opener, f"{public_origin}/api/v1/me")
        assert _status(after) == 401
    finally:
        subprocess.run(
            [nginx_bin, "-p", str(prefix), "-c", str(conf_path), "-s", "stop"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.send_signal(signal.SIGTERM)
        auth_server.shutdown()
        backend.shutdown()
