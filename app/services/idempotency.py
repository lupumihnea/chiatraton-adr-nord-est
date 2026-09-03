"""Port and transport-neutral values for idempotent HTTP operations."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


@dataclass(frozen=True, slots=True)
class IdempotencyScope:
    """A key namespace that deliberately excludes credentials and tokens."""

    user_id: str
    method: str
    resource: str
    key: str


@dataclass(frozen=True, slots=True)
class StoredHTTPResponse:
    status_code: int
    body: bytes
    headers: tuple[tuple[str, str], ...]


class IdempotencyDisposition(StrEnum):
    PROCEED = "proceed"
    REPLAY = "replay"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class IdempotencyDecision:
    disposition: IdempotencyDisposition
    response: StoredHTTPResponse | None = None


class IdempotencyStoreCapacityError(RuntimeError):
    """Raised when all bounded store slots are occupied by active requests."""


class IdempotencyStore(Protocol):
    """Adapter port; a durable DB implementation can replace the memory adapter."""

    async def begin(self, scope: IdempotencyScope, fingerprint: str) -> IdempotencyDecision: ...

    async def complete(
        self,
        scope: IdempotencyScope,
        fingerprint: str,
        response: StoredHTTPResponse,
    ) -> None: ...

    async def abort(self, scope: IdempotencyScope, fingerprint: str) -> None: ...
