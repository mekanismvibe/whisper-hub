"""Runtime settings: env ``WHUB_*`` > SQLite ``settings`` table > built-in default."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any
from urllib.parse import urlparse

from . import catalog
from .config import Config
from .db import Database

logger = logging.getLogger(__name__)

# Fields that can be changed at runtime in the UI. Host, port and the data
# directory stay environment/CLI only.
SETTING_NAMES: tuple[str, ...] = (
    "model",
    "translate_model",
    "english_engine",
    "device",
    "compute_type",
    "cpu_threads",
    "beam_size",
    "translate_beam_size",
    "max_concurrency",
    "model_idle_unload_seconds",
    "max_upload_mb",
    "non_english",
    "lang_confidence",
    "honor_client_language",
    "public_url",
    "https_url",
    "parakeet_model",
)

ENGINE_RELOAD_FIELDS = frozenset(
    {
        "model",
        "translate_model",
        "english_engine",
        "device",
        "compute_type",
        "cpu_threads",
        "parakeet_model",
        "non_english",
    }
)

_BUILTIN_DEFAULTS = Config()


class SettingsError(ValueError):
    """A setting value was rejected."""


class EnvLockedError(SettingsError):
    def __init__(self, field: str, env: str) -> None:
        super().__init__(f"{field} is set by {env} and cannot be changed here.")
        self.field = field
        self.env = env


def env_name(field: str) -> str:
    return "WHUB_" + field.upper()


def parse_value(field: str, raw: Any) -> Any:
    """Coerce a DB string or JSON value to the field's Python type."""
    if field in {"honor_client_language", "non_english"}:
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    if field in {"cpu_threads", "beam_size", "translate_beam_size", "max_concurrency", "max_upload_mb"}:
        return int(raw)
    if field in {"model_idle_unload_seconds", "lang_confidence"}:
        return float(raw)
    if raw is None:
        return ""
    return str(raw).strip()


def serialize_value(field: str, value: Any) -> str:
    if field == "honor_client_language":
        return "1" if value else "0"
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _normalize_url(field: str, value: str) -> str:
    value = (value or "").strip().rstrip("/")
    if not value:
        return ""
    try:
        parsed = urlparse(value)
        parsed.port  # raises on a malformed port
    except ValueError:
        raise SettingsError(f"{field} must be an http:// or https:// URL.") from None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SettingsError(f"{field} must be an http:// or https:// URL.")
    return value


COMPUTE_TYPES = frozenset(
    {"auto", "default", "int8", "int8_float32", "int8_float16", "int8_bfloat16", "int16",
     "float16", "bfloat16", "float32"}
)


def validate_values(values: dict[str, Any], *, check_models: bool = True) -> dict[str, Any]:
    """Validate a complete effective settings dict; returns the normalized dict."""
    cleaned = dict(values)
    cleaned["model"] = str(cleaned.get("model") or "").strip()
    cleaned["translate_model"] = str(cleaned.get("translate_model") or "").strip()
    cleaned["compute_type"] = str(cleaned.get("compute_type") or "").strip().lower()
    cleaned["english_engine"] = str(cleaned.get("english_engine") or "").strip().lower()
    cleaned["device"] = str(cleaned.get("device") or "").strip().lower()
    if cleaned["compute_type"] not in COMPUTE_TYPES:
        raise SettingsError(f"Compute type must be one of: {', '.join(sorted(COMPUTE_TYPES))}.")
    if cleaned["device"] == "cpu" and "float16" in cleaned["compute_type"]:
        # CTranslate2 refuses fp16 on the CPU, so every model load would fail.
        raise SettingsError("float16 compute types need a CUDA GPU. Use auto or int8 on the CPU.")
    if cleaned["english_engine"] not in {"whisper", "parakeet"}:
        raise SettingsError("English engine must be whisper or parakeet.")
    if cleaned["device"] not in {"auto", "cpu", "cuda"}:
        raise SettingsError("Device must be auto, cpu or cuda.")
    if int(cleaned["beam_size"]) < 1 or int(cleaned["beam_size"]) > 10:
        raise SettingsError("Beam size must be between 1 and 10.")
    if int(cleaned["translate_beam_size"]) < 1 or int(cleaned["translate_beam_size"]) > 10:
        raise SettingsError("Translation beam size must be between 1 and 10.")
    if int(cleaned["cpu_threads"]) < 0:
        raise SettingsError("CPU threads cannot be negative.")
    if not 1 <= int(cleaned["max_concurrency"]) <= 32:
        raise SettingsError("Max concurrency must be between 1 and 32.")
    if float(cleaned["model_idle_unload_seconds"]) < 0:
        raise SettingsError("Idle unload cannot be negative.")
    if not 1 <= int(cleaned["max_upload_mb"]) <= 4096:
        raise SettingsError("Max upload must be between 1 and 4096 MB.")
    if not 0 <= float(cleaned["lang_confidence"]) <= 1:
        raise SettingsError("Language confidence must be between 0 and 1.")
    cleaned["public_url"] = _normalize_url("public_url", str(cleaned.get("public_url") or ""))
    cleaned["https_url"] = _normalize_url("https_url", str(cleaned.get("https_url") or ""))
    cleaned["parakeet_model"] = str(cleaned.get("parakeet_model") or "").strip()
    if not cleaned["parakeet_model"]:
        raise SettingsError("Parakeet model id cannot be empty.")
    if check_models:
        try:
            if cleaned.get("non_english"):
                catalog.validate_models(cleaned["model"], cleaned["translate_model"])
            elif not cleaned["model"]:
                raise ValueError("Choose a main model.")
        except ValueError as exc:
            raise SettingsError(str(exc)) from None
        if cleaned["device"] == "auto" and "float16" in cleaned["compute_type"]:
            from .engine import cuda_usable

            if not cuda_usable():
                raise SettingsError(
                    "No usable CUDA GPU was found, so float16 compute types would fail. "
                    "Use auto or int8."
                )
    return cleaned


