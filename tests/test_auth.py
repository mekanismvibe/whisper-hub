from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import ADMIN_PASSWORD, auth, create_and_pair


def _upload(client: TestClient, key: str | None, *, endpoint: str = "transcriptions"):
    headers = auth(key) if key else {}
    return client.post(
        f"/v1/audio/{endpoint}",
        headers=headers,
        files={"file": ("clip.wav", b"not really audio", "audio/wav")},
    )


def test_missing_key_is_rejected(client: TestClient):
    response = _upload(client, None)
    assert response.status_code == 401
    error = response.json()["error"]
    assert error["type"] == "authentication_error"
    assert error["code"] == "invalid_api_key"


def test_invalid_key_is_rejected(client: TestClient):
    response = _upload(client, "whk_not-a-real-key")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_valid_key_works_and_identifies_device(admin: TestClient):
    device, key, _ = create_and_pair(admin, "Alice's iPhone", "iphone")
    response = admin.get("/api/device/me", headers=auth(key))
    assert response.status_code == 200
    assert response.json() == {"id": device["id"], "name": "Alice's iPhone", "kind": "iphone"}


def test_x_api_key_header_works(admin: TestClient):
    _, key, _ = create_and_pair(admin)
    response = admin.get("/api/device/me", headers={"X-API-Key": key})
    assert response.status_code == 200


def test_bearer_scheme_is_case_insensitive(admin: TestClient):
    _, key, _ = create_and_pair(admin)
    response = admin.get("/api/device/me", headers={"Authorization": f"bearer {key}"})
    assert response.status_code == 200


def test_revoked_key_is_rejected(admin: TestClient):
    device, key, _ = create_and_pair(admin)
    assert admin.post(f"/api/admin/devices/{device['id']}/revoke").status_code == 200
    assert _upload(admin, key).status_code == 401

    devices = admin.get("/api/admin/devices").json()["devices"]
    revoked = next(item for item in devices if item["id"] == device["id"])
    assert revoked["status"] == "revoked"
    assert revoked["key_prefix"] is None


def test_deleted_device_key_is_rejected_and_history_kept(admin: TestClient):
    device, key, _ = create_and_pair(admin)
    assert _upload(admin, key).status_code == 200

    response = admin.delete(f"/api/admin/devices/{device['id']}?delete_history=false")
    assert response.status_code == 200
    assert _upload(admin, key).status_code == 401

    devices = admin.get("/api/admin/devices").json()["devices"]
    deleted = next(item for item in devices if item["id"] == device["id"])
    assert deleted["deleted"] is True
    assert deleted["display_name"] == "Deleted device"

    history = admin.get("/api/admin/transcriptions").json()["items"]
    assert any(item["device_id"] == device["id"] for item in history)
    assert all(item["device_name"] == "Deleted device" for item in history if item["device_id"] == device["id"])


def test_deleted_device_with_history_removes_rows(admin: TestClient):
    device, key, _ = create_and_pair(admin)
    assert _upload(admin, key).status_code == 200
    response = admin.delete(f"/api/admin/devices/{device['id']}?delete_history=true")
    assert response.status_code == 200
    assert admin.get("/api/admin/transcriptions").json()["items"] == []


def test_pairing_requires_a_code_for_json_claim(client: TestClient):
    response = client.post("/pair/not-a-code?format=json")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "pairing_unavailable"


def test_login_rejects_wrong_password_and_sets_session(client: TestClient):
    wrong = client.post("/api/login", json={"password": "nope"})
    assert wrong.status_code == 401
    assert client.get("/api/session").json() == {"authenticated": False}

    right = client.post("/api/login", json={"password": ADMIN_PASSWORD})
    assert right.status_code == 200
    assert client.get("/api/session").json() == {"authenticated": True}

    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/session").json() == {"authenticated": False}


def test_login_requires_json_object(client: TestClient):
    response = client.post("/api/login", content=b"not json", headers={"content-type": "application/json"})
    assert response.status_code == 400
