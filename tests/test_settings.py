from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from whisper_hub.app import create_app
from whisper_hub.config import Config
from whisper_hub.settings import EnvLockedError, SettingsStore

from .conftest import ADMIN_PASSWORD, FakeEngine, auth, create_and_pair, make_result


def _store(tmp_path: Path, config: Config) -> SettingsStore:
    from whisper_hub.db import Database

    db = Database(tmp_path / "settings.db")
    db.initialize()
    return SettingsStore(config, db)


def test_precedence_default_then_db(tmp_path):
    store = _store(tmp_path, Config(model="small", data_dir=tmp_path))
    assert store.snapshot()["model"] == "small"
    store.update({"model": "base"})
    assert store.snapshot()["model"] == "base"
    assert store.effective_config().model == "base"


def test_env_locks_a_field(tmp_path):
    config = Config(
        model="small",
        data_dir=tmp_path,
        env_names=frozenset({"WHUB_MODEL", "WHUB_DATA_DIR"}),
    )
    store = _store(tmp_path, config)
    assert store.locked == {"model": "WHUB_MODEL"}
    assert store.payload()["locked"]["model"] == "WHUB_MODEL"
    store.update({"beam_size": 7})
    with pytest.raises(EnvLockedError):
        store.update({"model": "base"})
    # Re-sending the locked value is harmless.
    store.update({"model": "small"})
    assert store.snapshot()["beam_size"] == 7


