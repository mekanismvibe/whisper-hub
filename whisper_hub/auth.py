"""Device key generation/verification, request auth dependencies, login backoff."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from typing import Any

from fastapi import Request

from .errors import ApiError

DEVICE_KEY_PREFIX = "whk_"
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_LEN = 32
PASSWORD_MIN_LENGTH = 8


def generate_device_key() -> str:
    return DEVICE_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_device_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def display_prefix(key: str) -> str:
    """Eight characters, enough to tell keys apart in the dashboard."""
    return key[:8]


def extract_device_key(request: Request) -> str | None:
    authorization = request.headers.get("authorization")
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            return value.strip()
    header_key = request.headers.get("x-api-key")
    if header_key and header_key.strip():
        return header_key.strip()
    return None


async def require_device(request: Request) -> dict[str, Any]:
    key = extract_device_key(request)
    if not key:
        raise ApiError(
            401,
            "Missing API key. Send 'Authorization: Bearer whk_...' or 'X-API-Key: whk_...'.",
            type_="authentication_error",
            code="invalid_api_key",
        )
    db = request.app.state.db
    device = db.get_device_by_key_hash(hash_device_key(key))
    if device is None:
        raise ApiError(
            401,
            "Invalid, revoked or deleted API key.",
            type_="authentication_error",
            code="invalid_api_key",
        )
    client = request.client
    ip = client.host if client else None
    agent = request.headers.get("user-agent")
    # last-seen is display-only: one DB write per device per minute (or when the
    # address/client changes) instead of a synchronous commit on every request.
    seen: dict[int, tuple[float, Any, Any]] = request.app.state.device_seen
    previous = seen.get(device["id"])
    now = time.monotonic()
    if previous is None or now - previous[0] > 60 or previous[1:] != (ip, agent):
        seen[device["id"]] = (now, ip, agent)
        db.touch_device(device["id"], ip, agent)
    return device


async def require_admin(request: Request) -> None:
    if getattr(request.app.state, "setup_required", False):
        raise ApiError(
            409,
            "This instance is in first-run setup. Open the setup page with the token from the server log.",
            type_="authentication_error",
            code="setup_required",
        )
    session = getattr(request, "session", None) or {}
    if session.get("admin") is not True:
        raise ApiError(401, "Admin login required.", type_="authentication_error", code="unauthorized")


class LoginLimiter:
    """In-memory exponential backoff keyed by client address."""

    def __init__(self, *, threshold: int = 5, base_seconds: float = 30.0, max_seconds: float = 900.0) -> None:
        self.threshold = threshold
        self.base_seconds = base_seconds
        self.max_seconds = max_seconds
        self._failures: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> int:
        with self._lock:
            _, locked_until = self._failures.get(key, (0, 0.0))
            remaining = locked_until - time.monotonic()
            return max(0, int(remaining) + (1 if remaining > 0 else 0))

    def check(self, key: str) -> None:
        remaining = self.retry_after(key)
        if remaining > 0:
            raise ApiError(
                429,
                f"Too many failed login attempts. Try again in {remaining} seconds.",
                code="rate_limited",
                headers={"Retry-After": str(remaining)},
            )

    def record_failure(self, key: str) -> None:
        with self._lock:
            if len(self._failures) > 10_000:
                # Forget sources whose lockout ended long ago so the map cannot grow forever.
                now = time.monotonic()
                self._failures = {
                    k: v for k, v in self._failures.items() if v[1] > now - self.max_seconds
                }
            failures, _ = self._failures.get(key, (0, 0.0))
            failures += 1
            locked_until = 0.0
            if failures >= self.threshold:
                delay = min(self.max_seconds, self.base_seconds * (2 ** (failures - self.threshold)))
                locked_until = time.monotonic() + delay
            self._failures[key] = (failures, locked_until)

    def record_success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


def constant_time_equals(candidate: str, expected: str) -> bool:
    # surrogatepass: arbitrary client strings (lone surrogates, non-ASCII) must not raise.
    return hmac.compare_digest(
        candidate.encode("utf-8", "surrogatepass"), expected.encode("utf-8", "surrogatepass")
    )


def hash_password(password: str) -> str:
    """Scrypt hash in a self-describing format: ``scrypt$n$r$p$salt$hash``."""
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8", "surrogatepass"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_LEN,
    )
    return "scrypt${}${}${}${}${}".format(
        SCRYPT_N,
        SCRYPT_R,
        SCRYPT_P,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(derived).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, hash_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
        derived = hashlib.scrypt(
            password.encode("utf-8", "surrogatepass"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived, expected)


def validate_new_password(password: Any, confirm: Any) -> str:
    if not isinstance(password, str) or not isinstance(confirm, str):
        raise ValueError("Password and confirmation are required.")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Use at least {PASSWORD_MIN_LENGTH} characters.")
    if password != confirm:
        raise ValueError("The passwords do not match.")
    return password
