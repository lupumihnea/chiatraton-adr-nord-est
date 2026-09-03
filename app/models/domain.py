"""Pydantic models mirroring contracts/openapi.yaml."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AnyHttpUrl, ConfigDict, Field, model_validator

from app.models.base import APIModel

ShortText = Annotated[str, Field(min_length=1)]
Cursor = Annotated[str, Field(min_length=1, max_length=2048)]

PRIMARY_DOCUMENT_CONSTRAINTS = {
    "uniqueItems": True,
    "contains": {
        "type": "object",
        "required": ["role"],
        "properties": {"role": {"enum": ["main_report", "final_document"]}},
    },
    "minContains": 1,
    "maxContains": 1,
}


class DocumentMediaType(StrEnum):
    PDF = "application/pdf"
    DOC = "application/msword"
    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    XLS = "application/vnd.ms-excel"
    XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ReportType(StrEnum):
    IMPLEMENTATION_PROGRESS = "implementation_progress"
    FINAL_PROGRESS = "final_progress"
    DURABILITY = "durability"


class ReportDocumentRole(StrEnum):
    MAIN_REPORT = "main_report"
    ATTACHMENT = "attachment"
    CLARIFICATION = "clarification"
    FINAL_DOCUMENT = "final_document"


class ExternalSystem(StrEnum):
    MYADR = "myadr"
    MYSMIS = "mysmis"
    OTHER = "other"


class ReportStatus(StrEnum):
    CREATED = "created"
    ANALYSIS_QUEUED = "analysis_queued"
    ANALYSIS_IN_PROGRESS = "analysis_in_progress"
    AWAITING_USER_DECISION = "awaiting_user_decision"
    COMPLETED = "completed"
    ANALYSIS_FAILED = "analysis_failed"


class AnalysisJobKind(StrEnum):
    ANALYZE_REPORT = "analyze_report"
    EXTRACT_CRITERIA = "extract_criteria"


class AnalysisJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIOutcome(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ValidationStatus(StrEnum):
    AWAITING_USER_DECISION = "awaiting_user_decision"
    DECIDED = "decided"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ANALYSIS_FAILED = "analysis_failed"


class DecisionAction(StrEnum):
    CONFIRM = "confirm"
    CORRECT = "correct"
    REJECT = "reject"


class CriterionProposalReviewAction(StrEnum):
    ACCEPT = "accept"
    CORRECT = "correct"
    REJECT = "reject"


class Health(APIModel):
    status: Literal["ok"]
    service: Literal["chiatraton-api"]
    version: ShortText


class SourceAnchor(APIModel):
    document_id: UUID
    page_number: int = Field(ge=1)
    passage: str = Field(min_length=1, max_length=8000)


class ProjectCreate(APIModel):
    name: str = Field(min_length=1, max_length=200)
    completion_date: date
    monitoring_end_date: date

    @model_validator(mode="after")
    def monitoring_cannot_end_early(self) -> Self:
        if self.monitoring_end_date < self.completion_date:
            raise ValueError("monitoringEndDate must be on or after completionDate")
        return self


class Project(ProjectCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime


class Document(APIModel):
    id: UUID
    project_id: UUID
    display_name: str = Field(min_length=1, max_length=255)
    original_filename: str = Field(min_length=1, max_length=255)
    media_type: DocumentMediaType
    size_bytes: int = Field(ge=1, le=52_428_800)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    page_count: int | None = Field(ge=1)
    created_at: datetime


class DocumentUpload(APIModel):
    file: bytes = Field(json_schema_extra={"format": "binary"})
    display_name: str = Field(  # type: ignore[assignment]
        default=None, min_length=1, max_length=255
    )


class CriterionCreate(APIModel):
    code: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=4000)
    deadline: date | None = None
    source_anchors: list[SourceAnchor] = Field(
        default_factory=list,
        max_length=100,
        json_schema_extra={"default": []},
    )


class Criterion(CriterionCreate):
    id: UUID
    project_id: UUID
    deadline: date | None = Field(...)
    source_anchors: list[SourceAnchor] = Field(max_length=100)
    version: int = Field(ge=1)
    active: bool
    created_at: datetime
    updated_at: datetime


class ReportDocument(APIModel):
    document_id: UUID
    role: ReportDocumentRole


class _ReportRules(APIModel):
    report_type: ReportType
    period_start: date
    period_end: date
    documents: list[ReportDocument] = Field(
        min_length=1,
        max_length=100,
        json_schema_extra=PRIMARY_DOCUMENT_CONSTRAINTS,
    )

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if self.period_end < self.period_start:
            raise ValueError("periodEnd must be on or after periodStart")
        if len({item.document_id for item in self.documents}) != len(self.documents):
            raise ValueError("documents must contain unique documentId values")
        primaries = {
            ReportDocumentRole.MAIN_REPORT,
            ReportDocumentRole.FINAL_DOCUMENT,
        }
        if sum(item.role in primaries for item in self.documents) != 1:
            raise ValueError("documents must contain exactly one primary document")
        return self


class ReportCreate(_ReportRules):
    model_config = ConfigDict(
        json_schema_extra={
            "dependentRequired": {
                "externalId": ["externalSystem"],
                "externalUrl": ["externalSystem"],
                "externalStatus": ["externalSystem"],
            }
        }
    )

    external_system: ExternalSystem = None  # type: ignore[assignment]
    external_id: str = Field(default=None, min_length=1, max_length=255)  # type: ignore[assignment]
    external_url: AnyHttpUrl = Field(  # type: ignore[assignment]
        default=None,
        max_length=2048,
        json_schema_extra={"pattern": "^https?://"},
    )
    external_status: str = Field(default=None, min_length=1, max_length=255)  # type: ignore[assignment]

    @model_validator(mode="after")
    def external_fields_require_system(self) -> Self:
        external_fields = (self.external_id, self.external_url, self.external_status)
        if any(value is not None for value in external_fields) and self.external_system is None:
            raise ValueError("externalSystem is required with external metadata")
        return self


class Report(_ReportRules):
    id: UUID
    project_id: UUID
    external_system: ExternalSystem | None = Field(...)
    external_id: str | None = Field(..., min_length=1, max_length=255)
    external_url: AnyHttpUrl | None = Field(..., max_length=2048)
    external_status: str | None = Field(..., min_length=1, max_length=255)
    status: ReportStatus
    created_at: datetime
    updated_at: datetime


class CriterionExtractionJobCreate(APIModel):
    document_ids: list[UUID] = Field(
        min_length=1,
        max_length=100,
        json_schema_extra={"uniqueItems": True},
    )

    @model_validator(mode="after")
    def unique_documents(self) -> Self:
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("documentIds must be unique")
        return self


class AnalysisJobCreate(APIModel):
    project_document_ids: list[UUID] = Field(
        default_factory=list,
        max_length=100,
        json_schema_extra={"default": [], "uniqueItems": True},
    )
    previous_report_ids: list[UUID] = Field(
        default_factory=list,
        max_length=100,
        json_schema_extra={"default": [], "uniqueItems": True},
    )

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        if len(set(self.project_document_ids)) != len(self.project_document_ids):
            raise ValueError("projectDocumentIds must be unique")
        if len(set(self.previous_report_ids)) != len(self.previous_report_ids):
            raise ValueError("previousReportIds must be unique")
        return self


class AnalysisJobError(APIModel):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)


class AnalysisJob(APIModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"kind": {"const": "extract_criteria"}},
                        "required": ["kind"],
                    },
                    "then": {
                        "properties": {
                            "reportId": {"type": "null"},
                            "documentIds": {"minItems": 1},
                            "projectDocumentIds": {"maxItems": 0},
                            "previousReportIds": {"maxItems": 0},
                            "criteriaSnapshotVersion": {"type": "null"},
                        }
                    },
                },
                {
                    "if": {
                        "properties": {"kind": {"const": "analyze_report"}},
                        "required": ["kind"],
                    },
                    "then": {
                        "properties": {
                            "reportId": {"type": "string", "format": "uuid"},
                            "documentIds": {"maxItems": 0},
                            "criteriaSnapshotVersion": {"type": "integer", "minimum": 1},
                            "proposalCount": {"type": "null"},
                        }
                    },
                },
                {
                    "if": {
                        "properties": {
                            "kind": {"const": "extract_criteria"},
                            "status": {"const": "succeeded"},
                        },
                        "required": ["kind", "status"],
                    },
                    "then": {"properties": {"proposalCount": {"type": "integer", "minimum": 0}}},
                },
            ]
        }
    )

    id: UUID
    project_id: UUID
    kind: AnalysisJobKind
    report_id: UUID | None
    status: AnalysisJobStatus
    document_ids: list[UUID] = Field(max_length=100, json_schema_extra={"uniqueItems": True})
    project_document_ids: list[UUID] = Field(
        max_length=100, json_schema_extra={"uniqueItems": True}
    )
    previous_report_ids: list[UUID] = Field(max_length=100, json_schema_extra={"uniqueItems": True})
    criteria_snapshot_version: int | None = Field(ge=1)
    proposal_count: int | None = Field(ge=0)
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error: AnalysisJobError | None

    @model_validator(mode="after")
    def validate_kind_shape(self) -> Self:
        lists = (self.document_ids, self.project_document_ids, self.previous_report_ids)
        if any(len(items) != len(set(items)) for items in lists):
            raise ValueError("job identifiers must be unique within each collection")
        if self.kind == AnalysisJobKind.EXTRACT_CRITERIA:
            if self.report_id is not None or not self.document_ids:
                raise ValueError("extract_criteria requires documentIds and forbids reportId")
            if self.project_document_ids or self.previous_report_ids:
                raise ValueError("extract_criteria forbids report-analysis inputs")
            if self.criteria_snapshot_version is not None:
                raise ValueError("extract_criteria forbids criteriaSnapshotVersion")
            if self.status == AnalysisJobStatus.SUCCEEDED and self.proposal_count is None:
                raise ValueError("succeeded extraction requires proposalCount")
        else:
            if self.report_id is None or self.document_ids:
                raise ValueError("analyze_report requires reportId and empty documentIds")
            if self.criteria_snapshot_version is None or self.proposal_count is not None:
                raise ValueError(
                    "analyze_report requires criteriaSnapshotVersion and forbids proposalCount"
                )
        return self


class CriterionProposalCorrection(APIModel):
    code: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=4000)
    deadline: date | None = None
    source_anchors: list[SourceAnchor] = Field(min_length=1, max_length=100)


class CriterionProposalReview(APIModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"action": {"const": "correct"}},
                        "required": ["action"],
                    },
                    "then": {"required": ["correction", "comment"]},
                    "else": {"properties": {"correction": False}},
                },
                {
                    "if": {
                        "properties": {"action": {"const": "reject"}},
                        "required": ["action"],
                    },
                    "then": {"required": ["comment"]},
                },
            ]
        }
    )

    proposal_id: UUID
    proposal_revision: int = Field(ge=1)
    action: CriterionProposalReviewAction
    correction: CriterionProposalCorrection = None  # type: ignore[assignment]
    comment: str = Field(default=None, min_length=1, max_length=4000)  # type: ignore[assignment]

    @model_validator(mode="after")
    def validate_action(self) -> Self:
        if self.action == CriterionProposalReviewAction.CORRECT:
            if self.correction is None or self.comment is None:
                raise ValueError("correct requires correction and comment")
        elif self.correction is not None:
            raise ValueError("correction is only allowed for correct")
        if self.action == CriterionProposalReviewAction.REJECT and self.comment is None:
            raise ValueError("reject requires comment")
        return self


class CriterionProposalReviewBatch(APIModel):
    reviews: list[CriterionProposalReview] = Field(
        min_length=1,
        max_length=100,
        json_schema_extra={"uniqueItems": True},
    )

    @model_validator(mode="after")
    def unique_proposals(self) -> Self:
        ids = [review.proposal_id for review in self.reviews]
        if len(ids) != len(set(ids)):
            raise ValueError("reviews must contain unique proposalId values")
        return self


class CriterionProposalReviewRecord(APIModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"action": {"enum": ["accept", "correct"]}},
                        "required": ["action"],
                    },
                    "then": {
                        "properties": {
                            "createdCriterion": {"$ref": "#/components/schemas/Criterion"}
                        }
                    },
                },
                {
                    "if": {
                        "properties": {"action": {"const": "reject"}},
                        "required": ["action"],
                    },
                    "then": {"properties": {"createdCriterion": {"type": "null"}}},
                },
            ]
        }
    )

    id: UUID
    proposal_id: UUID
    proposal_revision: int = Field(ge=1)
    action: CriterionProposalReviewAction
    correction: CriterionProposalCorrection | None
    comment: str | None = Field(max_length=4000)
    created_criterion: Criterion | None
    reviewed_by: str = Field(min_length=1, max_length=255)
    reviewed_at: datetime

    @model_validator(mode="after")
    def validate_created_criterion(self) -> Self:
        creates = self.action in {
            CriterionProposalReviewAction.ACCEPT,
            CriterionProposalReviewAction.CORRECT,
        }
        if creates != (self.created_criterion is not None):
            raise ValueError("accept/correct create Criterion; reject does not")
        return self


class CriterionProposal(APIModel):
    id: UUID
    analysis_job_id: UUID
    project_id: UUID
    revision: int = Field(ge=1)
    proposed_code: str = Field(min_length=1, max_length=100)
    proposed_description: str = Field(min_length=1, max_length=4000)
    proposed_deadline: date | None
    source_anchors: list[SourceAnchor] = Field(min_length=1, max_length=100)
    review: CriterionProposalReviewRecord | None
    created_at: datetime


class CriterionProposalReviewBatchResult(APIModel):
    items: list[CriterionProposalReviewRecord] = Field(min_length=1, max_length=100)


class UserDecisionCreate(APIModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"action": {"const": "correct"}},
                        "required": ["action"],
                    },
                    "then": {"required": ["finalOutcome", "comment"]},
                    "else": {"properties": {"finalOutcome": False}},
                },
                {
                    "if": {
                        "properties": {"action": {"const": "reject"}},
                        "required": ["action"],
                    },
                    "then": {"required": ["comment"]},
                },
            ]
        }
    )

    action: DecisionAction
    validation_revision: int = Field(ge=1)
    final_outcome: AIOutcome = None  # type: ignore[assignment]
    comment: str = Field(default=None, min_length=1, max_length=4000)  # type: ignore[assignment]

    @model_validator(mode="after")
    def validate_action(self) -> Self:
        if self.action == DecisionAction.CORRECT:
            if self.final_outcome is None or self.comment is None:
                raise ValueError("correct requires finalOutcome and comment")
        elif self.final_outcome is not None:
            raise ValueError("finalOutcome is only allowed for correct")
        if self.action == DecisionAction.REJECT and self.comment is None:
            raise ValueError("reject requires comment")
        return self


class UserDecision(APIModel):
    id: UUID
    validation_id: UUID
    validation_revision: int = Field(ge=1)
    action: DecisionAction
    final_outcome: AIOutcome | None
    comment: str | None = Field(max_length=4000)
    decided_by: str = Field(min_length=1, max_length=255)
    decided_at: datetime


class CriterionValidation(APIModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"aiOutcome": {"not": {"const": "insufficient_evidence"}}},
                        "required": ["aiOutcome"],
                    },
                    "then": {"properties": {"sourceAnchors": {"minItems": 1}}},
                }
            ]
        }
    )

    id: UUID
    report_id: UUID
    criterion_id: UUID
    criterion_version: int = Field(ge=1)
    analysis_job_id: UUID
    revision: int = Field(ge=1)
    status: ValidationStatus
    ai_outcome: AIOutcome
    ai_rationale: str = Field(min_length=1, max_length=8000)
    source_anchors: list[SourceAnchor] = Field(max_length=100)
    user_decision: UserDecision | None
    created_at: datetime

    @model_validator(mode="after")
    def factual_outcome_requires_anchor(self) -> Self:
        if self.ai_outcome != AIOutcome.INSUFFICIENT_EVIDENCE and not self.source_anchors:
            raise ValueError("factual AI outcomes require at least one SourceAnchor")
        return self


class PaginatedProjects(APIModel):
    items: list[Project]
    next_cursor: Cursor | None


class PaginatedCriteria(APIModel):
    items: list[Criterion]
    next_cursor: Cursor | None


class PaginatedCriterionProposals(APIModel):
    items: list[CriterionProposal]
    next_cursor: Cursor | None


class PaginatedReports(APIModel):
    items: list[Report]
    next_cursor: Cursor | None


class PaginatedValidations(APIModel):
    items: list[CriterionValidation]
    next_cursor: Cursor | None
