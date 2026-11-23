"""Regression tests for issues found in the bug hunt."""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import auth, create_and_pair

FILE = ("clip.wav", b"pretend-this-is-audio", "audio/wav")


def test_revoke_invalidates_outstanding_pairing_code(admin: TestClient):
    created = admin.post("/api/admin/devices", json={"name": "Lost phone", "kind": "android"}).json()
    device_id, code = created["device"]["id"], created["pairing"]["code"]
    assert admin.post(f"/api/admin/devices/{device_id}/revoke").status_code == 200
    assert admin.post(f"/pair/{code}?format=json").status_code != 200


def test_device_deleted_mid_request_still_returns_text(admin: TestClient, fake):
    device, key, _ = create_and_pair(admin)
    original = fake.transcribe_bytes

    def delete_then_transcribe(*args, **kwargs):
        admin.app.state.db.delete_device(device["id"], delete_history=True)
        return original(*args, **kwargs)

    fake.transcribe_bytes = delete_then_transcribe
    response = admin.post(
        "/v1/audio/transcriptions", headers=auth(key), files={"file": FILE}, data={"response_format": "text"}
    )
    assert response.status_code == 200
    assert response.text == "Hello world."


def test_out_of_range_ids_are_400(admin: TestClient):
    huge = "9" * 25
    assert admin.get(f"/api/admin/transcriptions?device_id={huge}").status_code == 400
    assert admin.get(f"/api/admin/transcriptions/{huge}").status_code in (400, 404, 422)


def test_punctuation_only_search_matches_nothing(admin: TestClient):
    _, key, _ = create_and_pair(admin)
    admin.post("/v1/audio/transcriptions", headers=auth(key), files={"file": FILE})
    assert admin.get("/api/admin/transcriptions?q=!!!").json()["items"] == []
    assert len(admin.get("/api/admin/transcriptions").json()["items"]) == 1


def test_csv_export_neutralizes_formulas(admin: TestClient, fake):
    from .conftest import make_result

    _, key, _ = create_and_pair(admin)
    fake.push(make_result(text='=HYPERLINK("http://x","y")'))
    admin.post("/v1/audio/transcriptions", headers=auth(key), files={"file": FILE})
    body = admin.get("/api/admin/export?format=csv").text
    assert body.startswith("\ufeff")
    assert "'=HYPERLINK" in body


def test_delete_all_history_leaves_no_text_in_db_file(admin: TestClient, fake):
    from .conftest import make_result

    _, key, _ = create_and_pair(admin)
    fake.push(make_result(text="zebraquux supercalifragilistic"))
    admin.post("/v1/audio/transcriptions", headers=auth(key), files={"file": FILE})
    assert admin.delete("/api/admin/history?confirm=DELETE").status_code == 200
    db_path = admin.app.state.db.path
    assert b"zebraquux" not in db_path.read_bytes()


def test_settings_save_returns_the_full_payload(admin: TestClient):
    current = admin.get("/api/admin/settings").json()
    saved = admin.post("/api/admin/settings", json={"beam_size": 3}).json()
    assert saved["values"]["beam_size"] == 3
    for key in ("server", "parakeet_available", "model_status", "locked"):
        assert key in saved and key in current


def test_setup_finishes_when_model_is_pinned_by_env(tmp_path):
    from whisper_hub.app import create_app
    from whisper_hub.config import Config

    from .conftest import FakeEngine

    config = Config(
        data_dir=tmp_path / "data", admin_password=None, model="tiny", preload=False,
        env_names=frozenset({"WHUB_MODEL"}),
    )
    app = create_app(config, engine=FakeEngine(), engine_factory=lambda cfg: FakeEngine())
    with TestClient(app) as client:
        token = app.state.setup_token
        hw = client.get("/api/setup/hardware", params={"token": token}).json()
        assert hw["locked"] == {"model": "WHUB_MODEL"} and hw["values"]["model"] == "tiny"
        assert client.post(
            "/api/setup/password", json={"token": token, "password": "long-enough", "confirm": "long-enough"}
        ).status_code == 200
        done = client.post("/api/setup/finish", json={"token": token, "model": "medium", "english_engine": "whisper"})
        assert done.status_code == 200, done.text
        assert app.state.config.model == "tiny"


def test_cross_origin_admin_requests_are_refused(admin: TestClient):
    evil = {"Origin": "http://testserver:3000"}
    assert admin.post("/api/admin/devices", json={"name": "x", "kind": "other"}, headers=evil).status_code == 403
    same = {"Origin": "http://testserver"}
    assert admin.post("/api/admin/devices", json={"name": "x", "kind": "other"}, headers=same).status_code == 200
    # Device clients (no browser) are unaffected.
    assert admin.post("/v1/audio/transcriptions", headers={"Origin": "http://elsewhere"}).status_code != 403


def test_login_limiter_cannot_be_raced(client: TestClient):
    import concurrent.futures

    def guess(_):
        return client.post("/api/login", json={"password": "wrong-guess"}).status_code

    with concurrent.futures.ThreadPoolExecutor(12) as pool:
        codes = list(pool.map(guess, range(12)))
    assert codes.count(401) <= 5 and codes.count(429) >= 7


def test_password_change_signs_out_other_sessions(tmp_path):
    from whisper_hub.app import create_app
    from whisper_hub.config import Config

    from .conftest import FakeEngine

    config = Config(data_dir=tmp_path / "data", admin_password=None, model="tiny", preload=False)
    app = create_app(config, engine=FakeEngine(), engine_factory=lambda cfg: FakeEngine())
    with TestClient(app) as first, TestClient(app) as second:
        token = app.state.setup_token
        first.post("/api/setup/password", json={"token": token, "password": "old-password", "confirm": "old-password"})
        assert first.post("/api/setup/finish", json={"token": token, "model": "tiny"}).status_code == 200
        assert second.post("/api/login", json={"password": "old-password"}).status_code == 200
        changed = first.post(
            "/api/admin/password",
            json={"current_password": "old-password", "new_password": "new-password", "confirm": "new-password"},
        )
        assert changed.status_code == 200
        assert first.get("/api/admin/devices").status_code == 200, "the changing session stays signed in"
        assert second.get("/api/admin/devices").status_code == 401, "other sessions are signed out"


def test_json_endpoints_reject_large_bodies(client: TestClient):
    big = "x" * (2 * 1024 * 1024)
    assert client.post("/api/login", content=big, headers={"content-type": "application/json"}).status_code == 413


def test_non_ascii_setup_token_is_not_a_500(client: TestClient):
    assert client.get("/api/setup/status", params={"token": "é"}).status_code == 200
