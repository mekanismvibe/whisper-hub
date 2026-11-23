from __future__ import annotations

import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from whisper_hub.app import create_app
from whisper_hub.auth import hash_device_key, hash_password, verify_password
from whisper_hub.config import Config
from whisper_hub.db import Database

from .conftest import ADMIN_PASSWORD, FakeEngine, auth
from .test_admin_auth import ADMIN_REQUESTS


def _setup_app(tmp_path: Path) -> tuple[TestClient, FakeEngine, Config, str]:
    config = Config(
        data_dir=tmp_path / "data",
        admin_password=None,
        model="fake-model",
        preload=False,
    )
    fake = FakeEngine()
    app = create_app(
        config, engine=fake, engine_factory=lambda cfg: FakeEngine()
    )
    client = TestClient(app)
    client.__enter__()
    token = app.state.setup_token
    assert token
    return client, fake, config, token


def test_setup_mode_locks_admin_apis_and_login(tmp_path):
    client, _, config, token = _setup_app(tmp_path)
    try:
        token_file = config.data_dir / "setup_token"
        assert token_file.read_text(encoding="utf-8").strip() == token
        assert stat.S_IMODE(token_file.stat().st_mode) == 0o600

        for method, path in [
            ("GET", "/api/admin/devices"),
            ("GET", "/api/admin/settings"),
            ("GET", "/api/admin/stats"),
        ]:
            response = client.request(method, path)
            assert response.status_code == 409
            assert response.json()["error"]["code"] == "setup_required"

        login = client.post("/api/login", json={"password": "anything at all"})
        assert login.status_code == 409
        assert login.json()["error"]["code"] == "setup_required"

        status = client.get("/api/setup/status", params={"token": token}).json()
        assert status == {"setup_required": True, "token_valid": True, "authenticated": False}
        assert client.get("/api/setup/status").json()["token_valid"] is False
    finally:
        client.__exit__(None, None, None)


def test_setup_rejects_wrong_token_and_short_password(tmp_path):
    client, _, config, token = _setup_app(tmp_path)
    try:
        wrong = client.post(
            "/api/setup/password",
            json={"token": "nope", "password": "long-enough", "confirm": "long-enough"},
        )
        assert wrong.status_code == 403
        assert wrong.json()["error"]["code"] == "invalid_setup_token"

        short = client.post(
            "/api/setup/password",
            json={"token": token, "password": "short", "confirm": "short"},
        )
        assert short.status_code == 400
        assert short.json()["error"]["code"] == "invalid_password"

        mismatch = client.post(
            "/api/setup/password",
            json={"token": token, "password": "long-enough", "confirm": "different"},
        )
        assert mismatch.status_code == 400

        hardware = client.get("/api/setup/hardware", params={"token": "wrong"})
        assert hardware.status_code == 403
        detected = client.get("/api/setup/hardware", params={"token": token})
        assert detected.status_code == 200
        assert detected.json()["hardware"]["cpu_cores"] >= 1
        assert detected.json()["catalog"]
        assert config.data_dir.joinpath("setup_token").exists()
    finally:
        client.__exit__(None, None, None)


def test_full_wizard_removes_the_token_and_logs_in(tmp_path):
    client, _, config, token = _setup_app(tmp_path)
    try:
        password = "setup-password-1"
        assert (
            client.post(
                "/api/setup/password",
                json={"token": token, "password": password, "confirm": password},
            ).status_code
            == 200
        )
        finish = client.post(
            "/api/setup/finish",
            json={
                "token": token,
                "model": "small",
                "translate_model": "",
                "english_engine": "whisper",
                "public_url": "http://hub.example.test:8765/",
                "https_url": "https://hub.example.test",
            },
        )
        assert finish.status_code == 200, finish.text
        assert finish.json()["authenticated"] is True
        assert not (config.data_dir / "setup_token").exists()
        assert client.app.state.setup_required is False
        assert client.get("/api/admin/devices").status_code == 200
        assert client.get("/api/admin/settings").json()["values"]["public_url"] == "http://hub.example.test:8765"

        assert client.post("/api/logout").status_code == 200
        assert client.post("/api/login", json={"password": password}).status_code == 200
        assert client.get("/api/setup/status").json() == {
            "setup_required": False,
            "token_valid": False,
            "authenticated": True,
        }
        # The old token cannot finish setup again.
        again = client.post("/api/setup/finish", json={"token": token, "model": "small"})
        assert again.status_code == 410
    finally:
        client.__exit__(None, None, None)


