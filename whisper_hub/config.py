"""Configuration loaded from ``WHUB_*`` environment variables and ``./.env``."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", ""}

DEVICE_KINDS = ("iphone", "ipad", "mac", "windows", "linux", "android", "web", "other")


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def _parse_int(value: str | None, default: int, name: str) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _parse_float(value: str | None, default: float, name: str) -> float:
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {value!r}") from exc


def load_dotenv(path: Path) -> dict[str, str]:
    """Read a small ``KEY=VALUE`` .env file. Existing environment wins."""
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return values
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value[:1] in "\"'" and value and value.find(value[0], 1) > 0:
            # Quoted value, possibly followed by an inline comment: keep only the quoted part.
            value = value[1 : value.find(value[0], 1)]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if key:
            values[key] = value
    return values


@dataclass(frozen=True)
class Config:
    host: str = "0.0.0.0"
    port: int = 8765
    data_dir: Path = field(default_factory=lambda: Path("./data"))
    admin_password: str | None = None
    public_url: str | None = None
    https_url: str | None = None
    model: str = "small"
    translate_model: str = ""
    device: str = "auto"
    compute_type: str = "auto"
    cpu_threads: int = 0
    beam_size: int = 5
    translate_beam_size: int = 5
    max_concurrency: int = 1
    max_upload_mb: int = 100
    model_idle_unload_seconds: float = 0.0
    preload: bool = True
    honor_client_language: bool = False
    lang_confidence: float = 0.5
    english_engine: str = "whisper"
    parakeet_model: str = "moondream/parakeet-ultra"
    # WHUB_* names that were present in the environment (used to lock settings in the UI).
    env_names: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.port < 1 or self.port > 65535:
            raise ValueError("WHUB_PORT must be between 1 and 65535")
        if self.max_upload_mb < 1:
            raise ValueError("WHUB_MAX_UPLOAD_MB must be at least 1")
        if self.beam_size < 1:
            raise ValueError("WHUB_BEAM_SIZE must be at least 1")
        if self.translate_beam_size < 1:
            raise ValueError("WHUB_TRANSLATE_BEAM_SIZE must be at least 1")
        if self.max_concurrency < 1:
            raise ValueError("WHUB_MAX_CONCURRENCY must be at least 1")
        if self.device not in {"auto", "cpu", "cuda"}:
            raise ValueError("WHUB_DEVICE must be auto, cpu or cuda")
        if self.model_idle_unload_seconds < 0:
            raise ValueError("WHUB_MODEL_IDLE_UNLOAD_SECONDS cannot be negative")
        if not 0 <= self.lang_confidence <= 1:
            raise ValueError("WHUB_LANG_CONFIDENCE must be between 0 and 1")
        if self.english_engine not in {"whisper", "parakeet"}:
            raise ValueError("WHUB_ENGLISH_ENGINE must be whisper or parakeet")
        if not self.parakeet_model.strip():
            raise ValueError("WHUB_PARAKEET_MODEL cannot be empty")
        object.__setattr__(self, "data_dir", Path(self.data_dir))
        object.__setattr__(self, "public_url", (self.public_url or "").rstrip("/") or None)
        object.__setattr__(self, "https_url", (self.https_url or "").rstrip("/") or None)

    @property
    def translate_model_name(self) -> str:
        return self.translate_model.strip() or self.model

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def uses_turbo_without_translator(self) -> bool:
        return "turbo" in self.model.lower() and not self.translate_model.strip()

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None, dotenv_path: Path | str | None = None) -> Config:
        if env is None:
            file_values = load_dotenv(Path(dotenv_path) if dotenv_path else Path(".env"))
            merged = {**file_values, **os.environ}
        else:
            merged = env

        def get(name: str) -> str | None:
            return merged.get("WHUB_" + name)

        data_dir = Path(get("DATA_DIR") or "./data")
        return cls(
            host=get("HOST") or "0.0.0.0",
            port=_parse_int(get("PORT"), 8765, "WHUB_PORT"),
            data_dir=data_dir,
            admin_password=(get("ADMIN_PASSWORD") or None),
            public_url=get("PUBLIC_URL") or None,
            https_url=get("HTTPS_URL") or None,
            model=(get("MODEL") or "small").strip(),
            translate_model=(get("TRANSLATE_MODEL") or "").strip(),
            device=(get("DEVICE") or "auto").strip().lower(),
            compute_type=(get("COMPUTE_TYPE") or "auto").strip().lower(),
            cpu_threads=_parse_int(get("CPU_THREADS"), 0, "WHUB_CPU_THREADS"),
            beam_size=_parse_int(get("BEAM_SIZE"), 5, "WHUB_BEAM_SIZE"),
            translate_beam_size=_parse_int(
                get("TRANSLATE_BEAM_SIZE"), 5, "WHUB_TRANSLATE_BEAM_SIZE"
            ),
            max_concurrency=_parse_int(get("MAX_CONCURRENCY"), 1, "WHUB_MAX_CONCURRENCY"),
            max_upload_mb=_parse_int(get("MAX_UPLOAD_MB"), 100, "WHUB_MAX_UPLOAD_MB"),
            model_idle_unload_seconds=_parse_float(
                get("MODEL_IDLE_UNLOAD_SECONDS"), 0.0, "WHUB_MODEL_IDLE_UNLOAD_SECONDS"
            ),
            preload=_parse_bool(get("PRELOAD"), True),
            honor_client_language=_parse_bool(get("HONOR_CLIENT_LANGUAGE"), False),
            lang_confidence=_parse_float(get("LANG_CONFIDENCE"), 0.5, "WHUB_LANG_CONFIDENCE"),
            english_engine=(get("ENGLISH_ENGINE") or "whisper").strip().lower(),
            parakeet_model=(get("PARAKEET_MODEL") or "moondream/parakeet-ultra").strip(),
            # Blank variables (``WHUB_MODEL=``) mean "unset", so they must not lock a setting.
            env_names=frozenset(
                key for key, value in merged.items() if key.startswith("WHUB_") and str(value).strip()
            ),
        )
