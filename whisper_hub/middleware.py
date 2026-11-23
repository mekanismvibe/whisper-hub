"""ASGI body-size guard: reject oversized uploads before multipart parsing."""

from __future__ import annotations

import json
from collections.abc import Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .errors import PayloadTooLarge

OVERHEAD_ALLOWANCE = 1024 * 1024  # multipart headers and boundaries
JSON_BODY_LIMIT = 1024 * 1024  # everything that is not an audio upload
UPLOAD_PATHS = ("/v1/audio/", "/api/admin/web-transcribe")


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, get_limits: Callable[[], tuple[int, int]]) -> None:
        self.app = app
        self.get_limits = get_limits

    def _limits(self) -> tuple[int, int]:
        max_bytes, limit_mb = self.get_limits()
        return max_bytes + OVERHEAD_ALLOWANCE, limit_mb

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        threshold, limit_mb = self._limits()
        if not scope.get("path", "").startswith(UPLOAD_PATHS):
            threshold = min(threshold, JSON_BODY_LIMIT)
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope["headers"]}
        declared = headers.get("content-length")
        if declared:
            try:
                if int(declared) > threshold:
                    await self._reject(send, limit_mb)
                    return
            except ValueError:
                pass

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > threshold:
                    raise PayloadTooLarge()
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except PayloadTooLarge:
            if response_started:
                raise
            await self._reject(send, limit_mb)

    async def _reject(self, send: Send, limit_mb: int) -> None:
        body = json.dumps(
            {
                "error": {
                    "message": f"Upload exceeds the {limit_mb} MB limit.",
                    "type": "invalid_request_error",
                    "code": "payload_too_large",
                }
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class RotatingSessionMiddleware:
    """Signed cookie sessions whose signing key can be rotated at runtime.

    Starlette's SessionMiddleware fixes its key at construction, which makes
    "sign out all sessions" impossible without a restart. The key here is a
    callable, so rotating the secret instantly invalidates every old cookie.
    """

    def __init__(
        self,
        app: ASGIApp,
        get_secret: Callable[[], str],
        session_cookie: str = "session",
        max_age: int | None = 14 * 24 * 60 * 60,
        same_site: str = "lax",
        https_only: bool = False,
    ) -> None:
        self.app = app
        self.get_secret = get_secret
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.security_flags = "httponly; samesite=" + same_site
        if https_only:
            self.security_flags += "; secure"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        import json
        from base64 import b64decode, b64encode

        import itsdangerous
        from itsdangerous.exc import BadSignature
        from starlette.datastructures import MutableHeaders
        from starlette.requests import HTTPConnection

        from starlette.middleware.sessions import Session

        connection = HTTPConnection(scope)
        forwarded = (connection.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
        # Secure when the browser reached us over HTTPS (directly or via a reverse proxy),
        # so plain-HTTP LAN logins keep working.
        flags = self.security_flags
        if "secure" not in flags and (scope.get("scheme") == "https" or forwarded == "https"):
            flags += "; secure"
        initial_session_was_empty = True
        signer = itsdangerous.TimestampSigner(str(self.get_secret()))
        if self.session_cookie in connection.cookies:
            data = connection.cookies[self.session_cookie].encode("utf-8")
            try:
                data = signer.unsign(data, max_age=self.max_age)
                scope["session"] = Session(json.loads(b64decode(data)))
                initial_session_was_empty = False
            except BadSignature:
                scope["session"] = Session()
        else:
            scope["session"] = Session()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                session: Session = scope["session"]
                message.setdefault("headers", [])
                headers = MutableHeaders(scope=message)
                if session.accessed:
                    headers.add_vary_header("Cookie")
                if session.modified and session:
                    data = b64encode(json.dumps(session).encode("utf-8"))
                    # Sign with the current key: the handler may just have rotated it.
                    data = itsdangerous.TimestampSigner(str(self.get_secret())).sign(data)
                    header_value = (
                        f"{self.session_cookie}={data.decode('utf-8')}; path=/; "
                        f"Max-Age={self.max_age}; {flags}"
                    )
                    headers.append("set-cookie", header_value)
                elif session.modified and not initial_session_was_empty:
                    header_value = (
                        f"{self.session_cookie}=null; path=/; "
                        f"expires=Thu, 01 Jan 1970 00:00:00 GMT; {flags}"
                    )
                    headers.append("set-cookie", header_value)
            await send(message)

        await self.app(scope, receive, send_wrapper)
