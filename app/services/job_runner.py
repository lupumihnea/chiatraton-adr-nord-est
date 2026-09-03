"""Process-local asynchronous job runner for test and development/demo."""

from __future__ import annotations

import asyncio
from uuid import UUID

from app.services.ports import JobWork


class LocalJobRunner:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()
        self._job_tasks: dict[UUID, asyncio.Task[None]] = {}

    def enqueue(self, job_id: UUID, work: JobWork) -> None:
        if job_id in self._job_tasks:
            return

        async def execute() -> None:
            # Important for the in-process demo runner: let the request which
            # created the job finish and send its HTTP 202 response before the
            # CPU-heavy parser/embedding work begins. A zero-length yield can
            # still schedule the job before ASGI has flushed the response. A
            # short delay is enough and avoids adding visible latency to every job.
            await asyncio.sleep(0.05)
            await work()

        task = asyncio.create_task(execute(), name=f"chiatraton-job-{job_id}")
        self._tasks.add(task)
        self._job_tasks[job_id] = task
        task.add_done_callback(self._finished)

    def _finished(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        for job_id, current in tuple(self._job_tasks.items()):
            if current is task:
                self._job_tasks.pop(job_id, None)
        if not task.cancelled():
            task.exception()

    async def close(self) -> None:
        pending: tuple[asyncio.Task[None], ...] = tuple(self._tasks)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
