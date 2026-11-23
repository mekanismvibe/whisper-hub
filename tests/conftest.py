from __future__ import annotations

import copy
from collections import deque
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from whisper_hub.app import create_app
from whisper_hub.config import Config
from whisper_hub.engine import TranscriptionResult

ADMIN_PASSWORD = "correct-horse-battery-staple"


def make_result(
    text: str = "Hello world.",
    *,
    language: str = "en",
    task: str = "transcribe",
    duration: float = 1.5,
    model: str = "fake-model",
    probability: float = 0.98,
) -> TranscriptionResult:
    return TranscriptionResult(
        text=text,
        detected_language=language,
        language_probability=probability,
        task=task,
        duration_s=duration,
        segments=[{"id": 0, "start": 0.0, "end": duration, "text": " " + text}] if text else [],
        model=model,
    )


class FakeEngine:
    """Injectable engine: no model download, no audio decoding."""

    def __init__(self) -> None:
        self.default = make_result()
        self.queue: deque[Any] = deque()
        self.calls: list[dict[str, Any]] = []
        self.models_loaded = True
        self.device = "cpu"
        self.idle_seconds = 0.0
        self.unloaded = False
        self.loaded = False

    def push(self, result: Any) -> None:
        self.queue.append(result)

    def transcribe_bytes(
        self, data: bytes, *, prompt: str | None = None, language: str | None = None
    ) -> TranscriptionResult:
        self.calls.append({"size": len(data), "prompt": prompt, "language": language})
        if self.queue:
            item = self.queue.popleft()
            if isinstance(item, BaseException):
                raise item
            if callable(item):
                item = item(data, prompt, language)
            return copy.deepcopy(item)
        return copy.deepcopy(self.default)

    def unload(self) -> bool:
        self.unloaded = True
        self.models_loaded = False
        return True

    def load(self) -> None:
        self.loaded = True
        self.models_loaded = True


@pytest.fixture
def client_factory(tmp_path: Path):
    clients: list[TestClient] = []

    def make(**overrides: Any) -> tuple[TestClient, FakeEngine, Config]:
        data_dir = tmp_path / f"data-{len(clients)}"
        engine_factory = overrides.pop("engine_factory", None)
        params: dict[str, Any] = {
            "admin_password": ADMIN_PASSWORD,
            "data_dir": data_dir,
            "model": "fake-model",
            "preload": False,
        }
        params.update(overrides)
        config = Config(**params)
        fake = FakeEngine()
        app = create_app(config, engine=fake, engine_factory=engine_factory)
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client, fake, config

    yield make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(client_factory: Callable[..., tuple[TestClient, FakeEngine, Config]]):
    client, _, _ = client_factory()
    return client


@pytest.fixture
def fake(client) -> FakeEngine:
    return client.app.state.engine


@pytest.fixture
def config(client) -> Config:
    return client.app.state.config


@pytest.fixture
def admin(client: TestClient) -> TestClient:
    response = client.post("/api/login", json={"password": ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    return client


def create_and_pair(
    admin: TestClient, name: str = "Test phone", kind: str = "iphone"
) -> tuple[dict[str, Any], str, str]:
    response = admin.post("/api/admin/devices", json={"name": name, "kind": kind})
    assert response.status_code == 200, response.text
    payload = response.json()
    code = payload["pairing"]["code"]
    claim = admin.post(f"/pair/{code}?format=json")
    assert claim.status_code == 200, claim.text
    data = claim.json()
    return data["device"], data["api_key"], code


def auth(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


@pytest.fixture
def paired(admin: TestClient) -> tuple[dict[str, Any], str]:
    device, key, _ = create_and_pair(admin)
    return device, key


__all__ = [
    "ADMIN_PASSWORD",
    "FakeEngine",
    "auth",
    "create_and_pair",
    "make_result",
    "replace",
]
