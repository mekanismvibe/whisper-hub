from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from whisper_hub.auth import hash_device_key

from .conftest import auth, create_and_pair

EXPIRED = "2000-01-01T00:00:00.000000Z"


def _pair(admin: TestClient, name: str = "Phone") -> tuple[dict, str]:
    response = admin.post("/api/admin/devices", json={"name": name, "kind": "iphone"})
    assert response.status_code == 200
    payload = response.json()
    return payload["device"], payload["pairing"]["code"]


def test_pairing_flow_get_does_not_consume_and_post_claims(admin: TestClient):
    device, code = _pair(admin)

    first = admin.get(f"/pair/{code}")
    second = admin.get(f"/pair/{code}")
    assert first.status_code == 200
    assert second.status_code == 200
    assert "Link this device" in second.text
    assert "Phone" in second.text

    # Still pending after the GETs.
    devices = admin.get("/api/admin/devices").json()["devices"]
    pending = next(item for item in devices if item["id"] == device["id"])
    assert pending["status"] == "pending"

    claim = admin.post(f"/pair/{code}?format=json")
    assert claim.status_code == 200
    payload = claim.json()
    key = payload["api_key"]
    assert key.startswith("whk_")
    assert payload["base_url"].startswith("http://")
    assert payload["device"]["status"] == "active"
    setup = payload["setup"]
    assert setup["api_base"].endswith("/v1/")
    assert setup["endpoint"].endswith("/v1/audio/transcriptions")
    assert setup["model"] == "whisper-1"
    labels = [item["label"] for item in setup["values"]]
    assert any("Base URL" in label for label in labels)
    assert any("Full endpoint" in label for label in labels)
    assert any("API key" in label for label in labels)
    assert any("Model" in label for label in labels)

    me = admin.get("/api/device/me", headers=auth(key))
    assert me.status_code == 200
    assert me.json()["name"] == "Phone"

    # The key is visible once in the HTML setup page.
    html_claim = admin.post(f"/pair/{code}")
    assert html_claim.status_code == 410

    devices = admin.get("/api/admin/devices").json()["devices"]
    active = next(item for item in devices if item["id"] == device["id"])
    assert active["status"] == "active"
    assert active["has_key"] is True


def test_setup_page_shows_key_and_guide(admin: TestClient):
    response = admin.post("/api/admin/devices", json={"name": "Pixel", "kind": "android"})
    android_code = response.json()["pairing"]["code"]
    claim = admin.post(f"/pair/{android_code}")
    assert claim.status_code == 200
    text = claim.text
    assert "Device linked" in text
    assert "API key" in text
    assert "whk_" in text
    assert "Base URL" in text
    assert "Full endpoint" in text
    assert "whisper-1" in text
    assert "Dictate" in text
    assert "/v1/audio/transcriptions" in text


def test_second_claim_fails(admin: TestClient):
    _, key, code = create_and_pair(admin)
    again = admin.post(f"/pair/{code}?format=json")
    assert again.status_code == 410
    assert again.json()["error"]["code"] == "pairing_unavailable"
    assert admin.get("/api/device/me", headers=auth(key)).status_code == 200


def test_expired_code_fails(admin: TestClient, config):
    device, code = _pair(admin, "Expired")
    conn = sqlite3.connect(config.data_dir / "whisper.db")
    try:
        conn.execute(
            "UPDATE pairing_codes SET expires_at = ? WHERE code_hash = ?",
            (EXPIRED, hash_device_key(code)),
        )
        conn.commit()
    finally:
        conn.close()

    page = admin.get(f"/pair/{code}")
    assert page.status_code == 410
    assert "expired" in page.text.lower()

    claim = admin.post(f"/pair/{code}?format=json")
    assert claim.status_code == 410
    devices = admin.get("/api/admin/devices").json()["devices"]
    still_pending = next(item for item in devices if item["id"] == device["id"])
    assert still_pending["status"] == "pending"


def test_repair_rotates_key_and_old_key_stops_working(admin: TestClient):
    device, old_key, _ = create_and_pair(admin, "Rotating")
    assert admin.get("/api/device/me", headers=auth(old_key)).status_code == 200

    response = admin.post(f"/api/admin/devices/{device['id']}/pair")
    assert response.status_code == 200
    code = response.json()["pairing"]["code"]
    claim = admin.post(f"/pair/{code}?format=json")
    assert claim.status_code == 200
    new_key = claim.json()["api_key"]
    assert new_key != old_key

    assert admin.get("/api/device/me", headers=auth(old_key)).status_code == 401
    assert admin.get("/api/device/me", headers=auth(new_key)).status_code == 200

    devices = admin.get("/api/admin/devices").json()["devices"]
    rotated = next(item for item in devices if item["id"] == device["id"])
    assert rotated["key_prefix"] == new_key[:8]


def test_new_pairing_code_invalidates_previous_unclaimed_code(admin: TestClient):
    device, first_code = _pair(admin)
    second = admin.post(f"/api/admin/devices/{device['id']}/pair").json()
    # Creating a new code invalidates the previous unclaimed one.
    assert admin.post(f"/pair/{first_code}?format=json").status_code == 404
    assert admin.post(f"/pair/{second['pairing']['code']}?format=json").status_code == 200


def test_web_dashboard_device_cannot_be_paired_or_revoked(admin: TestClient):
    devices = admin.get("/api/admin/devices").json()["devices"]
    web = next(item for item in devices if item["builtin"])
    assert web["kind"] == "web"
    assert web["status"] == "active"
    assert web["key_prefix"] is None

    assert admin.post(f"/api/admin/devices/{web['id']}/pair").status_code == 400
    assert admin.post(f"/api/admin/devices/{web['id']}/revoke").status_code == 400
    assert admin.delete(f"/api/admin/devices/{web['id']}").status_code == 400


def test_device_kind_validation(admin: TestClient):
    response = admin.post("/api/admin/devices", json={"name": "Thing", "kind": "toaster"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_kind"

    response = admin.post("/api/admin/devices", json={"name": "   "})
    assert response.status_code == 400


def test_https_url_is_recommended_on_setup(client_factory):
    client, _, _ = client_factory(https_url="https://whisper.example.com")
    assert client.post("/api/login", json={"password": "correct-horse-battery-staple"}).status_code == 200
    _, code = _pair(client, "Secure phone")
    payload = client.post(f"/pair/{code}?format=json").json()
    setup = payload["setup"]
    assert setup["base_url"] == "https://whisper.example.com"
    assert setup["lan_url"].startswith("http://testserver")
    assert setup["api_base"] == "https://whisper.example.com/v1/"
    assert setup["endpoint"] == "https://whisper.example.com/v1/audio/transcriptions"
