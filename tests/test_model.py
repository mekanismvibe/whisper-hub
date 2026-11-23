"""Optional integration test with the real tiny model (downloads ~75 MB)."""

from __future__ import annotations

import io
import math
import struct
import wave

import pytest
from fastapi.testclient import TestClient

from whisper_hub.app import create_app
from whisper_hub.config import Config
from whisper_hub.engine import WhisperEngine

from .conftest import ADMIN_PASSWORD, auth, create_and_pair


def _wav_bytes(seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for index in range(int(seconds * sample_rate)):
            value = int(1200 * math.sin(2 * math.pi * 220 * index / sample_rate))
            frames += struct.pack("<h", value)
        handle.writeframes(bytes(frames))
    return buffer.getvalue()


@pytest.mark.model
def test_tiny_model_round_trip(tmp_path):
    config = Config(
        admin_password=ADMIN_PASSWORD,
        data_dir=tmp_path / "data",
        model="tiny",
        device="cpu",
        compute_type="int8",
        preload=False,
    )
    engine = WhisperEngine(config)
    app = create_app(config, engine=engine)
    with TestClient(app) as client:
        assert client.post("/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200
        _, key, _ = create_and_pair(client)
        response = client.post(
            "/v1/audio/transcriptions",
            headers=auth(key),
            files={"file": ("tone.wav", _wav_bytes(), "audio/wav")},
            data={"response_format": "verbose_json"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "text" in body
        assert body["language"] == "english"
        assert body["task"] == "transcribe"
        assert client.get("/healthz").json()["models_loaded"] is True

        rows = client.get("/api/admin/transcriptions").json()["items"]
        if body["text"].strip():
            assert len(rows) == 1
            assert rows[0]["text"] == body["text"]
            assert rows[0]["model"] == "tiny"
        else:
            assert rows == []
