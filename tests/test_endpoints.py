from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from .conftest import ADMIN_PASSWORD, FakeEngine, auth, create_and_pair, make_result

FILE = ("clip.wav", b"pretend-this-is-audio", "audio/wav")


def post_audio(client: TestClient, key: str, endpoint: str, data: dict[str, str] | None = None):
    return client.post(
        f"/v1/audio/{endpoint}",
        headers=auth(key),
        files={"file": FILE},
        data=data or {},
    )


@pytest.mark.parametrize("endpoint", ["transcriptions", "translations"])
@pytest.mark.parametrize("response_format", ["json", "text", "verbose_json", "srt", "vtt"])
def test_every_response_format(admin: TestClient, endpoint: str, response_format: str):
    _, key, _ = create_and_pair(admin)
    response = post_audio(admin, key, endpoint, {"response_format": response_format})
    assert response.status_code == 200, response.text
    assert response.headers["X-Whub-Detected-Language"] == "en"
    assert response.headers["X-Whub-Task"] == "transcribe"
    assert response.headers["X-Whub-Transcription-Id"].isdigit()

    if response_format == "json":
        assert response.json() == {"text": "Hello world."}
    elif response_format == "text":
        assert response.text == "Hello world."
        assert response.headers["content-type"].startswith("text/plain")
    elif response_format == "verbose_json":
        body = response.json()
        assert body["task"] == "transcribe"
        assert body["language"] == "english"
        assert body["duration"] == 1.5
        assert body["text"] == "Hello world."
        assert body["segments"][0]["text"].strip() == "Hello world."
    elif response_format == "srt":
        assert response.text.startswith("1\n00:00:00,000 --> 00:00:01,500\nHello world.")
    elif response_format == "vtt":
        assert response.text.startswith("WEBVTT")
        assert "00:00:00.000 --> 00:00:01.500" in response.text


@pytest.mark.parametrize(
    ("response_format", "skip_timestamps"),
    [("text", True), ("json", True), ("verbose_json", False), ("srt", False), ("vtt", False)],
)
@pytest.mark.parametrize("endpoint", ["transcriptions", "translations"])
def test_timestamp_tokens_are_skipped_only_for_plain_formats(
    admin: TestClient, endpoint: str, response_format: str, skip_timestamps: bool
):
    _, key, _ = create_and_pair(admin)
    engine: FakeEngine = admin.app.state.engine
    response = post_audio(admin, key, endpoint, {"response_format": response_format})
    assert response.status_code == 200, response.text
    assert engine.calls[-1]["without_timestamps"] is skip_timestamps


def test_apple_shortcuts_default_to_plain_text(admin: TestClient):
    _, key, _ = create_and_pair(admin)
    shortcut = {**auth(key), "User-Agent": "BackgroundShortcutRunner/5114.0.8.3 CFNetwork/3896 Darwin/27.2.0"}
    response = admin.post("/v1/audio/transcriptions", headers=shortcut, files={"file": FILE})
    assert response.text == "Hello world."
    explicit = admin.post(
        "/v1/audio/transcriptions", headers=shortcut, files={"file": FILE}, data={"response_format": "json"}
    )
    assert explicit.json() == {"text": "Hello world."}
    other = admin.post("/v1/audio/transcriptions?response_format=text", headers=auth(key), files={"file": FILE})
    assert other.text == "Hello world."
    default = post_audio(admin, key, "transcriptions")
    assert default.json() == {"text": "Hello world."}


def test_translation_format_headers_and_verbose_language(admin: TestClient):
    _, key, _ = create_and_pair(admin)
    engine: FakeEngine = admin.app.state.engine
    engine.push(make_result("Hola mundo.", language="es", task="translate", duration=2.0))
    response = post_audio(admin, key, "translations", {"response_format": "verbose_json"})
    assert response.status_code == 200
    body = response.json()
    assert body["task"] == "translate"
    assert body["language"] == "english"  # translations report the output language
    assert response.headers["X-Whub-Task"] == "translate"
    assert response.headers["X-Whub-Detected-Language"] == "es"


