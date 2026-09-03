"""Opaque, deterministic, process-local cursor codec."""

from __future__ import annotations

import base64
import hashlib
import hmac

from app.core.exceptions import ProblemException


class CursorCodec:
    """Maps signed opaque tokens to positions without encoding the offset in the token."""

    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")
        self._positions: dict[str, tuple[str, int]] = {}

    def encode(self, scope: str, offset: int) -> str:
        message = f"v1\0{scope}\0{offset}".encode()
        digest = hmac.new(self._secret, message, hashlib.sha256).digest()
        token = base64.urlsafe_b64encode(digest).decode().rstrip("=")
        self._positions[token] = (scope, offset)
        return token

    def decode(self, token: str | None, scope: str) -> int:
        if token is None:
            return 0
        position = self._positions.get(token)
        if position is None or position[0] != scope:
            raise ProblemException(
                status=422,
                code="validation_error",
                title="Request validation failed",
                detail="The pagination cursor is invalid or expired.",
            )
        return position[1]
