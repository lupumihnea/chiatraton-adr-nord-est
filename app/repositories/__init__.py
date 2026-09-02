"""Persistence abstractions; concrete database adapters are out of scope."""

from app.repositories.interfaces import (
    AnalysisJobRepository,
    CriterionRepository,
    DocumentRepository,
    ProjectRepository,
    ReportRepository,
    ValidationRepository,
)

__all__ = [
    "AnalysisJobRepository",
    "CriterionRepository",
    "DocumentRepository",
    "ProjectRepository",
    "ReportRepository",
    "ValidationRepository",
]
