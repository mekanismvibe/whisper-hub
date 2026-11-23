from __future__ import annotations

import tempfile
from pathlib import Path

from starlette.formparsers import MultiPartParser

from whisper_hub.errors import DecodeError

from .conftest import ADMIN_PASSWORD, FakeEngine, auth, create_and_pair


def _files(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}


def test_audio_never_touches_disk(client_factory, tmp_path: Path, monkeypatch):
    client, fake, config = client_factory(max_upload_mb=2)
    assert isinstance(fake, FakeEngine)
    assert MultiPartParser.spool_max_size > config.max_upload_bytes

    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(spool_dir))

    assert client.post("/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200
    _, key, _ = create_and_pair(client)

    data_files = _files(config.data_dir)
    temp_files = _files(spool_dir)
    assert data_files  # the database and session secret exist before the uploads

    # Successful upload larger than 1 MB.
    response = client.post(
        "/v1/audio/transcriptions",
        headers=auth(key),
        files={"file": ("big.webm", b"\x00" * (1_500_000), "audio/webm")},
    )
    assert response.status_code == 200, response.text
    assert _files(config.data_dir) == data_files
    assert _files(spool_dir) == temp_files

    # Decode failure.
    fake.push(DecodeError("broken"))
    response = client.post(
        "/v1/audio/transcriptions",
        headers=auth(key),
        files={"file": ("bad.webm", b"\x01" * 300_000, "audio/webm")},
    )
    assert response.status_code == 400
    assert _files(config.data_dir) == data_files
    assert _files(spool_dir) == temp_files

    # Oversize upload rejected by the endpoint.
    response = client.post(
        "/v1/audio/transcriptions",
        headers=auth(key),
        files={"file": ("huge.webm", b"\x02" * (3_000_000), "audio/webm")},
    )
    assert response.status_code == 413
    assert _files(config.data_dir) == data_files
    assert _files(spool_dir) == temp_files

    # Oversize upload rejected by the body-limit middleware (5 MB > 2 MB + 1 MB).
    response = client.post(
        "/v1/audio/transcriptions",
        headers=auth(key),
        files={"file": ("huge2.webm", b"\x03" * (5_000_000), "audio/webm")},
    )
    assert response.status_code == 413
    assert _files(config.data_dir) == data_files
    assert _files(spool_dir) == temp_files

    # Web dashboard upload path.
    fake.push(DecodeError("broken"))
    response = client.post(
        "/api/admin/web-transcribe",
        files={"file": ("record.webm", b"\x04" * (1_200_000), "audio/webm")},
    )
    assert response.status_code == 400
    assert _files(config.data_dir) == data_files
    assert _files(spool_dir) == temp_files


def test_data_dir_contains_only_text_storage(client_factory):
    _, fake, config = client_factory()
    assert fake is not None
    names = {path.name for path in config.data_dir.iterdir()}
    assert "whisper.db" in names
    assert not any(name.endswith((".wav", ".mp3", ".webm", ".m4a", ".opus", ".ogg")) for name in names)
