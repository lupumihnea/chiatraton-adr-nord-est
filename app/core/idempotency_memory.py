"""Bounded process-local idempotency adapter for development and tests only."""

import asyncio
from dataclasses import dataclass
from time import monotonic

from app.services.idempotency import (
    IdempotencyDecision,
    IdempotencyDisposition,
    IdempotencyScope,
    IdempotencyStoreCapacityError,
    StoredHTTPResponse,
)


@dataclass(slots=True)
class _Entry:
    fingerprint: str
    ready: asyncio.Event
    created_at: float
    expires_at: float
    response: StoredHTTPResponse | None = None


class InMemoryIdempotencyStore:
    """Single-process adapter with atomic reservation, TTL and a hard entry cap.

    This implementation intentionally does not provide cross-process durability.
    Production must inject a durable adapter implementing ``IdempotencyStore``.
    """

    def __init__(self, *, ttl_seconds: int, max_entries: int) -> None:
        if ttl_seconds <= 0 or max_entries <= 0:
            raise ValueError("ttl_seconds and max_entries must be positive")
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._entries: dict[IdempotencyScope, _Entry] = {}
        self._lock = asyncio.Lock()

    def _prune_expired_locked(self, now: float) -> None:
        expired = [
            scope
            for scope, entry in self._entries.items()
            if entry.response is not None and entry.expires_at <= now
        ]
        for scope in expired:
            del self._entries[scope]

    def _make_room_locked(self) -> None:
        if len(self._entries) < self._max_entries:
            return
        completed = [
            (entry.created_at, scope)
            for scope, entry in self._entries.items()
            if entry.response is not None
        ]
        if not completed:
            raise IdempotencyStoreCapacityError("idempotency store capacity reached")
        _, oldest_scope = min(completed, key=lambda item: item[0])
        del self._entries[oldest_scope]

    async def begin(self, scope: IdempotencyScope, fingerprint: str) -> IdempotencyDecision:
        while True:
            async with self._lock:
                now = monotonic()
                self._prune_expired_locked(now)
                entry = self._entries.get(scope)
                if entry is None:
                    self._make_room_locked()
                    self._entries[scope] = _Entry(
                        fingerprint=fingerprint,
                        ready=asyncio.Event(),
                        created_at=now,
                        expires_at=now + self._ttl_seconds,
                    )
                    return IdempotencyDecision(IdempotencyDisposition.PROCEED)
                if entry.fingerprint != fingerprint:
                    return IdempotencyDecision(IdempotencyDisposition.CONFLICT)
                if entry.response is not None:
                    return IdempotencyDecision(IdempotencyDisposition.REPLAY, entry.response)
                waiter = entry.ready
            await waiter.wait()

    async def complete(
        self,
        scope: IdempotencyScope,
        fingerprint: str,
        response: StoredHTTPResponse,
    ) -> None:
        async with self._lock:
            entry = self._entries.get(scope)
            if entry is None or entry.fingerprint != fingerprint:
                return
            entry.response = response
            entry.expires_at = monotonic() + self._ttl_seconds
            entry.ready.set()

    async def abort(self, scope: IdempotencyScope, fingerprint: str) -> None:
        async with self._lock:
            entry = self._entries.get(scope)
            if entry is None or entry.fingerprint != fingerprint:
                return
            del self._entries[scope]
            entry.ready.set()
