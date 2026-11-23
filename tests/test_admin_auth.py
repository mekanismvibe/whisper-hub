from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

ADMIN_REQUESTS = [
    ("GET", "/api/admin/devices"),
    ("POST", "/api/admin/devices"),
    ("PATCH", "/api/admin/devices/1"),
    ("POST", "/api/admin/devices/1/revoke"),
    ("DELETE", "/api/admin/devices/1"),
    ("POST", "/api/admin/devices/1/pair"),
    ("GET", "/api/admin/transcriptions"),
    ("GET", "/api/admin/transcriptions/1"),
    ("DELETE", "/api/admin/transcriptions/1"),
    ("GET", "/api/admin/stats"),
    ("POST", "/api/admin/web-transcribe"),
    ("GET", "/api/admin/setup"),
]


@pytest.mark.parametrize(("method", "path"), ADMIN_REQUESTS)
def test_admin_endpoints_require_session(client: TestClient, method: str, path: str):
    response = client.request(method, path)
    assert response.status_code == 401, (method, path, response.text)
    assert response.json()["error"]["code"] == "unauthorized"


def test_session_endpoint_is_public(client: TestClient):
    response = client.get("/api/session")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_admin_cookie_is_httponly_and_samesite(admin: TestClient):
    cookie = admin.cookies.get("whub_session")
    assert cookie
    login = TestClient(admin.app, base_url="http://testserver").post(
        "/api/login", json={"password": "correct-horse-battery-staple"}
    )
    header = login.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header


def test_session_secret_is_private(tmp_path):
    from whisper_hub.app import create_app
    from whisper_hub.config import Config

    from .conftest import FakeEngine

    config = Config(
        data_dir=tmp_path / "data",
        admin_password="a-password",
        model="fake-model",
        preload=False,
    )
    with TestClient(create_app(config, engine=FakeEngine())):
        secret_file = config.data_dir / "session_secret"
        assert secret_file.exists()
        assert (secret_file.stat().st_mode & 0o777) == 0o600
        assert secret_file.read_text(encoding="utf-8").strip()
