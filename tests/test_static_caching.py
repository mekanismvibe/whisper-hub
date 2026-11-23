from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from whisper_hub.app import ASSET_VERSIONS, INDEX_ETAG, STATIC_DIR

from .conftest import FakeEngine, auth, create_and_pair, make_result

FILE = ("clip.wav", b"pretend-this-is-audio", "audio/wav")


def test_dashboard_html_uses_content_hashes(client: TestClient):
    for name in ("app.js", "style.css"):
        expected = hashlib.sha256((STATIC_DIR / name).read_bytes()).hexdigest()[:12]
        assert ASSET_VERSIONS[f"/static/{name}"] == expected

    response = client.get("/")
    assert response.status_code == 200
    assert "__APP_VERSION__" not in response.text
    assert "__STYLE_VERSION__" not in response.text
    assert f"/static/app.js?v={ASSET_VERSIONS['/static/app.js']}" in response.text
    assert f"/static/style.css?v={ASSET_VERSIONS['/static/style.css']}" in response.text
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["etag"] == INDEX_ETAG

    cached = client.get("/", headers={"If-None-Match": INDEX_ETAG})
    assert cached.status_code == 304
    assert cached.content == b""
    assert cached.headers["etag"] == INDEX_ETAG
    assert cached.headers["cache-control"] == "no-cache"


def test_hashed_assets_are_immutable_and_still_etagged(client: TestClient):
    for name in ("app.js", "style.css"):
        path = f"/static/{name}"
        version = ASSET_VERSIONS[path]
        expected = (STATIC_DIR / name).read_bytes()

        bare = client.get(path)
        assert bare.status_code == 200
        assert bare.headers["cache-control"] == "no-cache"
        assert bare.content == expected

        wrong = client.get(path, params={"v": "000000000000"})
        assert wrong.status_code == 200
        assert wrong.headers["cache-control"] == "no-cache"

        hashed = client.get(path, params={"v": version})
        assert hashed.status_code == 200
        assert hashed.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert hashed.content == expected

        cached = client.get(
            path, params={"v": version}, headers={"If-None-Match": hashed.headers["etag"]}
        )
        assert cached.status_code == 304
        assert cached.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_gzip_is_used_for_text_but_not_small_json(client: TestClient):
    compressed = client.get("/static/app.js", headers={"Accept-Encoding": "gzip"})
    assert compressed.status_code == 200
    assert compressed.headers["content-encoding"] == "gzip"
    assert "accept-encoding" in compressed.headers["vary"].lower()
    assert compressed.content == (STATIC_DIR / "app.js").read_bytes()

    identity = client.get("/static/app.js", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in identity.headers
    assert identity.content == compressed.content

    small = client.get("/api/setup/status", headers={"Accept-Encoding": "gzip"})
    assert small.status_code == 200
    assert "content-encoding" not in small.headers


def test_gzip_streamed_csv_export(admin: TestClient, fake: FakeEngine):
    _, key, _ = create_and_pair(admin)
    fake.default = make_result("Long transcript text. " * 80)
    upload = admin.post("/v1/audio/transcriptions", headers=auth(key), files={"file": FILE})
    assert upload.status_code == 200, upload.text

    export = admin.get("/api/admin/export?format=csv", headers={"Accept-Encoding": "gzip"})
    assert export.status_code == 200
    assert export.headers["content-encoding"] == "gzip"
    assert "attachment" in export.headers["content-disposition"]
    body = export.text.lstrip("\ufeff")
    assert body.splitlines()[0] == "created_at,device,detected_language,task,text"
    assert "Long transcript text." in body


def test_gzip_keeps_v1_upload_responses_intact(admin: TestClient, fake: FakeEngine):
    _, key, _ = create_and_pair(admin)
    fake.default = make_result("Large response text. " * 120)
    large = admin.post(
        "/v1/audio/transcriptions",
        headers={**auth(key), "Accept-Encoding": "gzip"},
        files={"file": FILE},
        data={"response_format": "json"},
    )
    assert large.status_code == 200, large.text
    assert large.headers["content-encoding"] == "gzip"
    assert large.headers["x-whub-detected-language"] == "en"
    assert large.json()["text"] == "Large response text. " * 120

    fake.default = make_result()
    small = admin.post(
        "/v1/audio/transcriptions",
        headers={**auth(key), "Accept-Encoding": "gzip"},
        files={"file": FILE},
        data={"response_format": "json"},
    )
    assert small.status_code == 200
    assert "content-encoding" not in small.headers
    assert small.json() == {"text": "Hello world."}
