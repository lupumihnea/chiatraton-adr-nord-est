"""Outbound ports and transport-neutral AI values."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID

from app.models.domain import (
    AIOutcome,
    Criterion,
    Document,
    DocumentQuestionAnswer,
    Report,
    SourceAnchor,
)


class AIResponseValidationError(RuntimeError):
    """Raised when an adapter result cannot satisfy the public AI contract."""


@dataclass(frozen=True, slots=True)
class AIInputDocument:
    metadata: Document
    content_handle: str


@dataclass(frozen=True, slots=True)
class CriterionProposalCandidate:
    client_reference: str
    code: str
    description: str
    deadline: date | None
    source_anchors: tuple[SourceAnchor, ...]


@dataclass(frozen=True, slots=True)
class CriterionExtractionRequest:
    job_id: UUID
    project_id: UUID
    documents: tuple[AIInputDocument, ...]
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ValidationCandidate:
    criterion_id: UUID
    criterion_version: int
    outcome: AIOutcome
    rationale: str
    source_anchors: tuple[SourceAnchor, ...]


@dataclass(frozen=True, slots=True)
class ReportAnalysisRequest:
    job_id: UUID
    project_id: UUID
    report: Report
    criteria: tuple[Criterion, ...]
    project_documents: tuple[AIInputDocument, ...]
    previous_reports: tuple[Report, ...]
    allowed_documents: tuple[AIInputDocument, ...]
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class DocumentQuestionRequest:
    project_id: UUID
    question: str
    documents: tuple[AIInputDocument, ...]
    idempotency_key: str


class CriterionExtractor(Protocol):
    async def extract(
        self, request: CriterionExtractionRequest
    ) -> list[CriterionProposalCandidate]: ...


class ReportAnalyzer(Protocol):
    async def analyze(self, request: ReportAnalysisRequest) -> list[ValidationCandidate]: ...


class DocumentQuestionAnswerer(Protocol):
    async def answer(self, request: DocumentQuestionRequest) -> DocumentQuestionAnswer: ...


class DocumentStorage(Protocol):
    async def put(self, document_id: UUID, content: bytes) -> str: ...
    async def handle_for(self, document_id: UUID) -> str | None: ...
    async def get(self, content_handle: str) -> bytes | None: ...
    async def delete(self, content_handle: str) -> None: ...


JobWork = Callable[[], Awaitable[None]]


class JobRunner(Protocol):
    def enqueue(self, job_id: UUID, work: JobWork) -> None: ...
    async def close(self) -> None: ...