def test_settings_api_shows_and_edits_values(admin: TestClient):
    body = admin.get("/api/admin/settings").json()
    assert body["values"]["model"] == "fake-model"
    assert body["values"]["beam_size"] == 5
    assert body["values"]["translate_beam_size"] == 5
    assert body["catalog"]
    assert isinstance(body["locked"], dict)
    assert body["server"]["version"]

    response = admin.post(
        "/api/admin/settings",
        json={
            "beam_size": 3,
            "translate_beam_size": 2,
            "max_concurrency": 2,
            "honor_client_language": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["values"]["beam_size"] == 3
    assert payload["values"]["translate_beam_size"] == 2
    assert payload["values"]["honor_client_language"] is True
    assert payload["reload_requested"] is False
    assert admin.app.state.config.beam_size == 3
    assert admin.app.state.config.translate_beam_size == 2


def test_settings_api_rejects_out_of_range_translate_beam_size(admin: TestClient):
    response = admin.post("/api/admin/settings", json={"translate_beam_size": 11})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_setting"


def test_settings_api_rejects_a_translation_capable_main_without_translator(client_factory):
    client, _, _ = client_factory(
        non_english=True, engine_factory=lambda config: FakeEngine()
    )
    client.post("/api/login", json={"password": ADMIN_PASSWORD})
    response = client.post(
        "/api/admin/settings", json={"model": "large-v3-turbo", "translate_model": ""}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_setting"
    response = client.post(
        "/api/admin/settings",
        json={"model": "large-v3-turbo", "translate_model": "distil-large-v3"},
    )
    assert response.status_code == 400
    ok = client.post(
        "/api/admin/settings",
        json={"model": "large-v3-turbo", "translate_model": "large-v3"},
    )
    assert ok.status_code == 200, ok.text
    assert client.app.state.manager.wait(5)


def test_settings_api_rejects_unknown_fields(client: TestClient):
    assert client.post("/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200
    response = client.post("/api/admin/settings", json={"host": "0.0.0.0"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_setting"


def test_change_password_and_sign_out_all(tmp_path):
    config = Config(
        data_dir=tmp_path / "data", admin_password=None, model="fake-model", preload=False
    )
    data_dir = config.data_dir
    data_dir.mkdir(parents=True)
    (data_dir / "admin_password").write_text("legacy-password\n", encoding="utf-8")
    app = create_app(config, engine=FakeEngine(), engine_factory=lambda cfg: FakeEngine())
    client = TestClient(app)
    client.__enter__()
    try:
        assert client.post("/api/login", json={"password": "legacy-password"}).status_code == 200
        response = client.post(
            "/api/admin/password",
            json={
                "current_password": "legacy-password",
                "new_password": "new-passphrase-9",
                "confirm": "new-passphrase-9",
            },
        )
        assert response.status_code == 200, response.text
        assert client.post("/api/login", json={"password": "new-passphrase-9"}).status_code == 200

        other = TestClient(client.app)
        assert other.post("/api/login", json={"password": "new-passphrase-9"}).status_code == 200
        old_cookie = other.cookies.get("whub_session")
        assert other.get("/api/session").json() == {"authenticated": True}

        rotated = client.post("/api/admin/logout-all")
        assert rotated.status_code == 200, rotated.text
        # The old cookie cannot be replayed: the signing key changed.
        replay = TestClient(client.app)
        replay.cookies.set("whub_session", old_cookie)
        assert replay.get("/api/session").json() == {"authenticated": False}
    finally:
        client.__exit__(None, None, None)


def test_export_and_delete_all_history(admin: TestClient):
    _, key, _ = create_and_pair(admin)
    engine: FakeEngine = admin.app.state.engine
    engine.push(make_result("Export me.", language="es", task="translate"))
    response = admin.post(
        "/v1/audio/transcriptions", headers=auth(key), files={"file": ("a.wav", b"x", "audio/wav")}
    )
    assert response.status_code == 200
    row_id = int(response.headers["X-Whub-Transcription-Id"])

    exported = admin.get("/api/admin/export?format=json")
    assert exported.status_code == 200
    assert "Export me." in exported.text
    assert "a.wav" not in exported.text
    assert "attachment" in exported.headers["content-disposition"]

    csv_export = admin.get("/api/admin/export?format=csv")
    assert csv_export.text.splitlines()[0] == "\ufeffcreated_at,device,detected_language,task,text"
    assert "Export me." in csv_export.text

    assert admin.get("/api/admin/export?format=xml").status_code == 400
    assert admin.delete("/api/admin/history").status_code == 400
    deleted = admin.delete("/api/admin/history?confirm=DELETE")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1
    assert admin.get(f"/api/admin/transcriptions/{row_id}").status_code == 404


def test_hot_swap_success_and_failure_paths(client_factory):
    created: list[FakeEngine] = []

    def factory(config: Config) -> FakeEngine:
        engine = FakeEngine()
        engine.loaded = True
        created.append(engine)
        return engine

    client, old, _ = client_factory(engine_factory=factory)
    assert client.post("/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200

    response = client.post("/api/admin/settings", json={"model": "base"})
    assert response.status_code == 200, response.text
    assert response.json()["reload_requested"] is True
    assert client.app.state.manager.wait(5)
    assert client.app.state.engine is created[-1]
    assert client.app.state.engine is not old
    assert old.unloaded, "the superseded engine must release its models"
    status = client.get("/api/admin/model-status").json()
    assert status["state"] == "ready"
    assert client.get("/healthz").json()["model"] == "base"

    def broken(config: Config) -> FakeEngine:
        raise RuntimeError("cannot load that model")

    client.app.state.engine_factory = broken
    current = client.app.state.engine
    response = client.post("/api/admin/settings", json={"model": "small"})
    assert response.status_code == 200, response.text
    assert client.app.state.manager.wait(5)
    assert client.app.state.engine is current, "a failed load must keep the old engine"
    assert not current.unloaded, "a failed load must not release the serving engine"
    status = client.get("/api/admin/model-status").json()
    assert status["state"] == "error"
    assert "cannot load that model" in status["message"]


def test_env_locked_setting_is_read_only_over_the_api(tmp_path):
    from whisper_hub.app import create_app
    from whisper_hub.config import Config

    config = Config.from_env(
        {
            "WHUB_ADMIN_PASSWORD": ADMIN_PASSWORD,
            "WHUB_DATA_DIR": str(tmp_path / "data"),
            "WHUB_MODEL": "small",
            "WHUB_PRELOAD": "false",
        }
    )
    app = create_app(config, engine=FakeEngine(), engine_factory=lambda cfg: FakeEngine())
    client = TestClient(app)
    client.__enter__()
    try:
        assert client.post("/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200
        body = client.get("/api/admin/settings").json()
        assert body["locked"]["model"] == "WHUB_MODEL"
        assert body["values"]["model"] == "small"
        response = client.post("/api/admin/settings", json={"model": "base"})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "env_locked"
        # A non-locked field still saves.
        assert client.post("/api/admin/settings", json={"beam_size": 2}).status_code == 200
    finally:
        client.__exit__(None, None, None)


def test_non_english_defaults_off_and_allows_an_untranslatable_main(client_factory):
    client, _, _ = client_factory(engine_factory=lambda config: FakeEngine())
    assert client.post("/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200
    body = client.get("/api/admin/settings").json()
    assert body["values"]["non_english"] is False
    assert body["defaults"]["non_english"] is False

    response = client.post(
        "/api/admin/settings", json={"model": "large-v3-turbo", "translate_model": ""}
    )
    assert response.status_code == 200, response.text
    assert response.json()["reload_requested"] is True
    assert client.app.state.manager.wait(5)
    assert client.app.state.config.model == "large-v3-turbo"


def test_toggling_non_english_triggers_a_reload(client_factory):
    def factory(config: Config) -> FakeEngine:
        engine = FakeEngine()
        engine.config = config
        return engine

    client, _, _ = client_factory(engine_factory=factory)
    assert client.post("/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200

    response = client.post("/api/admin/settings", json={"non_english": True})

    assert response.status_code == 200, response.text
    assert response.json()["reload_requested"] is True
    assert response.json()["values"]["non_english"] is True
    assert client.app.state.config.non_english is True
    assert client.app.state.manager.wait(5)
    assert client.app.state.engine.config.non_english is True


def test_env_locks_non_english(tmp_path):
    config = Config.from_env(
        {
            "WHUB_NON_ENGLISH": "true",
            "WHUB_ADMIN_PASSWORD": ADMIN_PASSWORD,
            "WHUB_DATA_DIR": str(tmp_path / "data"),
        }
    )
    store = _store(tmp_path, config)

    assert config.non_english is True
    assert store.locked["non_english"] == "WHUB_NON_ENGLISH"
    assert store.snapshot()["non_english"] is True
    with pytest.raises(EnvLockedError):
        store.update({"non_english": False})
    # Sending the pinned value back is harmless.
    store.update({"non_english": True})