def test_rows_are_stored_with_metadata(admin: TestClient):
    device, key, _ = create_and_pair(admin)
    response = post_audio(admin, key, "transcriptions", {"prompt": "Names: Alice", "language": "en"})
    assert response.status_code == 200
    row_id = int(response.headers["X-Whub-Transcription-Id"])

    row = admin.get(f"/api/admin/transcriptions/{row_id}").json()
    assert row["id"] == row_id
    assert row["device_id"] == device["id"]
    assert row["device_name"] == "Test phone"
    assert row["text"] == "Hello world."
    assert row["detected_language"] == "en"
    assert row["task"] == "transcribe"
    assert row["audio_duration_s"] == 1.5
    assert row["processing_ms"] >= 0
    assert row["model"] == "fake-model"
    assert row["endpoint"] == "transcriptions"
    assert row["client_user_agent"]

    engine: FakeEngine = admin.app.state.engine
    assert engine.calls[-1]["prompt"] == "Names: Alice"
    assert engine.calls[-1]["language"] == "en"


def test_missing_file_is_a_400(admin: TestClient):
    _, key, _ = create_and_pair(admin)
    response = admin.post(
        "/v1/audio/transcriptions",
        headers=auth(key),
        data={"response_format": "json"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_file"


def test_undecodable_audio_is_a_400(admin: TestClient):
    from whisper_hub.errors import DecodeError

    _, key, _ = create_and_pair(admin)
    engine: FakeEngine = admin.app.state.engine
    engine.push(DecodeError("bad audio"))
    response = post_audio(admin, key, "transcriptions")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_audio"


def test_invalid_response_format_is_a_400(admin: TestClient):
    _, key, _ = create_and_pair(admin)
    response = post_audio(admin, key, "transcriptions", {"response_format": "xml"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_response_format"


def test_empty_result_is_not_stored(admin: TestClient):
    _, key, _ = create_and_pair(admin)
    engine: FakeEngine = admin.app.state.engine
    before = admin.get("/api/admin/stats").json()["transcriptions_total"]
    engine.push(make_result(text="", duration=0.0))

    response = post_audio(admin, key, "transcriptions", {"response_format": "text"})
    assert response.status_code == 200
    assert response.text == ""
    assert "X-Whub-Transcription-Id" not in response.headers
    assert response.headers["X-Whub-Detected-Language"] == "en"

    after = admin.get("/api/admin/stats").json()["transcriptions_total"]
    assert after == before == 0


def test_models_list_requires_device_key_and_does_not_load_models(admin: TestClient):
    engine: FakeEngine = admin.app.state.engine
    assert admin.get("/v1/models").status_code == 401
    _, key, _ = create_and_pair(admin)
    response = admin.get("/v1/models", headers=auth(key))
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    ids = {item["id"] for item in body["data"]}
    assert {"whisper-1", "fake-model"} <= ids
    assert engine.loaded is False
    assert engine.models_loaded is True  # fake starts "loaded"; /models must not touch it


def test_healthz_is_public(client: TestClient):
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["models_loaded"] is True
    assert body["model"] == "fake-model"
    assert body["english_engine"] == "whisper"
    assert body["parakeet_model"] is None
    assert body["parakeet_loaded"] is False


def test_web_transcribe_attributes_to_web_device(admin: TestClient):
    response = admin.post(
        "/api/admin/web-transcribe",
        files={"file": ("record.webm", b"browser audio", "audio/webm")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["text"] == "Hello world."
    assert body["transcription"]["endpoint"] == "web"

    devices = admin.get("/api/admin/devices").json()["devices"]
    web = next(item for item in devices if item["builtin"])
    assert body["transcription"]["device_id"] == web["id"]
    assert web["transcription_count"] == 1
    assert web["last_text_preview"] == "Hello world."


def test_web_transcribe_empty_result(admin: TestClient):
    engine: FakeEngine = admin.app.state.engine
    engine.push(make_result(text=""))
    response = admin.post(
        "/api/admin/web-transcribe", files={"file": ("record.webm", b"silence", "audio/webm")}
    )
    assert response.status_code == 200
    assert response.json()["transcription"] is None
    assert response.json()["text"] == ""


def test_guides_payload_has_no_key(admin: TestClient):
    body = admin.get("/api/admin/setup").json()
    assert body["base_url"].startswith("http://")
    assert body["curl"]
    assert any(kind["kind"] == "iphone" for kind in body["kinds"])
    assert "whk_" not in str(body)


def test_healthz_and_models_report_the_parakeet_engine(client_factory):
    client, _, _ = client_factory(english_engine="parakeet")
    body = client.get("/healthz").json()
    assert body["english_engine"] == "parakeet"
    assert body["parakeet_model"] == "moondream/parakeet-ultra"
    assert body["parakeet_loaded"] is False

    assert client.post("/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200
    _, key, _ = create_and_pair(client)
    ids = {item["id"] for item in client.get("/v1/models", headers=auth(key)).json()["data"]}
    assert "moondream/parakeet-ultra" in ids
