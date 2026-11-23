from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import auth, create_and_pair


def _post(client: TestClient, key: str, size: int):
    return client.post(
        "/v1/audio/transcriptions",
        headers=auth(key),
        files={"file": ("upload.webm", b"\x00" * size, "audio/webm")},
    )


def test_upload_size_limit(client_factory):
    client, _, _ = client_factory(max_upload_mb=1)
    assert client.post("/api/login", json={"password": "correct-horse-battery-staple"}).status_code == 200
    _, key, _ = create_and_pair(client)

    at_limit = _post(client, key, 1024 * 1024)
    assert at_limit.status_code == 200, at_limit.text

    over = _post(client, key, 1_500_000)
    assert over.status_code == 413
    assert over.json()["error"]["code"] == "payload_too_large"

    way_over = _post(client, key, 5_000_000)
    assert way_over.status_code == 413
    assert way_over.json()["error"]["code"] == "payload_too_large"

    # Admin uploads use the same cap.
    admin_over = client.post(
        "/api/admin/web-transcribe",
        files={"file": ("record.webm", b"\x00" * 1_500_000, "audio/webm")},
    )
    assert admin_over.status_code == 413
    assert admin_over.json()["error"]["code"] == "payload_too_large"


def test_missing_multipart_file_shape(client_factory):
    client, _, _ = client_factory()
    client.post("/api/login", json={"password": "correct-horse-battery-staple"})
    _, key, _ = create_and_pair(client)
    response = client.post(
        "/v1/audio/transcriptions",
        headers={**auth(key), "content-type": "application/json"},
        content=b"{}",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_file"
