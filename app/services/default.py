"""Concrete contract-first application service."""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID, uuid4

from fastapi import UploadFile
from pydantic import ValidationError

from app.core.cursors import CursorCodec
from app.core.exceptions import ProblemException
from app.core.idempotency import IdempotencyContext
from app.core.security import CurrentUser
from app.models.domain import (
    AIOutcome,
    AnalysisJob,
    AnalysisJobCreate,
    AnalysisJobError,
    AnalysisJobKind,
    AnalysisJobStatus,
    Criterion,
    CriterionCreate,
    CriterionExtractionJobCreate,
    CriterionProposal,
    CriterionProposalReviewAction,
    CriterionProposalReviewBatch,
    CriterionProposalReviewBatchResult,
    CriterionProposalReviewRecord,
    CriterionValidation,
    Document,
    DocumentMediaType,
    PaginatedCriteria,
    PaginatedCriterionProposals,
    PaginatedProjects,
    PaginatedReports,
    PaginatedValidations,
    Project,
    ProjectCreate,
    Report,
    ReportCreate,
    ReportStatus,
    SourceAnchor,
    UserDecision,
    UserDecisionCreate,
    ValidationStatus,
)
from app.repositories.interfaces import UnitOfWork, UnitOfWorkFactory
from app.services.ports import (
    AIInputDocument,
    AIResponseValidationError,
    CriterionExtractionRequest,
    CriterionExtractor,
    DocumentStorage,
    JobRunner,
    ReportAnalysisRequest,
    ReportAnalyzer,
)

MAX_DOCUMENT_BYTES = 52_428_800
T = TypeVar("T")


def _now() -> datetime:
    return datetime.now(UTC)


def _problem(status: int, code: str, title: str, detail: str) -> ProblemException:
    return ProblemException(status=status, code=code, title=title, detail=detail)


def _not_found(resource: str) -> ProblemException:
    return _problem(
        404, "resource_not_found", "Resource not found", f"The {resource} does not exist."
    )


