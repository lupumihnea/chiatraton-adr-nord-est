"""Development-only document-content storage adapter."""

from __future__ import annotations

import asyncio
from uuid import UUID


class InMemoryDocumentStorage:
    """Keeps file bytes outside document metadata and never logs their content."""

    def __init__(self) -> None:
        self._content: dict[str, bytes] = {}
        self._handles: dict[UUID, str] = {}
        self._lock = asyncio.Lock()

    async def put(self, document_id: UUID, content: bytes) -> str:
        handle = f"memory://documents/{document_id}"
        async with self._lock:
            self._content[handle] = bytes(content)
            self._handles[document_id] = handle
        return handle

    async def handle_for(self, document_id: UUID) -> str | None:
        async with self._lock:
            return self._handles.get(document_id)

    async def get(self, content_handle: str) -> bytes | None:
        async with self._lock:
            value = self._content.get(content_handle)
            return bytes(value) if value is not None else None

    async def delete(self, content_handle: str) -> None:
        async with self._lock:
            self._content.pop(content_handle, None)
            for document_id, handle in tuple(self._handles.items()):
                if handle == content_handle:
                    self._handles.pop(document_id, None)