def test_setup_finish_validates_translation_models(tmp_path):
    client, _, _, token = _setup_app(tmp_path)
    try:
        client.post(
            "/api/setup/password",
            json={"token": token, "password": "setup-password-1", "confirm": "setup-password-1"},
        )
        response = client.post(
            "/api/setup/finish",
            json={
                "token": token,
                "model": "large-v3-turbo",
                "translate_model": "",
                "english_engine": "whisper",
                "non_english": True,
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_setting"
    finally:
        client.__exit__(None, None, None)


def test_legacy_password_file_is_migrated_and_devices_survive(tmp_path):
    data_dir = tmp_path / "data"
    database = Database(data_dir / "whisper.db")
    database.initialize()
    device = database.create_device("Existing phone", "iphone")
    database.set_device_key(device["id"], hash_device_key("whk_existing-key"), "whk_exis")
    database.insert_transcription(
        device_id=device["id"],
        text="Old history survives.",
        detected_language="es",
        language_probability=0.9,
        task="translate",
        audio_duration_s=2.0,
        processing_ms=10,
        model="small",
        endpoint="transcriptions",
        client_user_agent="pytest",
    )
    data_dir.mkdir(exist_ok=True)
    password_file = data_dir / "admin_password"
    password_file.write_text("legacy-password\n", encoding="utf-8")
    password_file.chmod(0o600)

    config = Config(data_dir=data_dir, admin_password=None, model="fake-model", preload=False)
    app = create_app(config, engine=FakeEngine(), engine_factory=lambda cfg: FakeEngine())
    with TestClient(app) as client:
        assert app.state.setup_required is False
        assert password_file.exists()
        assert database.get_setting("admin_password_hash")
        assert verify_password("legacy-password", database.get_setting("admin_password_hash") or "")
        assert client.post("/api/login", json={"password": "legacy-password"}).status_code == 200
        devices = client.get("/api/admin/devices").json()["devices"]
        assert any(item["name"] == "Existing phone" and item["status"] == "active" for item in devices)
        assert client.get("/api/device/me", headers=auth("whk_existing-key")).json()["name"] == "Existing phone"
        items = client.get("/api/admin/transcriptions").json()["items"]
        assert [item["text"] for item in items] == ["Old history survives."]
        # No setup token is issued for a migrated instance.
        assert not (data_dir / "setup_token").exists()


@pytest.mark.parametrize(("method", "path"), ADMIN_REQUESTS)
def test_every_admin_endpoint_returns_setup_required(tmp_path, method, path):
    client, _, _, _ = _setup_app(tmp_path)
    try:
        response = client.request(method, path)
        assert response.status_code == 409, (method, path, response.text)
        assert response.json()["error"]["code"] == "setup_required"
    finally:
        client.__exit__(None, None, None)


def test_finish_requires_a_password_first(tmp_path):
    client, _, _, token = _setup_app(tmp_path)
    try:
        response = client.post(
            "/api/setup/finish",
            json={"token": token, "model": "small", "translate_model": ""},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "password_required"
        assert client.post("/api/login", json={"password": ADMIN_PASSWORD}).status_code == 409
    finally:
        client.__exit__(None, None, None)


def test_setup_wizard_can_enable_non_english(tmp_path):
    client, _, _, token = _setup_app(tmp_path)
    try:
        client.post(
            "/api/setup/password",
            json={"token": token, "password": "setup-password-1", "confirm": "setup-password-1"},
        )
        response = client.post(
            "/api/setup/finish",
            json={
                "token": token,
                "model": "small",
                "translate_model": "",
                "english_engine": "whisper",
                "non_english": True,
            },
        )
        assert response.status_code == 200, response.text
        assert client.app.state.config.non_english is True
        assert client.get("/api/admin/settings").json()["values"]["non_english"] is True
    finally:
        client.__exit__(None, None, None)
