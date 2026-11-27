import stat
from pathlib import Path

from fastapi.testclient import TestClient

from ppos.infrastructure.config import Settings
from ppos.shared.clock import FixedClock
from ppos_api.main import create_app
from ppos_api.security import COOKIE, token_path


def _app(tmp_path: Path, clock: FixedClock, **kw: object):  # type: ignore[no-untyped-def]
    dist = tmp_path / "web"
    (dist / "assets").mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text("<!doctype html><title>t</title>", encoding="utf-8")
    settings = Settings(local_data_dir=tmp_path / "data", web_dist_dir=dist, **kw)  # type: ignore[arg-type]
    return create_app(settings, clock), settings


def test_token_cookie_host_and_origin(tmp_path: Path, clock: FixedClock) -> None:
    app, settings = _app(tmp_path, clock)
    token = app.state.api_token
    path = token_path(settings)
    assert path.read_text().strip() == token and len(token) >= 32
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    c = TestClient(app, base_url="http://127.0.0.1:8765")
    assert c.get("/api/tasks").status_code == 401  # no token
    assert c.get("/api/tasks", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/api/health").status_code == 401  # even health reveals paths: guarded

    page = c.get("/")  # the app's own page hands out the cookie
    assert page.status_code == 200
    set_cookie = page.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=strict" in set_cookie
    assert c.cookies.get(COOKIE) == token
    assert c.get("/api/tasks").status_code == 200  # cookie now works

    # DNS rebinding: a page on evil.example resolving to 127.0.0.1 sends Host: evil.example
    evil = TestClient(app, base_url="http://evil.example:8765")
    assert evil.get("/").status_code == 421
    assert evil.get("/api/tasks", headers={"Authorization": f"Bearer {token}"}).status_code == 421

    # CSRF: state change from a foreign origin is refused even with a valid cookie
    r = c.post("/api/tasks", json={"title": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert (
        c.post(
            "/api/tasks", json={"title": "ok"}, headers={"Origin": "http://127.0.0.1:8765"}
        ).status_code
        == 201
    )
    assert (
        c.post(
            "/api/tasks", json={"title": "dev"}, headers={"Origin": "http://localhost:5173"}
        ).status_code
        == 201
    )

    bearer = TestClient(
        app, base_url="http://localhost:8765", headers={"Authorization": f"Bearer {token}"}
    )
    assert bearer.get("/api/tasks").status_code == 200  # scripts / CLI


def test_token_is_stable_and_overridable(tmp_path: Path, clock: FixedClock) -> None:
    app1, _ = _app(tmp_path, clock)
    app2, _ = _app(tmp_path, clock)
    assert app1.state.api_token == app2.state.api_token  # survives restarts
    app3, _ = _app(tmp_path, clock, api_token="fixed-token-for-automation-000000000")
    assert app3.state.api_token == "fixed-token-for-automation-000000000"


def test_allowed_hosts_and_off_switch(tmp_path: Path, clock: FixedClock) -> None:
    app, _ = _app(tmp_path, clock, allowed_hosts=["mybox.lan"])
    c = TestClient(
        app,
        base_url="http://mybox.lan:8765",
        headers={"Authorization": f"Bearer {app.state.api_token}"},
    )
    assert c.get("/api/tasks").status_code == 200
    off, _ = _app(tmp_path, clock, auth=False)
    assert TestClient(off, base_url="http://anything:1").get("/api/tasks").status_code == 200
