"""Persistence abstractions; concrete database adapters are out of scope."""

from app.repositories.interfaces import (
    AnalysisJobRepository,
    CriterionProposalRepository,
    CriterionRepository,
    DocumentRepository,
    ProjectRepository,
    ReportRepository,
    UnitOfWork,
    UnitOfWorkFactory,
    ValidationRepository,
)
from app.repositories.memory import InMemoryStore, InMemoryUnitOfWork, InMemoryUnitOfWorkFactory

__all__ = [
    "AnalysisJobRepository",
    "CriterionProposalRepository",
    "CriterionRepository",
    "DocumentRepository",
    "InMemoryStore",
    "InMemoryUnitOfWork",
    "InMemoryUnitOfWorkFactory",
    "ProjectRepository",
    "ReportRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
    "ValidationRepository",
]
