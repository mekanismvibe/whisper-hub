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


def test_per_request_settings_reach_the_running_engine(client_factory):
    from whisper_hub.config import Config as _Config

    client, fake, _ = client_factory()
    fake.config = _Config(model="fake-model", preload=False)
    from .conftest import ADMIN_PASSWORD

    client.post("/api/login", json={"password": ADMIN_PASSWORD})
    saved = client.post("/api/admin/settings", json={"beam_size": 2, "lang_confidence": 0.8, "honor_client_language": True})
    assert saved.status_code == 200 and saved.json()["reload_requested"] is False
    assert (fake.config.beam_size, fake.config.lang_confidence, fake.config.honor_client_language) == (2, 0.8, True)


def test_blank_env_vars_do_not_lock_settings():
    from whisper_hub.config import Config as _Config

    config = _Config.from_env({"WHUB_MODEL": "", "WHUB_PUBLIC_URL": " ", "WHUB_BEAM_SIZE": "3"})
    assert config.env_names == frozenset({"WHUB_BEAM_SIZE"})


def test_dotenv_quoted_value_with_inline_comment(tmp_path):
    from whisper_hub.config import load_dotenv

    path = tmp_path / ".env"
    path.write_text('WHUB_MODEL="small" # main model\nWHUB_X=plain # note\n', encoding="utf-8")
    assert load_dotenv(path) == {"WHUB_MODEL": "small", "WHUB_X": "plain"}


def test_cpu_float16_and_bogus_compute_types_are_rejected(admin: TestClient):
    assert admin.post("/api/admin/settings", json={"device": "cpu", "compute_type": "float16"}).status_code == 400
    assert admin.post("/api/admin/settings", json={"compute_type": "bogus"}).status_code == 400
    assert admin.post("/api/admin/settings", json={"public_url": "http://["}).status_code == 400


def test_unchanged_model_fields_do_not_block_saves_during_a_swap(admin: TestClient):
    manager = admin.app.state.manager
    current = admin.get("/api/admin/settings").json()["values"]
    import threading

    gate = threading.Event()
    manager.request_swap(lambda: gate.wait(5) or (_ for _ in ()).throw(RuntimeError("stop")), model="x")
    try:
        response = admin.post("/api/admin/settings", json={"model": current["model"], "beam_size": 4})
        assert response.status_code == 200, response.text
        assert admin.post("/api/admin/settings", json={"model": "tiny"}).status_code == 409
    finally:
        gate.set()
        manager.wait(5)


def test_status_reflects_lazy_loads(client_factory):
    client, fake, _ = client_factory()
    fake.models_loaded = False
    manager = client.app.state.manager
    manager.set_error("Model preload failed.")
    fake.models_loaded = True  # a later request loaded the models lazily
    assert manager.status()["state"] == "ready"


def test_queue_of_waiting_uploads_is_bounded(admin: TestClient):
    _, key, _ = create_and_pair(admin)
    limiter = admin.app.state.limiter
    limiter.admitted = max(4, 4 * limiter.limit)  # pretend the queue is full
    try:
        response = admin.post("/v1/audio/transcriptions", headers=auth(key), files={"file": FILE})
        assert response.status_code == 503 and response.headers["retry-after"]
    finally:
        limiter.admitted = 0


def test_max_concurrency_resize_keeps_one_limiter(admin: TestClient):
    limiter = admin.app.state.limiter
    assert admin.post("/api/admin/settings", json={"max_concurrency": 3}).status_code == 200
    assert admin.app.state.limiter is limiter and limiter.limit == 3


def test_null_origin_is_refused(admin: TestClient):
    response = admin.post("/api/admin/devices", json={"name": "x", "kind": "other"}, headers={"Origin": "null"})
    assert response.status_code == 403


def test_history_write_failure_still_returns_text(admin: TestClient):
    import sqlite3

    _, key, _ = create_and_pair(admin)
    db = admin.app.state.db

    def broken(**kwargs):
        raise sqlite3.OperationalError("database or disk is full")

    original, db.insert_transcription = db.insert_transcription, broken
    try:
        response = admin.post(
            "/v1/audio/transcriptions", headers=auth(key), files={"file": FILE}, data={"response_format": "text"}
        )
    finally:
        db.insert_transcription = original
    assert response.status_code == 200 and response.text == "Hello world."


def test_streamed_export_matches_one_shot_export_across_pages(admin: TestClient, fake):
    import csv
    import functools
    import io
    import json

    from .conftest import make_result

    _, key, _ = create_and_pair(admin)
    for index in range(5):
        fake.push(make_result(text=f"Entry number {index} — ünïcode"))
        admin.post("/v1/audio/transcriptions", headers=auth(key), files={"file": FILE})
    db = admin.app.state.db
    db.iter_transcriptions = functools.partial(type(db).iter_transcriptions, db, page_size=2)
    expected = [
        {"created_at": i["created_at"], "device": i["device_name"] or "Deleted device",
         "detected_language": i["detected_language"], "task": i["task"], "text": i["text"]}
        for i in db.all_transcriptions()
    ]
    body = admin.get("/api/admin/export?format=json").text
    assert body == json.dumps(expected, ensure_ascii=False, indent=2)
    rows = list(csv.DictReader(io.StringIO(admin.get("/api/admin/export?format=csv").text.lstrip("﻿"))))
    assert [r["text"] for r in rows] == [r["text"] for r in expected]
    admin.delete("/api/admin/history?confirm=DELETE")
    assert admin.get("/api/admin/export?format=json").text == "[]"
