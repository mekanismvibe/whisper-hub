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
