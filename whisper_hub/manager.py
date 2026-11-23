"""Background model loading with an atomic engine swap.

Requests keep using the old engine while a new one downloads and loads. Only
a fully loaded replacement is published; a failure leaves the old engine in
place and records an error for the UI.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

READY = "ready"
IDLE = "idle"
DOWNLOADING = "downloading"
LOADING = "loading"
ERROR = "error"


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for item in path.rglob("*"):
            try:
                if item.is_file():
                    total += item.stat().st_size
            except OSError:
                continue
    except OSError:
        return total
    return total


def default_cache_dir() -> Path:
    try:
        from huggingface_hub import constants

        return Path(constants.HF_HUB_CACHE)  # honors HF_HUB_CACHE, HF_HOME and XDG_CACHE_HOME
    except Exception:  # pragma: no cover - huggingface_hub ships with faster-whisper
        return Path.home() / ".cache" / "huggingface" / "hub"


class EngineManager:
    def __init__(
        self,
        engine: Any,
        *,
        cache_dir: Path | None = None,
        on_swap: Callable[[Any], None] | None = None,
    ) -> None:
        self._engine = engine
        self._on_swap = on_swap
        self._cache_dir = cache_dir or default_cache_dir()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._status: dict[str, Any] = {
            "state": READY if engine.models_loaded else IDLE,
            "message": "",
            "model": getattr(engine, "model_name", ""),
            "progress": None,
            "updated_at": time.time(),
        }

    @property
    def engine(self) -> Any:
        return self._engine

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def status(self) -> dict[str, Any]:
        with self._lock:
            status = dict(self._status)
        status["busy"] = self.busy
        loaded = bool(self._engine.models_loaded)
        status["models_loaded"] = loaded
        # Lazy loads and idle unloads happen outside the manager; reflect them here.
        if not status["busy"]:
            if loaded and status["state"] in (IDLE, ERROR) and not status.get("swap_failed"):
                status["state"], status["message"] = READY, ""
            elif not loaded and status["state"] == READY:
                status["state"] = IDLE
        status.pop("swap_failed", None)
        status["device"] = getattr(self._engine, "device", None)
        status["compute_type"] = getattr(self._engine, "compute_type", None)
        status["loaded_models"] = list(getattr(self._engine, "loaded_models", []) or [])
        status["non_english"] = bool(
            getattr(getattr(self._engine, "config", None), "non_english", False)
        )
        return status

    def mark_ready(self) -> None:
        with self._lock:
            self._status = {
                "state": READY,
                "message": "",
                "model": getattr(self._engine, "model_name", "") or self._status.get("model", ""),
                "progress": None,
                "updated_at": time.time(),
            }

    def set_error(self, message: str) -> None:
        with self._lock:
            self._status = {
                "state": ERROR,
                "message": message,
                "model": getattr(self._engine, "model_name", ""),
                "progress": None,
                "updated_at": time.time(),
            }

    def request_swap(
        self,
        factory: Callable[[], Any],
        *,
        model: str,
        expected_bytes: int | None = None,
    ) -> bool:
        """Start a background load; returns False when one is already running."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._status = {
                "state": DOWNLOADING if expected_bytes else LOADING,
                "message": "",
                "model": model,
                "progress": 0 if expected_bytes else None,
                "updated_at": time.time(),
            }
            self._thread = threading.Thread(
                target=self._run,
                args=(factory, expected_bytes),
                name="whisper-hub-model-swap",
                daemon=True,
            )
            self._thread.start()
            return True

    def _run(self, factory: Callable[[], Any], expected_bytes: int | None) -> None:
        stop = threading.Event()
        monitor = None
        if expected_bytes:
            monitor = threading.Thread(
                target=self._monitor, args=(expected_bytes, stop), name="whisper-hub-model-progress", daemon=True
            )
            monitor.start()
        started = time.monotonic()
        engine = None
        try:
            engine = factory()
            engine.load()
        except Exception as exc:
            logger.exception("model swap failed")
            with self._lock:
                self._status = {
                    "state": ERROR,
                    "message": f"{type(exc).__name__}: {exc}"[:500],
                    "model": self._status.get("model", ""),
                    "progress": None,
                    "updated_at": time.time(),
                    # The old engine still serves, but the UI must keep showing the failure.
                    "swap_failed": True,
                }
        else:
            with self._lock:
                previous = self._engine
                self._engine = engine
                if self._on_swap is not None:
                    self._on_swap(engine)
                self._status = {
                    "state": READY,
                    "message": "",
                    "model": getattr(engine, "model_name", "") or self._status.get("model", ""),
                    "progress": 100,
                    "updated_at": time.time(),
                }
            logger.info("model swap ready in %.1fs", time.monotonic() - started)
            # Free the superseded engine's models (GPU memory, Photon clients) once the
            # requests still using it have finished.
            if previous is not engine:
                retire = getattr(previous, "retire", None) or getattr(previous, "unload", None)
                if callable(retire):
                    try:
                        retire()
                    except Exception:
                        logger.exception("releasing the previous engine failed")
        finally:
            stop.set()
            if monitor is not None:
                monitor.join(timeout=1)

    def _monitor(self, expected_bytes: int, stop: threading.Event) -> None:
        # Measure growth since the download started, not the whole (shared) HF cache.
        baseline = _dir_size(self._cache_dir)
        while not stop.wait(2.0):
            size = max(0, _dir_size(self._cache_dir) - baseline)
            progress = min(99, int(size / expected_bytes * 100)) if expected_bytes else None
            with self._lock:
                if self._status.get("state") not in {DOWNLOADING, LOADING}:
                    return
                self._status["progress"] = progress
                if progress is not None and progress >= 99:
                    self._status["state"] = LOADING

    def wait(self, timeout: float | None = None) -> bool:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
            return not thread.is_alive()
        return True