class DefaultApplicationService:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        document_storage: DocumentStorage,
        criterion_extractor: CriterionExtractor,
        report_analyzer: ReportAnalyzer,
        job_runner: JobRunner,
        cursor_codec: CursorCodec,
        extra_shutdown_hooks: Sequence[Callable[[], Awaitable[None]]] = (),
    ) -> None:
        self._uow_factory = unit_of_work_factory
        self._storage = document_storage
        self._criterion_extractor = criterion_extractor
        self._report_analyzer = report_analyzer
        self._job_runner = job_runner
        self._cursors = cursor_codec
        self._extra_shutdown_hooks = tuple(extra_shutdown_hooks)

    async def close(self) -> None:
        await self._job_runner.close()
        for hook in self._extra_shutdown_hooks:
            await hook()

    async def _owned_project(self, uow: UnitOfWork, project_id: UUID, user: CurrentUser) -> Project:
        project = await uow.projects.get(project_id)
        owner = await uow.projects.owner(project_id)
        if project is None or owner != user.subject:
            raise _not_found("project")
        return project

    async def _owned_job(self, uow: UnitOfWork, job_id: UUID, user: CurrentUser) -> AnalysisJob:
        job = await uow.jobs.get(job_id)
        if job is None:
            raise _not_found("analysis job")
        await self._owned_project(uow, job.project_id, user)
        return job

    async def _validate_anchors(
        self,
        uow: UnitOfWork,
        project_id: UUID,
        anchors: Sequence[SourceAnchor],
        *,
        allowed_document_ids: set[UUID] | None = None,
    ) -> None:
        for anchor in anchors:
            document = await uow.documents.get(anchor.document_id)
            if document is None or document.project_id != project_id:
                raise _problem(
                    422,
                    "validation_error",
                    "Request validation failed",
                    "Every SourceAnchor must reference a document from the same project.",
                )
            if allowed_document_ids is not None and anchor.document_id not in allowed_document_ids:
                raise _problem(
                    422,
                    "validation_error",
                    "Request validation failed",
                    "The SourceAnchor document was not selected for this analysis job.",
                )
            if document.page_count is not None and anchor.page_number > document.page_count:
                raise _problem(
                    422,
                    "validation_error",
                    "Request validation failed",
                    "The SourceAnchor page exceeds the known document page count.",
                )

    def _page(
        self, items: Sequence[T], limit: int, cursor: str | None, scope: str
    ) -> tuple[list[T], str | None]:
        start = self._cursors.decode(cursor, scope)
        if start > len(items):
            raise _problem(
                422,
                "validation_error",
                "Request validation failed",
                "The pagination cursor is no longer valid for this collection.",
            )
        page = list(items[start : start + limit])
        end = start + len(page)
        next_cursor = self._cursors.encode(scope, end) if end < len(items) else None
        return page, next_cursor

    async def create_project(
        self, data: ProjectCreate, user: CurrentUser, idempotency: IdempotencyContext
    ) -> Project:
        del idempotency
        timestamp = _now()
        project = Project(
            id=uuid4(),
            name=data.name,
            smis_code=data.smis_code,
            funding_call_id=data.funding_call_id,
            beneficiary_name=data.beneficiary_name,
            created_at=timestamp,
            updated_at=timestamp,
        )
        async with self._uow_factory() as uow:
            await uow.projects.add(project, user.subject)
            await uow.commit()
        return project

    async def list_projects(
        self, limit: int, cursor: str | None, user: CurrentUser
    ) -> PaginatedProjects:
        async with self._uow_factory() as uow:
            items = await uow.projects.list_for_owner(user.subject)
        items.sort(key=lambda item: (item.created_at, str(item.id)))
        page, next_cursor = self._page(items, limit, cursor, f"projects:{user.subject}")
        return PaginatedProjects(items=page, next_cursor=next_cursor)

    async def upload_project_document(
        self,
        project_id: UUID,
        file: UploadFile,
        display_name: str | None,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> Document:
        del idempotency
        media_type = (file.content_type or "").partition(";")[0].strip().lower()
        try:
            parsed_media_type = DocumentMediaType(media_type)
        except ValueError as exc:
            raise _problem(
                415,
                "unsupported_media_type",
                "Unsupported media type",
                "The uploaded document type is not supported.",
            ) from exc

        content = await file.read(MAX_DOCUMENT_BYTES + 1)
        if len(content) > MAX_DOCUMENT_BYTES:
            raise _problem(
                413,
                "payload_too_large",
                "Payload too large",
                "The uploaded document exceeds 50 MiB.",
            )
        if not content:
            raise _problem(
                422,
                "validation_error",
                "Request validation failed",
                "The uploaded document must not be empty.",
            )
        original_filename = (file.filename or "").strip()
        if not original_filename or len(original_filename) > 255:
            raise _problem(
                422,
                "validation_error",
                "Request validation failed",
                "The original filename must contain between 1 and 255 characters.",
            )
        effective_name = (display_name or original_filename).strip()
        digest = hashlib.sha256(content).hexdigest()
        document_id = uuid4()
        document = Document(
            id=document_id,
            project_id=project_id,
            display_name=effective_name,
            original_filename=original_filename,
            media_type=parsed_media_type,
            size_bytes=len(content),
            sha256=digest,
            page_count=None,
            created_at=_now(),
        )

        content_handle: str | None = None
        try:
            async with self._uow_factory() as uow:
                await self._owned_project(uow, project_id, user)
                duplicate = await uow.documents.find_by_sha256(project_id, digest)
                if duplicate is not None:
                    raise _problem(
                        409,
                        "document_duplicate",
                        "Duplicate document",
                        "A document with the same content already exists in this project.",
                    )
                content_handle = await self._storage.put(document_id, content)
                await uow.documents.add(document)
                await uow.commit()
        except Exception:
            if content_handle is not None:
                await self._storage.delete(content_handle)
            raise
        return document

    async def create_project_criterion(
        self,
        project_id: UUID,
        data: CriterionCreate,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> Criterion:
        del idempotency
        timestamp = _now()
        criterion = Criterion(
            id=uuid4(),
            project_id=project_id,
            code=data.code,
            description=data.description,
            deadline=data.deadline,
            source_anchors=data.source_anchors,
            version=1,
            active=True,
            created_at=timestamp,
            updated_at=timestamp,
        )
        async with self._uow_factory() as uow:
            await self._owned_project(uow, project_id, user)
            if await uow.criteria.code_exists(project_id, data.code.strip().casefold()):
                raise _problem(
                    409,
                    "criterion_code_conflict",
                    "Criterion code conflict",
                    "The criterion code is already used in this project.",
                )
            await self._validate_anchors(uow, project_id, data.source_anchors)
            await uow.criteria.add(criterion)
            await uow.commit()
        return criterion

    async def list_project_criteria(
        self, project_id: UUID, limit: int, cursor: str | None, user: CurrentUser
    ) -> PaginatedCriteria:
        async with self._uow_factory() as uow:
            await self._owned_project(uow, project_id, user)
            items = await uow.criteria.list_for_project(project_id)
        items.sort(key=lambda item: (item.created_at, str(item.id)))
        scope = f"criteria:{user.subject}:{project_id}"
        page, next_cursor = self._page(items, limit, cursor, scope)
        return PaginatedCriteria(items=page, next_cursor=next_cursor)

    async def create_criterion_extraction_job(
        self,
        project_id: UUID,
        data: CriterionExtractionJobCreate,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> AnalysisJob:
        job = AnalysisJob(
            id=uuid4(),
            project_id=project_id,
            kind=AnalysisJobKind.EXTRACT_CRITERIA,
            report_id=None,
            status=AnalysisJobStatus.QUEUED,
            document_ids=data.document_ids,
            project_document_ids=[],
            previous_report_ids=[],
            criteria_snapshot_version=None,
            proposal_count=None,
            created_at=_now(),
            started_at=None,
            completed_at=None,
            error=None,
        )
        async with self._uow_factory() as uow:
            await self._owned_project(uow, project_id, user)
            for document_id in data.document_ids:
                document = await uow.documents.get(document_id)
                if document is None or document.project_id != project_id:
                    raise _problem(
                        422,
                        "validation_error",
                        "Request validation failed",
                        "Every extraction document must belong to the project.",
                    )
            await uow.jobs.add(job)
            await uow.commit()
        self._job_runner.enqueue(
            job.id,
            lambda: self._run_criterion_extraction(job.id, idempotency.key),
        )
        return job

    async def _run_criterion_extraction(self, job_id: UUID, idempotency_key: str) -> None:
        try:
            async with self._uow_factory() as uow:
                job = await uow.jobs.get(job_id)
                if job is None or job.status != AnalysisJobStatus.QUEUED:
                    return
                running = job.model_copy(
                    update={"status": AnalysisJobStatus.RUNNING, "started_at": _now()}
                )
                await uow.jobs.update(running)
                documents = [await uow.documents.get(item) for item in running.document_ids]
                if any(item is None for item in documents):
                    raise AIResponseValidationError("missing input document")
                await uow.commit()

            extraction_documents: list[AIInputDocument] = []
            for item in documents:
                if item is not None:
                    extraction_documents.append(
                        AIInputDocument(
                            metadata=item,
                            content_handle=await self._required_content_handle(item.id),
                        )
                    )
            request = CriterionExtractionRequest(
                job_id=running.id,
                project_id=running.project_id,
                documents=tuple(extraction_documents),
                idempotency_key=idempotency_key,
            )
            candidates = await self._criterion_extractor.extract(request)
            references = [item.client_reference for item in candidates]
            if len(references) != len(set(references)):
                raise AIResponseValidationError("duplicate clientReference")
            allowed = set(running.document_ids)
            proposals: list[CriterionProposal] = []
            for candidate in candidates:
                if not candidate.source_anchors:
                    raise AIResponseValidationError("proposal without SourceAnchor")
                if any(anchor.document_id not in allowed for anchor in candidate.source_anchors):
                    raise AIResponseValidationError("proposal references an unauthorized document")
                proposals.append(
                    CriterionProposal(
                        id=uuid4(),
                        analysis_job_id=running.id,
                        project_id=running.project_id,
                        revision=1,
                        proposed_code=candidate.code,
                        proposed_description=candidate.description,
                        proposed_deadline=candidate.deadline,
                        source_anchors=list(candidate.source_anchors),
                        review=None,
                        created_at=_now(),
                    )
                )

            async with self._uow_factory() as uow:
                current = await uow.jobs.get(job_id)
                if current is None or current.status != AnalysisJobStatus.RUNNING:
                    return
                await uow.proposals.add_many(proposals)
                await uow.jobs.update(
                    current.model_copy(
                        update={
                            "status": AnalysisJobStatus.SUCCEEDED,
                            "proposal_count": len(proposals),
                            "completed_at": _now(),
                            "error": None,
                        }
                    )
                )
                await uow.commit()
        except (AIResponseValidationError, ValidationError):
            await self._fail_job(job_id, "ai_invalid_response", "The AI response was invalid.")
        except Exception:
            await self._fail_job(job_id, "ai_unavailable", "The AI adapter was unavailable.")

    async def create_project_report(
        self,
        project_id: UUID,
        data: ReportCreate,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> Report:
        del idempotency
        timestamp = _now()
        report = Report(
            id=uuid4(),
            project_id=project_id,
            report_type=data.report_type,
            period_start=data.period_start,
            period_end=data.period_end,
            documents=data.documents,
            external_system=data.external_system,
            external_id=data.external_id,
            external_url=data.external_url,
            external_status=data.external_status,
            status=ReportStatus.CREATED,
            created_at=timestamp,
            updated_at=timestamp,
        )
        async with self._uow_factory() as uow:
            await self._owned_project(uow, project_id, user)
            for association in data.documents:
                document = await uow.documents.get(association.document_id)
                if document is None or document.project_id != project_id:
                    raise _problem(
                        422,
                        "validation_error",
                        "Request validation failed",
                        "Every report document must belong to the report project.",
                    )
            if data.external_system is not None and data.external_id is not None:
                if await uow.reports.external_identity_exists(
                    project_id, data.external_system.value, data.external_id
                ):
                    raise _problem(
                        409,
                        "external_report_conflict",
                        "External report conflict",
                        "The external report identity is already used in this project.",
                    )
            await uow.reports.add(report)
            await uow.commit()
        return report

    async def list_project_reports(
        self, project_id: UUID, limit: int, cursor: str | None, user: CurrentUser
    ) -> PaginatedReports:
        async with self._uow_factory() as uow:
            await self._owned_project(uow, project_id, user)
            items = await uow.reports.list_for_project(project_id)
        items.sort(key=lambda item: (item.created_at, str(item.id)))
        scope = f"reports:{user.subject}:{project_id}"
        page, next_cursor = self._page(items, limit, cursor, scope)
        return PaginatedReports(items=page, next_cursor=next_cursor)

    async def create_report_analysis_job(
        self,
        report_id: UUID,
        data: AnalysisJobCreate,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> AnalysisJob:
        async with self._uow_factory() as uow:
            report = await uow.reports.get(report_id)
            if report is None:
                raise _not_found("report")
            await self._owned_project(uow, report.project_id, user)
            if report.status in {ReportStatus.ANALYSIS_QUEUED, ReportStatus.ANALYSIS_IN_PROGRESS}:
                raise _problem(
                    409,
                    "invalid_report_state",
                    "Invalid report state",
                    "The report already has an active analysis job.",
                )
            for document_id in data.project_document_ids:
                document = await uow.documents.get(document_id)
                if document is None or document.project_id != report.project_id:
                    raise _problem(
                        422,
                        "validation_error",
                        "Request validation failed",
                        "Every selected project document must belong to the report project.",
                    )
            for previous_report_id in data.previous_report_ids:
                previous = await uow.reports.get(previous_report_id)
                if previous is None or previous.project_id != report.project_id:
                    raise _problem(
                        422,
                        "validation_error",
                        "Request validation failed",
                        "Every previous report must belong to the same project.",
                    )
                if previous.id == report.id:
                    raise _problem(
                        422,
                        "validation_error",
                        "Request validation failed",
                        "A report cannot be selected as its own previous report.",
                    )
            snapshot_version, criteria = await uow.criteria.active_snapshot(report.project_id)
            if not criteria:
                raise _problem(
                    409,
                    "no_active_criteria",
                    "No active criteria",
                    "The report project has no active criteria to analyze.",
                )
            job = AnalysisJob(
                id=uuid4(),
                project_id=report.project_id,
                kind=AnalysisJobKind.ANALYZE_REPORT,
                report_id=report.id,
                status=AnalysisJobStatus.QUEUED,
                document_ids=[],
                project_document_ids=data.project_document_ids,
                previous_report_ids=data.previous_report_ids,
                criteria_snapshot_version=snapshot_version,
                proposal_count=None,
                created_at=_now(),
                started_at=None,
                completed_at=None,
                error=None,
            )
            await uow.jobs.add(job)
            await uow.jobs.set_criteria_snapshot(job.id, criteria)
            await uow.reports.update(
                report.model_copy(
                    update={"status": ReportStatus.ANALYSIS_QUEUED, "updated_at": _now()}
                )
            )
            await uow.commit()
        self._job_runner.enqueue(
            job.id,
            lambda: self._run_report_analysis(job.id, idempotency.key),
        )
        return job

    async def _run_report_analysis(self, job_id: UUID, idempotency_key: str) -> None:
        try:
            async with self._uow_factory() as uow:
                job = await uow.jobs.get(job_id)
                if job is None or job.status != AnalysisJobStatus.QUEUED or job.report_id is None:
                    return
                report = await uow.reports.get(job.report_id)
                if report is None:
                    raise AIResponseValidationError("missing report")
                running = job.model_copy(
                    update={"status": AnalysisJobStatus.RUNNING, "started_at": _now()}
                )
                await uow.jobs.update(running)
                await uow.reports.update(
                    report.model_copy(
                        update={"status": ReportStatus.ANALYSIS_IN_PROGRESS, "updated_at": _now()}
                    )
                )
                criteria = await uow.jobs.get_criteria_snapshot(job_id)
                allowed_ids = {item.document_id for item in report.documents}
                allowed_ids.update(running.project_document_ids)
                previous_reports: list[Report] = []
                for previous_id in running.previous_report_ids:
                    previous = await uow.reports.get(previous_id)
                    if previous is None:
                        raise AIResponseValidationError("missing previous report")
                    previous_reports.append(previous)
                    allowed_ids.update(item.document_id for item in previous.documents)
                documents = [await uow.documents.get(item) for item in sorted(allowed_ids, key=str)]
                if any(item is None for item in documents):
                    raise AIResponseValidationError("missing analysis document")
                await uow.commit()

            input_documents: list[AIInputDocument] = []
            project_documents: list[AIInputDocument] = []
            for item in documents:
                if item is None:
                    continue
                input_document = AIInputDocument(
                    metadata=item,
                    content_handle=await self._required_content_handle(item.id),
                )
                input_documents.append(input_document)
                if item.id in running.project_document_ids:
                    project_documents.append(input_document)
            request = ReportAnalysisRequest(
                job_id=running.id,
                project_id=running.project_id,
                report=report,
                criteria=tuple(criteria),
                project_documents=tuple(project_documents),
                previous_reports=tuple(previous_reports),
                allowed_documents=tuple(input_documents),
                idempotency_key=idempotency_key,
            )
            candidates = await self._report_analyzer.analyze(request)
            expected = {(item.id, item.version) for item in criteria}
            actual = {(item.criterion_id, item.criterion_version) for item in candidates}
            if actual != expected or len(candidates) != len(expected):
                raise AIResponseValidationError("criterion coverage mismatch")
            for candidate in candidates:
                if (
                    candidate.outcome != AIOutcome.INSUFFICIENT_EVIDENCE
                    and not candidate.source_anchors
                ):
                    raise AIResponseValidationError("factual outcome without SourceAnchor")
                if any(
                    anchor.document_id not in allowed_ids for anchor in candidate.source_anchors
                ):
                    raise AIResponseValidationError("validation references unauthorized document")

            async with self._uow_factory() as uow:
                current = await uow.jobs.get(job_id)
                if current is None or current.status != AnalysisJobStatus.RUNNING:
                    return
                history = await uow.validations.list_for_report(report.id)
                revisions: dict[UUID, int] = {}
                for item in history:
                    revisions[item.criterion_id] = max(
                        revisions.get(item.criterion_id, 0), item.revision
                    )
                validations = [
                    CriterionValidation(
                        id=uuid4(),
                        report_id=report.id,
                        criterion_id=candidate.criterion_id,
                        criterion_version=candidate.criterion_version,
                        analysis_job_id=current.id,
                        revision=revisions.get(candidate.criterion_id, 0) + 1,
                        status=(
                            ValidationStatus.INSUFFICIENT_EVIDENCE
                            if candidate.outcome == AIOutcome.INSUFFICIENT_EVIDENCE
                            else ValidationStatus.AWAITING_USER_DECISION
                        ),
                        ai_outcome=candidate.outcome,
                        ai_rationale=candidate.rationale,
                        source_anchors=list(candidate.source_anchors),
                        user_decision=None,
                        created_at=_now(),
                    )
                    for candidate in candidates
                ]
                await uow.validations.add_many(validations)
                await uow.jobs.update(
                    current.model_copy(
                        update={
                            "status": AnalysisJobStatus.SUCCEEDED,
                            "completed_at": _now(),
                            "error": None,
                        }
                    )
                )
                current_report = await uow.reports.get(report.id)
                if current_report is not None:
                    await uow.reports.update(
                        current_report.model_copy(
                            update={
                                "status": ReportStatus.AWAITING_USER_DECISION,
                                "updated_at": _now(),
                            }
                        )
                    )
                await uow.commit()
        except (AIResponseValidationError, ValidationError):
            await self._fail_job(job_id, "ai_invalid_response", "The AI response was invalid.")
        except Exception:
            await self._fail_job(job_id, "ai_unavailable", "The AI adapter was unavailable.")

    async def _required_content_handle(self, document_id: UUID) -> str:
        handle = await self._storage.handle_for(document_id)
        if handle is None:
            raise AIResponseValidationError("missing document content")
        return handle

    async def _fail_job(self, job_id: UUID, code: str, message: str) -> None:
        async with self._uow_factory() as uow:
            job = await uow.jobs.get(job_id)
            if job is None or job.status in {
                AnalysisJobStatus.SUCCEEDED,
                AnalysisJobStatus.FAILED,
                AnalysisJobStatus.CANCELLED,
            }:
                return
            await uow.jobs.update(
                job.model_copy(
                    update={
                        "status": AnalysisJobStatus.FAILED,
                        "completed_at": _now(),
                        "error": AnalysisJobError(code=code, message=message),
                    }
                )
            )
            if job.report_id is not None:
                report = await uow.reports.get(job.report_id)
                if report is not None:
                    await uow.reports.update(
                        report.model_copy(
                            update={"status": ReportStatus.ANALYSIS_FAILED, "updated_at": _now()}
                        )
                    )
            await uow.commit()

    async def get_analysis_job(self, job_id: UUID, user: CurrentUser) -> AnalysisJob:
        async with self._uow_factory() as uow:
            return await self._owned_job(uow, job_id, user)

    async def list_criterion_extraction_proposals(
        self, job_id: UUID, limit: int, cursor: str | None, user: CurrentUser
    ) -> PaginatedCriterionProposals:
        async with self._uow_factory() as uow:
            job = await self._owned_job(uow, job_id, user)
            if job.kind != AnalysisJobKind.EXTRACT_CRITERIA:
                raise _problem(
                    409,
                    "invalid_analysis_job_kind",
                    "Invalid analysis job kind",
                    "This job is not a criterion-extraction job.",
                )
            if job.status != AnalysisJobStatus.SUCCEEDED:
                raise _problem(
                    409,
                    "analysis_job_not_succeeded",
                    "Analysis job not succeeded",
                    "Proposals are available only after a successful extraction job.",
                )
            proposals = await uow.proposals.list_for_job(job_id)
            hydrated = [
                item.model_copy(update={"review": await uow.proposals.get_review(item.id)})
                for item in proposals
            ]
        hydrated.sort(key=lambda item: (item.created_at, str(item.id)))
        scope = f"proposals:{user.subject}:{job_id}"
        page, next_cursor = self._page(hydrated, limit, cursor, scope)
        return PaginatedCriterionProposals(items=page, next_cursor=next_cursor)

    async def create_criterion_proposal_reviews(
        self,
        job_id: UUID,
        data: CriterionProposalReviewBatch,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> CriterionProposalReviewBatchResult:
        del idempotency
        async with self._uow_factory() as uow:
            job = await self._owned_job(uow, job_id, user)
            if job.kind != AnalysisJobKind.EXTRACT_CRITERIA:
                raise _problem(
                    409,
                    "invalid_analysis_job_kind",
                    "Invalid analysis job kind",
                    "This job is not a criterion-extraction job.",
                )
            if job.status != AnalysisJobStatus.SUCCEEDED:
                raise _problem(
                    409,
                    "analysis_job_not_succeeded",
                    "Analysis job not succeeded",
                    "Proposals can be reviewed only after successful extraction.",
                )
            selected_documents = set(job.document_ids)
            staged: list[tuple[CriterionProposalReviewRecord, Criterion | None]] = []
            staged_codes: set[str] = set()
            timestamp = _now()

            for review in data.reviews:
                proposal = await uow.proposals.get(review.proposal_id)
                if proposal is None or proposal.analysis_job_id != job_id:
                    raise _not_found("criterion proposal")
                if review.proposal_revision != proposal.revision:
                    raise _problem(
                        409,
                        "stale_proposal_revision",
                        "Stale proposal revision",
                        "The proposal revision has changed.",
                    )
                if await uow.proposals.get_review(proposal.id) is not None:
                    raise _problem(
                        409,
                        "proposal_already_reviewed",
                        "Proposal already reviewed",
                        "The proposal already has a final review.",
                    )

                criterion: Criterion | None = None
                if review.action != CriterionProposalReviewAction.REJECT:
                    if review.action == CriterionProposalReviewAction.ACCEPT:
                        code = proposal.proposed_code
                        description = proposal.proposed_description
                        deadline = proposal.proposed_deadline
                        anchors = proposal.source_anchors
                    else:
                        assert review.correction is not None
                        code = review.correction.code
                        description = review.correction.description
                        deadline = review.correction.deadline
                        anchors = review.correction.source_anchors
                    await self._validate_anchors(
                        uow,
                        job.project_id,
                        anchors,
                        allowed_document_ids=selected_documents,
                    )
                    normalized_code = code.strip().casefold()
                    if normalized_code in staged_codes or await uow.criteria.code_exists(
                        job.project_id, normalized_code
                    ):
                        raise _problem(
                            409,
                            "criterion_code_conflict",
                            "Criterion code conflict",
                            "A reviewed proposal would create a duplicate criterion code.",
                        )
                    staged_codes.add(normalized_code)
                    criterion = Criterion(
                        id=uuid4(),
                        project_id=job.project_id,
                        code=code,
                        description=description,
                        deadline=deadline,
                        source_anchors=anchors,
                        version=1,
                        active=True,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                record = CriterionProposalReviewRecord(
                    id=uuid4(),
                    proposal_id=proposal.id,
                    proposal_revision=proposal.revision,
                    action=review.action,
                    correction=review.correction,
                    comment=review.comment,
                    created_criterion=criterion,
                    reviewed_by=user.subject,
                    reviewed_at=timestamp,
                )
                staged.append((record, criterion))

            for record, criterion in staged:
                if criterion is not None:
                    await uow.criteria.add(criterion)
                await uow.proposals.add_review(record)
            await uow.commit()
        return CriterionProposalReviewBatchResult(items=[item[0] for item in staged])

    async def list_report_validations(
        self,
        report_id: UUID,
        limit: int,
        cursor: str | None,
        include_history: bool,
        user: CurrentUser,
    ) -> PaginatedValidations:
        async with self._uow_factory() as uow:
            report = await uow.reports.get(report_id)
            if report is None:
                raise _not_found("report")
            await self._owned_project(uow, report.project_id, user)
            items = await uow.validations.list_for_report(report_id)
            hydrated: list[CriterionValidation] = []
            for item in items:
                decision = await uow.validations.get_decision(item.id)
                hydrated.append(
                    item.model_copy(
                        update={
                            "user_decision": decision,
                            "status": ValidationStatus.DECIDED if decision else item.status,
                        }
                    )
                )
        if not include_history:
            latest: dict[UUID, CriterionValidation] = {}
            for item in hydrated:
                current = latest.get(item.criterion_id)
                if current is None or item.revision > current.revision:
                    latest[item.criterion_id] = item
            hydrated = list(latest.values())
        hydrated.sort(key=lambda item: (str(item.criterion_id), -item.revision, str(item.id)))
        scope = f"validations:{user.subject}:{report_id}:{include_history}"
        page, next_cursor = self._page(hydrated, limit, cursor, scope)
        return PaginatedValidations(items=page, next_cursor=next_cursor)

    async def create_validation_decision(
        self,
        validation_id: UUID,
        data: UserDecisionCreate,
        user: CurrentUser,
        idempotency: IdempotencyContext,
    ) -> UserDecision:
        del idempotency
        async with self._uow_factory() as uow:
            validation = await uow.validations.get(validation_id)
            if validation is None:
                raise _not_found("criterion validation")
            report = await uow.reports.get(validation.report_id)
            if report is None:
                raise _not_found("report")
            await self._owned_project(uow, report.project_id, user)
            history = await uow.validations.list_for_report(report.id)
            latest_revision = max(
                item.revision for item in history if item.criterion_id == validation.criterion_id
            )
            if (
                data.validation_revision != validation.revision
                or validation.revision != latest_revision
            ):
                raise _problem(
                    409,
                    "stale_validation_revision",
                    "Stale validation revision",
                    "The validation revision is no longer current.",
                )
            if await uow.validations.get_decision(validation.id) is not None:
                raise _problem(
                    409,
                    "decision_already_exists",
                    "Decision already exists",
                    "This validation revision already has a user decision.",
                )
            decision = UserDecision(
                id=uuid4(),
                validation_id=validation.id,
                validation_revision=validation.revision,
                action=data.action,
                final_outcome=data.final_outcome,
                comment=data.comment,
                decided_by=user.subject,
                decided_at=_now(),
            )
            await uow.validations.add_decision(decision)

            latest_by_criterion: dict[UUID, CriterionValidation] = {}
            for item in history:
                current = latest_by_criterion.get(item.criterion_id)
                if current is None or item.revision > current.revision:
                    latest_by_criterion[item.criterion_id] = item
            all_decided = True
            for item in latest_by_criterion.values():
                if await uow.validations.get_decision(item.id) is None:
                    all_decided = False
                    break
            if all_decided:
                await uow.reports.update(
                    report.model_copy(
                        update={"status": ReportStatus.COMPLETED, "updated_at": _now()}
                    )
                )
            await uow.commit()
        return decision
