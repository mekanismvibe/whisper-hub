"""Errors and the OpenAI-compatible error envelope."""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """An error rendered as ``{"error": {"message", "type", "code"}}``."""

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        type_: str = "invalid_request_error",
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.type = type_
        self.code = code
        self.headers = headers or {}

    def body(self) -> dict[str, Any]:
        return {"error": {"message": self.message, "type": self.type, "code": self.code}}


class PayloadTooLarge(Exception):
    """Raised by the body-limit middleware when a request exceeds the upload cap."""


class DecodeError(Exception):
    """The uploaded audio could not be decoded."""


class EngineBusyError(Exception):
    """The inference engine is not available."""