class SettingsStore:
    """Merges the environment, the database and built-in defaults."""

    def __init__(self, config: Config, db: Database) -> None:
        self.base = config
        self.db = db
        self.locked: dict[str, str] = {
            field: name for field in SETTING_NAMES if (name := env_name(field)) in config.env_names
        }

    @property
    def password_from_env(self) -> bool:
        return bool(self.base.admin_password)

    def _base(self, field: str) -> Any:
        return getattr(self.base, field)

    def snapshot(self) -> dict[str, Any]:
        stored = self.db.get_settings()
        values: dict[str, Any] = {}
        for field in SETTING_NAMES:
            base = self._base(field)
            if field in self.locked:
                values[field] = base
                continue
            if field not in stored:
                values[field] = base
                continue
            try:
                values[field] = parse_value(field, stored[field])
            except (TypeError, ValueError):
                logger.warning("ignoring invalid stored setting %s", field)
                values[field] = base
        for field in ("public_url", "https_url"):
            if values.get(field) is None:
                values[field] = ""
        return values

    def effective_config(self, values: dict[str, Any] | None = None) -> Config:
        resolved = validate_values(
            values if values is not None else self.snapshot(), check_models=False
        )
        return replace(self.base, **resolved)

    def update(self, payload: dict[str, Any]) -> Config:
        unknown = set(payload) - set(SETTING_NAMES)
        if unknown:
            raise SettingsError(f"Unknown setting: {', '.join(sorted(unknown))}.")
        for field, env in self.locked.items():
            if field in payload:
                current = serialize_value(field, self._base(field))
                try:
                    proposed = serialize_value(field, parse_value(field, payload[field]))
                except (TypeError, ValueError):
                    raise SettingsError(f"Invalid value for {field}.") from None
                if proposed != current:
                    raise EnvLockedError(field, env)
        incoming: dict[str, Any] = {}
        for field, raw in payload.items():
            try:
                incoming[field] = parse_value(field, raw)
            except (TypeError, ValueError):
                raise SettingsError(f"Invalid value for {field}.") from None
        merged = validate_values({**self.snapshot(), **incoming})
        changed = {
            field: serialize_value(field, value)
            for field, value in merged.items()
            if serialize_value(field, value) != serialize_value(field, self.snapshot().get(field))
        }
        if changed:
            self.db.set_settings(changed)
        return self.effective_config(merged)

    def payload(self) -> dict[str, Any]:
        values = self.snapshot()
        return {
            "values": values,
            "locked": dict(self.locked),
            "defaults": {field: getattr(_BUILTIN_DEFAULTS, field) for field in SETTING_NAMES},
            "catalog": catalog.catalog_payload(),
            "password_from_env": self.password_from_env,
        }
