"""FastAPI application: OpenAI-compatible audio API, admin API, pairing pages and SPA."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import secrets
import socket
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import segno
import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartParser

from . import __version__, catalog, cuda, hardware
from .auth import (
    LoginLimiter,
    constant_time_equals,
    display_prefix,
    generate_device_key,
    hash_device_key,
    hash_password,
    require_admin,
    require_device,
    validate_new_password,
    verify_password,
)
from .config import DEVICE_KINDS, Config
from .db import Database, decode_cursor, encode_cursor
from .engine import EngineProtocol, TranscriptionResult, WhisperEngine
from .errors import ApiError, DecodeError, EngineBusyError, PayloadTooLarge
from .formats import RESPONSE_FORMATS, render_srt, render_vtt, verbose_json
from .guides import guides_for_setup, setup_payload
from .manager import EngineManager
from .middleware import BodyLimitMiddleware, RotatingSessionMiddleware
from .pages import render_error_page, render_pair_page, render_setup_page
from .settings import ENGINE_RELOAD_FIELDS, EnvLockedError, SettingsError, SettingsStore

logger = logging.getLogger("whisper_hub")

STATIC_DIR = Path(__file__).parent / "static"
PAIRING_TTL = timedelta(minutes=15)


# --------------------------------------------------------------------------- helpers


def _utc_iso(delta: timedelta = timedelta(0)) -> str:
    return (datetime.now(timezone.utc) + delta).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _base_url(request: Request) -> str:
    configured = request.app.state.config.public_url
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _wants_json(request: Request) -> bool:
    if request.query_params.get("format", "").lower() == "json":
        return True
    accept = request.headers.get("accept", "").lower()
    return "application/json" in accept and "text/html" not in accept


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        raise ApiError(400, "Request body must be valid JSON.", code="invalid_json") from None
    if not isinstance(payload, dict):
        raise ApiError(400, "Request body must be a JSON object.", code="invalid_json")
    return payload


def _clean_name(value: Any) -> str:
    if not isinstance(value, str):
        raise ApiError(400, "Device name is required.", code="invalid_name")
    name = " ".join(value.split())
    if not name:
        raise ApiError(400, "Device name is required.", code="invalid_name")
    if len(name) > 80:
        raise ApiError(400, "Device name must be 80 characters or fewer.", code="invalid_name")
    return name


def _clean_kind(value: Any, *, default: str = "other") -> str:
    if value is None:
        return default
    if not isinstance(value, str) or value not in DEVICE_KINDS:
        raise ApiError(400, f"Device kind must be one of: {', '.join(DEVICE_KINDS)}.", code="invalid_kind")
    return value


def _device_payload(device: dict[str, Any]) -> dict[str, Any]:
    preview = (device.get("last_text") or "").strip()
    if len(preview) > 200:
        preview = preview[:200].rstrip() + "…"
    return {
        "id": device["id"],
        "name": device["name"],
        "display_name": device["display_name"],
        "kind": device["kind"],
        "status": device["status"],
        "builtin": bool(device["builtin"]),
        "deleted": bool(device["deleted"]),
        "has_key": bool(device.get("has_key")),
        "key_prefix": device.get("key_prefix"),
        "created_at": device["created_at"],
        "activated_at": device.get("activated_at"),
        "revoked_at": device.get("revoked_at"),
        "last_seen_at": device.get("last_seen_at"),
        "last_ip": device.get("last_ip"),
        "last_user_agent": device.get("last_user_agent"),
        "transcription_count": device.get("transcription_count", 0),
        "last_transcription_at": device.get("last_transcription_at"),
        "last_text_preview": preview,
        "last_language": device.get("last_language"),
        "last_task": device.get("last_task"),
    }


def _pairing_payload(request: Request, code: str, expires_at: str) -> dict[str, Any]:
    url = f"{_base_url(request)}/pair/{code}"
    svg = segno.make(url, error="m").svg_inline(scale=4, border=2, dark="#111827", light="#ffffff")
    return {"code": code, "url": url, "expires_at": expires_at, "qr_svg": svg}


def _new_pairing(request: Request, device_id: int) -> dict[str, Any]:
    code = secrets.token_urlsafe(16)
    expires_at = _utc_iso(PAIRING_TTL)
    request.app.state.db.create_pairing_code(device_id, hash_device_key(code), expires_at)
    return _pairing_payload(request, code, expires_at)


def _human_expiry(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        return parsed.strftime("%H:%M UTC on %d %b")
    except ValueError:
        return value


async def _read_audio_form(request: Request) -> tuple[bytes, dict[str, str]]:
    """Parse a multipart upload entirely in memory and close every spooled file."""
    try:
        form = await request.form()
    except PayloadTooLarge:
        raise
    except Exception as exc:
        raise ApiError(400, "Could not parse the multipart upload.", code="invalid_multipart") from exc
    try:
        file = form.get("file")
        fields = {key: value for key, value in form.multi_items() if isinstance(value, str)}
        if not isinstance(file, UploadFile):
            raise ApiError(
                400,
                "Missing required 'file' field. Send the audio as multipart form data.",
                code="missing_file",
            )
        data = await file.read()
    finally:
        for _, value in form.multi_items():
            if isinstance(value, UploadFile):
                try:
                    await value.close()
                except Exception:  # pragma: no cover - already closed
                    pass
    limit = request.app.state.config.max_upload_bytes
    if len(data) > limit:
        raise ApiError(
            413,
            f"Upload exceeds the {request.app.state.config.max_upload_mb} MB limit.",
            code="payload_too_large",
        )
    if not data:
        raise ApiError(400, "The uploaded file is empty.", code="empty_file")
    return data, fields


def _normalize_language(value: str | None) -> str | None:
    if not value:
        return None
    base = value.strip().lower().replace("_", "-").split("-")[0]
    if 2 <= len(base) <= 3 and base.isalpha():
        return base
    return None


async def _transcribe(
    request: Request, data: bytes, *, prompt: str | None, language: str | None
) -> tuple[TranscriptionResult, int]:
    started = time.perf_counter()
    try:
        async with request.app.state.semaphore:
            result = await asyncio.to_thread(
                request.app.state.engine.transcribe_bytes,
                data,
                prompt=prompt,
                language=language,
            )
    except DecodeError:
        raise ApiError(400, "Could not decode the uploaded audio.", code="invalid_audio") from None
    except EngineBusyError:
        logger.exception("inference failed")
        raise ApiError(500, "Transcription failed.", type_="server_error", code="inference_failed") from None
    except Exception:
        logger.exception("unexpected inference failure")
        raise ApiError(500, "Transcription failed.", type_="server_error", code="inference_failed") from None
    finally:
        del data
    processing_ms = int((time.perf_counter() - started) * 1000)
    return result, processing_ms


def _store(
    request: Request,
    device_id: int,
    result: TranscriptionResult,
    processing_ms: int,
    endpoint: str,
) -> dict[str, Any] | None:
    if not result.text.strip():
        return None
    return request.app.state.db.insert_transcription(
        device_id=device_id,
        text=result.text,
        detected_language=result.detected_language,
        language_probability=result.language_probability,
        task=result.task,
        audio_duration_s=result.duration_s,
        processing_ms=processing_ms,
        model=result.model or request.app.state.config.model,
        endpoint=endpoint,
        client_user_agent=request.headers.get("user-agent"),
    )


def _response_headers(result: TranscriptionResult, row: dict[str, Any] | None) -> dict[str, str]:
    headers = {
        "X-Whub-Detected-Language": result.detected_language or "",
        "X-Whub-Task": result.task,
    }
    if row is not None:
        headers["X-Whub-Transcription-Id"] = str(row["id"])
    return headers


def _audio_response(result: TranscriptionResult, response_format: str, row: dict[str, Any] | None) -> Response:
    headers = _response_headers(result, row)
    if response_format == "json":
        return JSONResponse({"text": result.text}, headers=headers)
    if response_format == "text":
        return Response(result.text, media_type="text/plain; charset=utf-8", headers=headers)
    if response_format == "verbose_json":
        return JSONResponse(verbose_json(result), headers=headers)
    if response_format == "srt":
        return Response(render_srt(result), media_type="application/x-subrip; charset=utf-8", headers=headers)
    if response_format == "vtt":
        return Response(render_vtt(result), media_type="text/vtt; charset=utf-8", headers=headers)
    raise ApiError(400, f"Unsupported response_format: {response_format}", code="invalid_response_format")


def _ensure_web_device(db: Database) -> dict[str, Any]:
    device = db.get_builtin_device("web")
    if device is None:
        device = db.create_device("Web dashboard", "web", builtin=True)
        db.activate_without_key(device["id"])
        device = db.get_device(device["id"]) or device
    return device


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _load_session_secret(data_dir: Path) -> str:
    path = data_dir / "session_secret"
    try:
        secret = path.read_text(encoding="utf-8").strip()
        if secret:
            return secret
    except FileNotFoundError:
        pass
    secret = secrets.token_urlsafe(48)
    _write_private(path, secret + "\n")
    return secret


def _rotate_session_secret(data_dir: Path) -> str:
    secret = secrets.token_urlsafe(48)
    _write_private(data_dir / "session_secret", secret + "\n")
    return secret


def _migrate_legacy_password(db: Database, data_dir: Path, config: Config) -> bool:
    """Move a pre-settings password file into the database, keeping it usable."""
    if config.admin_password or db.get_setting("admin_password_hash"):
        return False
    path = data_dir / "admin_password"
    try:
        password = path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return False
    if not password:
        return False
    db.set_settings(
        {"admin_password_hash": hash_password(password), "setup_completed": "1"}
    )
    logger.warning(
        "Migrated the legacy admin password from %s into the database; %s can now be deleted.",
        path,
        path,
    )
    return True


def _setup_token_path(data_dir: Path) -> Path:
    return data_dir / "setup_token"


def _issue_setup_token(data_dir: Path) -> str:
    token = secrets.token_urlsafe(24)
    _write_private(_setup_token_path(data_dir), token + "\n")
    return token


def _clear_setup_token(data_dir: Path) -> None:
    try:
        _setup_token_path(data_dir).unlink()
    except FileNotFoundError:
        pass
    except OSError:
        logger.warning("could not remove the setup token file", exc_info=True)


def _setup_url(config: Config, token: str) -> str:
    base = config.public_url or config.https_url
    if not base:
        host = config.host
        if host in {"0.0.0.0", "::", ""}:
            host = socket.gethostname()
        base = f"http://{host}:{config.port}"
    return f"{base.rstrip('/')}/setup?token={token}"


def _expected_model_bytes(config: Config) -> int:
    names = {config.model, config.translate_model_name}
    if config.english_engine == "parakeet":
        names.add(config.parakeet_model)
    total = 0
    for name in names:
        info = catalog.model_info(name)
        if info is not None:
            total += info.download_mb * 1024 * 1024
    return total


def _sync_upload_limit(config: Config) -> None:
    # Keep multipart spools in RAM; the body limiter rejects anything above the cap.
    MultiPartParser.spool_max_size = max(config.max_upload_bytes + 8 * 1024 * 1024, 16 * 1024 * 1024)


def _start_engine_swap(app: FastAPI, new_config: Config, fields: set[str]) -> bool:
    """Load a replacement engine in the background when model settings changed."""
    if not fields & ENGINE_RELOAD_FIELDS:
        return False
    manager: EngineManager = app.state.manager
    if manager.busy:
        raise ApiError(
            409,
            "A model is already loading. Wait for it to finish and save again.",
            code="swap_in_progress",
        )
    expected = _expected_model_bytes(new_config) or None
    started = manager.request_swap(
        lambda: app.state.engine_factory(new_config),
        model=new_config.model,
        expected_bytes=expected,
    )
    if not started:
        raise ApiError(409, "A model is already loading.", code="swap_in_progress")
    return True


# --------------------------------------------------------------------------- app


def create_app(
    config: Config | None = None,
    *,
    engine: EngineProtocol | None = None,
    engine_factory: Any | None = None,
) -> FastAPI:
    config = config or Config.from_env()
    data_dir = config.data_dir
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    cuda.preload_cuda_libraries()

    db = Database(data_dir / "whisper.db")
    db.initialize()
    web_device = _ensure_web_device(db)
    legacy_migrated = _migrate_legacy_password(db, data_dir, config)
    settings_store = SettingsStore(config, db)
    config = settings_store.effective_config()
    session_secret = _load_session_secret(data_dir)
    setup_required = not bool(config.admin_password) and not bool(
        db.get_setting("admin_password_hash")
    )
    setup_token: str | None = None
    if setup_required:
        setup_token = _issue_setup_token(data_dir)
        logger.warning("First-run setup is required. Open %s", _setup_url(config, setup_token))
        logger.warning(
            "The one-time setup token is also in %s (it is deleted when setup finishes).",
            _setup_token_path(data_dir),
        )
        logger.warning(
            "In Docker, read the token from the data volume (or `docker logs`) and open "
            "the published address instead of the container hostname."
        )
    elif not legacy_migrated:
        _clear_setup_token(data_dir)

    _sync_upload_limit(config)

    engine_factory = engine_factory or WhisperEngine
    engine = engine or engine_factory(config)
    if config.uses_turbo_without_translator:
        logger.warning(
            "WHUB_MODEL=%s cannot translate. Set WHUB_TRANSLATE_MODEL "
            "(for example large-v3) or non-English audio will fail.",
            config.model,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        idle_task: asyncio.Task[None] | None = None
        # Do not download any model before the wizard has chosen one.
        if config.preload and not app.state.setup_required:
            try:
                await asyncio.to_thread(app.state.engine.load)
            except Exception:
                app.state.manager.set_error("Model preload failed. See the server log.")
                logger.exception("model preload failed; will retry on the first request")
            else:
                app.state.manager.mark_ready()

        async def idle_loop() -> None:
            while True:
                current = app.state.config
                timeout = current.model_idle_unload_seconds
                await asyncio.sleep(min(max(timeout / 4, 1.0), 30.0) if timeout > 0 else 5.0)
                if timeout <= 0:
                    continue
                try:
                    active = app.state.engine
                    idle_for = getattr(active, "idle_seconds", 0.0)
                    if idle_for >= timeout and active.models_loaded:
                        await asyncio.to_thread(active.unload)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("idle unload failed")

        idle_task = asyncio.create_task(idle_loop())
        logger.info(
            "whisper-hub %s ready: model=%s translate_model=%s english_engine=%s "
            "parakeet_model=%s device=%s data=%s",
            __version__,
            config.model,
            config.translate_model_name,
            config.english_engine,
            config.parakeet_model if config.english_engine == "parakeet" else None,
            getattr(engine, "device", config.device),
            data_dir,
        )
        try:
            yield
        finally:
            if idle_task is not None:
                idle_task.cancel()
                try:
                    await idle_task
                except (asyncio.CancelledError, Exception):
                    pass

    app = FastAPI(
        title="Whisper Hub",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.config = config
    app.state.db = db
    app.state.engine = engine
    app.state.engine_factory = engine_factory
    app.state.manager = EngineManager(
        engine, on_swap=lambda new_engine: setattr(app.state, "engine", new_engine)
    )
    app.state.settings = settings_store
    app.state.session_secret = session_secret
    app.state.setup_required = setup_required
    app.state.setup_token = setup_token
    app.state.legacy_migrated = legacy_migrated
    app.state.semaphore = asyncio.Semaphore(config.max_concurrency)
    app.state.login_limiter = LoginLimiter()
    app.state.web_device_id = web_device["id"]

    app.add_middleware(
        RotatingSessionMiddleware,
        get_secret=lambda: app.state.session_secret,
        session_cookie="whub_session",
        max_age=30 * 24 * 3600,
        same_site="lax",
        https_only=False,
    )
    app.add_middleware(
        BodyLimitMiddleware,
        get_limits=lambda: (app.state.config.max_upload_bytes, app.state.config.max_upload_mb),
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        path = request.url.path
        if path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        elif path.startswith(("/api/", "/v1/", "/healthz")):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(exc.body(), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(PayloadTooLarge)
    async def payload_handler(request: Request, exc: PayloadTooLarge) -> JSONResponse:
        return JSONResponse(
            {
                "error": {
                    "message": f"Upload exceeds the {request.app.state.config.max_upload_mb} MB limit.",
                    "type": "invalid_request_error",
                    "code": "payload_too_large",
                }
            },
            status_code=413,
        )

    @app.exception_handler(OverflowError)
    async def overflow_handler(request: Request, exc: OverflowError) -> JSONResponse:
        # Ids/cursors beyond SQLite's 64-bit range cannot exist; treat them as bad input.
        return JSONResponse(ApiError(400, "Number out of range.", code="invalid_parameter").body(), status_code=400)

    # ------------------------------------------------------------ public endpoints

    @app.get("/healthz")
    async def healthz(request: Request) -> dict[str, Any]:
        current = request.app.state.config
        active = request.app.state.engine
        return {
            "ok": True,
            "model": current.model,
            "translate_model": current.translate_model_name,
            "english_engine": current.english_engine,
            "parakeet_model": (
                current.parakeet_model if current.english_engine == "parakeet" else None
            ),
            "device": getattr(active, "device", current.device),
            "models_loaded": bool(active.models_loaded),
            "parakeet_loaded": bool(getattr(active, "parakeet_loaded", False)),
            "model_status": request.app.state.manager.status()["state"],
        }

    @app.get("/v1/models")
    async def list_models(
        request: Request, device: dict[str, Any] = Depends(require_device)
    ) -> dict[str, Any]:
        current = request.app.state.config
        names = ["whisper-1", current.model]
        if current.translate_model_name != current.model:
            names.append(current.translate_model_name)
        if current.english_engine == "parakeet":
            names.append(current.parakeet_model)
        seen: set[str] = set()
        data = []
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            data.append(
                {"id": name, "object": "model", "created": int(time.time()), "owned_by": "whisper-hub"}
            )
        return {"object": "list", "data": data}

    @app.get("/api/device/me")
    async def device_me(device: dict[str, Any] = Depends(require_device)) -> dict[str, Any]:
        return {"id": device["id"], "name": device["display_name"], "kind": device["kind"]}

    async def audio_endpoint(request: Request, device: dict[str, Any], endpoint: str) -> Response:
        data, fields = await _read_audio_form(request)
        requested = fields.get("response_format") or request.query_params.get("response_format")
        if not requested:
            # Apple Shortcuts shows the raw body in notifications/clipboard, so plain text is
            # what a Shortcut wants unless it explicitly asks for something else.
            agent = request.headers.get("user-agent", "")
            requested = "text" if agent.startswith(("BackgroundShortcutRunner", "Shortcuts")) else "json"
        response_format = requested.strip().lower()
        if response_format not in RESPONSE_FORMATS:
            raise ApiError(
                400,
                f"Unsupported response_format '{response_format}'. "
                f"Use one of: {', '.join(sorted(RESPONSE_FORMATS))}.",
                code="invalid_response_format",
            )
        result, processing_ms = await _transcribe(
            request,
            data,
            prompt=fields.get("prompt"),
            language=_normalize_language(fields.get("language")),
        )
        row = _store(request, device["id"], result, processing_ms, endpoint)
        return _audio_response(result, response_format, row)

    @app.post("/v1/audio/transcriptions")
    async def transcriptions(request: Request, device: dict[str, Any] = Depends(require_device)) -> Response:
        return await audio_endpoint(request, device, "transcriptions")

    @app.post("/v1/audio/translations")
    async def translations(request: Request, device: dict[str, Any] = Depends(require_device)) -> Response:
        return await audio_endpoint(request, device, "translations")

    # ------------------------------------------------------------- pairing (public)

    @app.get("/pair/{code}", response_class=HTMLResponse)
    async def pair_page(request: Request, code: str) -> HTMLResponse:
        pairing = request.app.state.db.get_pairing(hash_device_key(code))
        headers = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"}
        if pairing is None:
            return HTMLResponse(
                render_error_page(
                    "This pairing link is not valid",
                    "Check that the whole link was copied, or create a new pairing code in the dashboard.",
                ),
                status_code=404,
                headers=headers,
            )
        if pairing["claimed"]:
            return HTMLResponse(
                render_error_page(
                    "This pairing link was already used",
                    "API keys are shown only once. Create a fresh pairing code from the dashboard "
                    "if you need to link this device again.",
                ),
                status_code=410,
                headers=headers,
            )
        if pairing["expired"] or pairing["device_deleted_at"]:
            return HTMLResponse(
                render_error_page(
                    "This pairing link has expired",
                    "Pairing codes last 15 minutes. Create a new one from the dashboard.",
                ),
                status_code=410,
                headers=headers,
            )
        return HTMLResponse(
            render_pair_page(
                pairing["display_name"],
                pairing["device_kind"],
                _base_url(request),
                code,
                _human_expiry(pairing["expires_at"]),
            ),
            headers=headers,
        )

    @app.post("/pair/{code}")
    async def claim_pairing(request: Request, code: str) -> Response:
        db_ = request.app.state.db
        key = generate_device_key()
        device = db_.claim_pairing(hash_device_key(code), hash_device_key(key), display_prefix(key))
        headers = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"}
        if device is None:
            existing = db_.get_pairing(hash_device_key(code))
            message = (
                "This pairing link was already used or has expired."
                if existing is not None
                else "This pairing link is not valid."
            )
            if _wants_json(request):
                raise ApiError(410 if existing is not None else 404, message, code="pairing_unavailable")
            return HTMLResponse(
                render_error_page(
                    "This pairing link is no longer usable",
                    message + " Create a new pairing code from the dashboard.",
                ),
                status_code=410 if existing is not None else 404,
                headers=headers,
            )
        base_url = _base_url(request)
        payload = setup_payload(
            base_url,
            key,
            device["display_name"],
            device["kind"],
            request.app.state.config.model,
            request.app.state.config.https_url,
        )
        if _wants_json(request):
            return JSONResponse(
                {"device": _device_payload(device), "api_key": key, "base_url": base_url, "setup": payload},
                headers=headers,
            )
        return HTMLResponse(render_setup_page(payload), headers=headers)

    # ---------------------------------------------------------------- first-run setup

    def require_setup_token(request: Request, token: Any) -> None:
        if not request.app.state.setup_required:
            raise ApiError(410, "Setup is already complete.", code="setup_complete")
        expected = request.app.state.setup_token
        if not isinstance(token, str) or not expected or not secrets.compare_digest(token, expected):
            raise ApiError(
                403,
                "Invalid or missing setup token. Open the setup URL printed in the server log.",
                type_="authentication_error",
                code="invalid_setup_token",
            )

    @app.get("/api/setup/status")
    async def setup_status(request: Request, token: str | None = None) -> dict[str, Any]:
        required = bool(request.app.state.setup_required)
        expected = request.app.state.setup_token
        token_valid = bool(
            required and token and expected and secrets.compare_digest(token, expected)
        )
        return {
            "setup_required": required,
            "token_valid": token_valid,
            "authenticated": (getattr(request, "session", None) or {}).get("admin") is True,
        }

    @app.post("/api/setup/password")
    async def setup_password(request: Request) -> dict[str, Any]:
        payload = await _json_body(request)
        require_setup_token(request, payload.get("token"))
        try:
            password = validate_new_password(payload.get("password"), payload.get("confirm"))
        except ValueError as exc:
            raise ApiError(400, str(exc), code="invalid_password") from None
        request.app.state.db.set_setting("admin_password_hash", hash_password(password))
        logger.info("admin password set during first-run setup")
        return {"ok": True}

    @app.get("/api/setup/hardware")
    async def setup_hardware(request: Request, token: str | None = None) -> dict[str, Any]:
        require_setup_token(request, token)
        detected = hardware.detect_hardware()
        store: SettingsStore = request.app.state.settings
        return {
            "hardware": detected,
            "catalog": catalog.catalog_payload(),
            # Fields pinned by WHUB_* env vars: the wizard shows them read-only.
            "locked": dict(store.locked),
            "values": {field: store.snapshot().get(field) for field in store.locked},
        }

    @app.post("/api/setup/finish")
    async def setup_finish(request: Request) -> dict[str, Any]:
        payload = await _json_body(request)
        require_setup_token(request, payload.get("token"))
        db_ = request.app.state.db
        if not db_.get_setting("admin_password_hash") and not request.app.state.config.admin_password:
            raise ApiError(400, "Set a password before finishing setup.", code="password_required")
        english_engine = str(payload.get("english_engine") or "whisper").strip().lower()
        if english_engine == "parakeet" and not hardware.moondream_available():
            raise ApiError(
                400,
                "The Parakeet engine is not installed. Run 'uv sync --extra parakeet' first.",
                code="parakeet_unavailable",
            )
        selection = {
            "model": payload.get("model"),
            "translate_model": payload.get("translate_model") or "",
            "english_engine": english_engine,
            "public_url": payload.get("public_url") or "",
            "https_url": payload.get("https_url") or "",
        }
        # Env vars win over the wizard (env > DB > default), so pinned fields are skipped
        # rather than making setup impossible to finish.
        for field in request.app.state.settings.locked:
            selection.pop(field, None)
        try:
            new_config = request.app.state.settings.update(selection)
        except EnvLockedError as exc:
            raise ApiError(409, str(exc), code="env_locked") from None
        except SettingsError as exc:
            raise ApiError(400, str(exc), code="invalid_setting") from None
        db_.set_settings({"setup_completed": "1"})
        request.app.state.setup_required = False
        request.app.state.setup_token = None
        _clear_setup_token(data_dir)
        request.app.state.config = new_config
        _sync_upload_limit(new_config)
        reload_started = False
        try:
            reload_started = _start_engine_swap(app, new_config, set(selection))
        except ApiError:
            logger.exception("could not start the model load after setup")
        request.session.clear()
        request.session["admin"] = True
        logger.info("first-run setup complete")
        return {
            "authenticated": True,
            "reload_started": reload_started,
            "model_status": request.app.state.manager.status(),
        }

    # ---------------------------------------------------------------- admin: auth

    @app.post("/api/login")
    async def login(request: Request) -> JSONResponse:
        if request.app.state.setup_required:
            raise ApiError(
                409,
                "This instance is in first-run setup. Open the setup URL printed in the server log.",
                type_="authentication_error",
                code="setup_required",
            )
        limiter: LoginLimiter = request.app.state.login_limiter
        ip = _client_ip(request)
        limiter.check(ip)
        payload = await _json_body(request)
        password = payload.get("password")
        if not isinstance(password, str):
            raise ApiError(400, "Password is required.", code="invalid_password")
        expected = request.app.state.config.admin_password
        if expected:
            valid = constant_time_equals(password, expected)
        else:
            stored = request.app.state.db.get_setting("admin_password_hash")
            valid = bool(stored) and verify_password(password, stored or "")
        if not valid:
            limiter.record_failure(ip)
            raise ApiError(401, "Incorrect password.", type_="authentication_error", code="invalid_password")
        limiter.record_success(ip)
        request.session.clear()
        request.session["admin"] = True
        return JSONResponse({"authenticated": True})

    @app.post("/api/logout")
    async def logout(request: Request) -> JSONResponse:
        request.session.clear()
        return JSONResponse({"ok": True})

    @app.get("/api/session")
    async def session_info(request: Request) -> JSONResponse:
        authenticated = (getattr(request, "session", None) or {}).get("admin") is True
        return JSONResponse({"authenticated": authenticated})

    # ---------------------------------------------------------------- admin: API

    admin = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

    @admin.get("/devices")
    async def admin_devices(request: Request) -> dict[str, Any]:
        return {"devices": [_device_payload(d) for d in request.app.state.db.list_devices()]}

    @admin.post("/devices")
    async def admin_create_device(request: Request) -> dict[str, Any]:
        payload = await _json_body(request)
        name = _clean_name(payload.get("name"))
        kind = _clean_kind(payload.get("kind"), default="other")
        db_ = request.app.state.db
        device = db_.create_device(name, kind)
        pairing = _new_pairing(request, device["id"])
        return {"device": _device_payload(device), "pairing": pairing}

    @admin.patch("/devices/{device_id}")
    async def admin_update_device(request: Request, device_id: int) -> dict[str, Any]:
        db_ = request.app.state.db
        device = db_.get_device(device_id)
        if device is None:
            raise ApiError(404, "Device not found.", code="not_found")
        if device["builtin"]:
            raise ApiError(400, "The built-in web dashboard device cannot be modified.", code="builtin_device")
        payload = await _json_body(request)
        name = _clean_name(payload["name"]) if "name" in payload else None
        kind = _clean_kind(payload["kind"]) if "kind" in payload else None
        updated = db_.rename_device(device_id, name=name, kind=kind)
        assert updated is not None
        return {"device": _device_payload(updated)}

    @admin.post("/devices/{device_id}/revoke")
    async def admin_revoke_device(request: Request, device_id: int) -> dict[str, Any]:
        db_ = request.app.state.db
        device = db_.get_device(device_id)
        if device is None:
            raise ApiError(404, "Device not found.", code="not_found")
        if device["builtin"]:
            raise ApiError(400, "The built-in web dashboard device cannot be revoked.", code="builtin_device")
        db_.revoke_device(device_id)
        updated = db_.get_device(device_id)
        assert updated is not None
        return {"device": _device_payload(updated)}

    @admin.delete("/devices/{device_id}")
    async def admin_delete_device(request: Request, device_id: int) -> dict[str, Any]:
        db_ = request.app.state.db
        device = db_.get_device(device_id)
        if device is None:
            raise ApiError(404, "Device not found.", code="not_found")
        if device["builtin"]:
            raise ApiError(400, "The built-in web dashboard device cannot be deleted.", code="builtin_device")
        delete_history = request.query_params.get("delete_history", "false").lower() in {"1", "true", "yes"}
        db_.delete_device(device_id, delete_history=delete_history)
        return {"ok": True, "delete_history": delete_history}

    @admin.post("/devices/{device_id}/pair")
    async def admin_pair_device(request: Request, device_id: int) -> dict[str, Any]:
        db_ = request.app.state.db
        device = db_.get_device(device_id)
        if device is None or device["deleted"]:
            raise ApiError(404, "Device not found.", code="not_found")
        if device["builtin"]:
            raise ApiError(400, "The built-in web dashboard device cannot be paired.", code="builtin_device")
        return {"device": _device_payload(device), "pairing": _new_pairing(request, device_id)}

    @admin.get("/transcriptions")
    async def admin_transcriptions(request: Request) -> dict[str, Any]:
        params = request.query_params
        device_id: int | None = None
        if params.get("device_id"):
            try:
                device_id = int(params["device_id"])
            except ValueError:
                raise ApiError(400, "device_id must be an integer.", code="invalid_device_id") from None
        try:
            before = decode_cursor(params.get("before"))
        except ValueError:
            raise ApiError(400, "Invalid pagination cursor.", code="invalid_cursor") from None
        try:
            limit = int(params.get("limit", "50"))
        except ValueError:
            raise ApiError(400, "limit must be an integer.", code="invalid_limit") from None
        limit = max(1, min(limit, 200))
        items, has_more = request.app.state.db.list_transcriptions(
            device_id=device_id, q=params.get("q"), before=before, limit=limit
        )
        next_cursor = None
        if has_more and items:
            next_cursor = encode_cursor(items[-1]["created_at"], items[-1]["id"])
        return {"items": items, "next_cursor": next_cursor, "has_more": has_more}

    @admin.get("/transcriptions/{row_id}")
    async def admin_transcription(request: Request, row_id: int) -> dict[str, Any]:
        item = request.app.state.db.get_transcription(row_id)
        if item is None:
            raise ApiError(404, "Transcription not found.", code="not_found")
        return item

    @admin.delete("/transcriptions/{row_id}")
    async def admin_delete_transcription(request: Request, row_id: int) -> dict[str, Any]:
        if not request.app.state.db.delete_transcription(row_id):
            raise ApiError(404, "Transcription not found.", code="not_found")
        return {"ok": True}

    @admin.get("/stats")
    async def admin_stats(request: Request) -> dict[str, Any]:
        db_ = request.app.state.db
        stats = db_.stats()
        per_device = [
            {
                "id": device["id"],
                "name": device["display_name"],
                "kind": device["kind"],
                "status": device["status"],
                "transcriptions": device["transcription_count"],
                "last_transcription_at": device["last_transcription_at"],
            }
            for device in db_.list_devices()
        ]
        current = request.app.state.config
        active = request.app.state.engine
        model_status = request.app.state.manager.status()
        model_status["model"] = current.model
        model_status["translate_model"] = current.translate_model_name
        return {
            **stats,
            "per_device": per_device,
            "model": current.model,
            "translate_model": current.translate_model_name,
            "english_engine": current.english_engine,
            "parakeet_model": (
                current.parakeet_model if current.english_engine == "parakeet" else None
            ),
            "device": getattr(active, "device", current.device),
            "compute_type": getattr(active, "compute_type", None),
            "models_loaded": bool(active.models_loaded),
            "parakeet_loaded": bool(getattr(active, "parakeet_loaded", False)),
            "model_status": model_status,
            "version": __version__,
        }

    @admin.post("/web-transcribe")
    async def admin_web_transcribe(request: Request) -> dict[str, Any]:
        data, fields = await _read_audio_form(request)
        result, processing_ms = await _transcribe(
            request,
            data,
            prompt=fields.get("prompt"),
            language=_normalize_language(fields.get("language")),
        )
        row = _store(request, request.app.state.web_device_id, result, processing_ms, "web")
        return {
            "transcription": row,
            "text": result.text,
            "detected_language": result.detected_language,
            "language_probability": result.language_probability,
            "task": result.task,
            "duration": result.duration_s,
            "processing_ms": processing_ms,
            "model": result.model or request.app.state.config.model,
        }

    def _settings_payload(request: Request) -> dict[str, Any]:
        store: SettingsStore = request.app.state.settings
        current = request.app.state.config
        payload = store.payload()
        payload["model_status"] = request.app.state.manager.status()
        payload["parakeet_available"] = hardware.moondream_available()
        payload["server"] = {
            "host": current.host,
            "port": current.port,
            "data_dir": str(current.data_dir),
            "version": __version__,
            "preload": current.preload,
        }
        return payload

    @admin.get("/settings")
    async def admin_get_settings(request: Request) -> dict[str, Any]:
        return _settings_payload(request)

    @admin.post("/settings")
    async def admin_update_settings(request: Request) -> dict[str, Any]:
        store: SettingsStore = request.app.state.settings
        manager: EngineManager = request.app.state.manager
        payload = await _json_body(request)
        if manager.busy and set(payload) & ENGINE_RELOAD_FIELDS:
            raise ApiError(
                409,
                "A model is already loading. Wait for it to finish and save again.",
                code="swap_in_progress",
            )
        old = request.app.state.config
        old_engine = store.snapshot().get("english_engine")
        if (
            payload.get("english_engine") == "parakeet"
            and old_engine != "parakeet"
            and not hardware.moondream_available()
        ):
            raise ApiError(
                400,
                "The Parakeet engine is not installed. Run 'uv sync --extra parakeet' first.",
                code="parakeet_unavailable",
            )
        try:
            new_config = store.update(payload)
        except EnvLockedError as exc:
            raise ApiError(409, str(exc), code="env_locked") from None
        except SettingsError as exc:
            raise ApiError(400, str(exc), code="invalid_setting") from None
        request.app.state.config = new_config
        _sync_upload_limit(new_config)
        if new_config.max_concurrency != old.max_concurrency:
            request.app.state.semaphore = asyncio.Semaphore(new_config.max_concurrency)
        engine_changed = request.app.state.manager.status()["state"] == "error" and bool(
            set(payload) & ENGINE_RELOAD_FIELDS
        )
        engine_changed = engine_changed or (
            new_config.model,
            new_config.translate_model_name,
            new_config.english_engine,
            new_config.device,
            new_config.compute_type,
            new_config.cpu_threads,
            new_config.parakeet_model,
        ) != (
            old.model,
            old.translate_model_name,
            old.english_engine,
            old.device,
            old.compute_type,
            old.cpu_threads,
            old.parakeet_model,
        )
        reload_requested = False
        if engine_changed:
            reload_requested = _start_engine_swap(
                request.app, new_config, set(ENGINE_RELOAD_FIELDS)
            )
        # Same shape as GET so the dashboard can re-render from the response directly.
        return {"ok": True, "reload_requested": reload_requested, **_settings_payload(request)}

    @admin.post("/password")
    async def admin_change_password(request: Request) -> dict[str, Any]:
        current = request.app.state.config
        if current.admin_password:
            raise ApiError(
                409,
                "The password is set by WHUB_ADMIN_PASSWORD and cannot be changed here.",
                code="env_locked",
            )
        payload = await _json_body(request)
        stored = request.app.state.db.get_setting("admin_password_hash") or ""
        if not stored or not verify_password(str(payload.get("current_password") or ""), stored):
            raise ApiError(401, "The current password is incorrect.", code="invalid_password")
        try:
            password = validate_new_password(payload.get("new_password"), payload.get("confirm"))
        except ValueError as exc:
            raise ApiError(400, str(exc), code="invalid_password") from None
        request.app.state.db.set_setting("admin_password_hash", hash_password(password))
        return {"ok": True}

    @admin.post("/logout-all")
    async def admin_logout_all(request: Request) -> dict[str, Any]:
        # Rotating the signing key invalidates every existing session cookie.
        request.app.state.session_secret = _rotate_session_secret(data_dir)
        request.session.clear()
        return {"ok": True}

    @admin.get("/export")
    async def admin_export(request: Request) -> Response:
        fmt = (request.query_params.get("format") or "json").strip().lower()
        rows = [
            {
                "created_at": item["created_at"],
                "device": item["device_name"] or "Deleted device",
                "detected_language": item["detected_language"],
                "task": item["task"],
                "text": item["text"],
            }
            for item in request.app.state.db.all_transcriptions()
        ]
        if fmt == "csv":
            buffer = io.StringIO()
            writer = csv.DictWriter(
                buffer, fieldnames=["created_at", "device", "detected_language", "task", "text"]
            )
            writer.writeheader()
            # Spreadsheets evaluate cells starting with = + - @ as formulas; any paired device
            # can put arbitrary text in the history, so neutralize them.
            writer.writerows(
                {
                    key: ("'" + value if isinstance(value, str) and value[:1] in "=+-@\t\r" and value else value)
                    for key, value in row.items()
                }
                for row in rows
            )
            return Response(
                "\ufeff" + buffer.getvalue(),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="whisper-hub-history.csv"'},
            )
        if fmt != "json":
            raise ApiError(400, "Export format must be json or csv.", code="invalid_format")
        return Response(
            json.dumps(rows, ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="whisper-hub-history.json"'},
        )

    @admin.delete("/history")
    async def admin_delete_history(request: Request) -> dict[str, Any]:
        if (request.query_params.get("confirm") or "") != "DELETE":
            raise ApiError(
                400,
                "Deleting all history requires confirm=DELETE.",
                code="confirmation_required",
            )
        deleted = request.app.state.db.clear_transcriptions()
        return {"ok": True, "deleted": deleted}

    @admin.get("/model-status")
    async def admin_model_status(request: Request) -> dict[str, Any]:
        status = request.app.state.manager.status()
        status["model"] = request.app.state.config.model
        status["translate_model"] = request.app.state.config.translate_model_name
        return status

    @admin.get("/setup")
    async def admin_setup(request: Request) -> dict[str, Any]:
        current = request.app.state.config
        return guides_for_setup(_base_url(request), current.model, current.https_url)

    app.include_router(admin)

    # ---------------------------------------------------------------- dashboard SPA

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "index.html",
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/setup", include_in_schema=False)
    async def setup_page() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "index.html",
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon() -> FileResponse:
        return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return app


def run(config: Config | None = None) -> None:
    config = config or Config.from_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = create_app(config)
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="info",
        access_log=False,
    )
