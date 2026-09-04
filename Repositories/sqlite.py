import aiosqlite
from types import TracebackType
from typing import Self
from uuid import UUID

from app.models.domain import (
    AnalysisJob, Criterion, CriterionProposal, CriterionProposalReviewRecord,
    CriterionValidation, Document, Project, Report, UserDecision
)
from app.repositories.interfaces import (
    AnalysisJobRepository, CriterionProposalRepository, CriterionRepository,
    DocumentRepository, ProjectRepository, ReportRepository,
    UnitOfWork, UnitOfWorkFactory, ValidationRepository
)


class SQLiteProjectRepository(ProjectRepository):
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def get(self, project_id: UUID) -> Project | None:
        async with self._conn.execute(
            "SELECT id, call_id, name, client FROM projects WHERE id = ?",
            (str(project_id),)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Project(id=UUID(row[0]), call_id=row[1], name=row[2], client=row[3])
            return None

    async def owner(self, project_id: UUID) -> str | None:
        async with self._conn.execute(
            "SELECT owner FROM project_owners WHERE project_id = ?",
            (str(project_id),)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def add(self, project: Project, owner: str) -> None:
        await self._conn.execute(
            "INSERT INTO projects (id, call_id, name, client) VALUES (?, ?, ?, ?)",
            (str(project.id), project.call_id, project.name, project.client)
        )
        await self._conn.execute(
            "INSERT INTO project_owners (project_id, owner) VALUES (?, ?)",
            (str(project.id), owner)
        )

    async def list_for_owner(self, owner: str) -> list[Project]:
        async with self._conn.execute(
            """
            SELECT p.id, p.call_id, p.name, p.client 
            FROM projects p 
            JOIN project_owners po ON p.id = po.project_id 
            WHERE po.owner = ?
            """,
            (owner,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [Project(id=UUID(row[0]), call_id=row[1], name=row[2], client=row[3]) for row in rows]


class SQLiteDocumentRepository(DocumentRepository):
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def get(self, document_id: UUID) -> Document | None:
        # Note: Corrected from the legacy bug which queried 'obligations' instead of 'documents'[cite: 16].
        async with self._conn.execute(
            "SELECT id, type, path FROM documents WHERE id = ?",
            (str(document_id),)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Document(id=UUID(row[0]), type=row[1], path=row[2])
            return None

    async def add(self, document: Document) -> None:
        await self._conn.execute(
            "INSERT INTO documents (id, type, path) VALUES (?, ?, ?)",
            (str(document.id), document.type, document.path)
        )

    async def list_for_project(self, project_id: UUID) -> list[Document]:
        async with self._conn.execute(
            """
            SELECT d.id, d.type, d.path 
            FROM documents d
            JOIN project_documents pd ON d.id = pd.document_id
            WHERE pd.project_id = ?
            """,
            (str(project_id),)
        ) as cursor:
            rows = await cursor.fetchall()
            return [Document(id=UUID(row[0]), type=row[1], path=row[2]) for row in rows]

    async def find_by_sha256(self, project_id: UUID, sha256: str) -> Document | None:
        async with self._conn.execute(
            """
            SELECT d.id, d.type, d.path 
            FROM documents d
            JOIN project_documents pd ON d.id = pd.document_id
            WHERE pd.project_id = ? AND d.sha256 = ?
            """,
            (str(project_id), sha256)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Document(id=UUID(row[0]), type=row[1], path=row[2])
            return None


class SQLiteCriterionRepository(CriterionRepository):
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def get(self, criterion_id: UUID) -> Criterion | None:
        async with self._conn.execute(
            "SELECT id, project_id, description, deadline FROM obligations WHERE id = ?",
            (str(criterion_id),)
        ) as cursor:
            row = await cursor.fetchone()
            # Mapping obligation row to Criterion domain model
            if row:
                return Criterion(id=UUID(row[0]), project_id=UUID(row[1]), description=row[2])
            return None

    async def add(self, criterion: Criterion) -> None:
        await self._conn.execute(
            "INSERT INTO obligations (id, project_id, description, deadline) VALUES (?, ?, ?, ?)",
            (str(criterion.id), str(criterion.project_id), criterion.description, None)
        )

    async def list_for_project(self, project_id: UUID) -> list[Criterion]:
        async with self._conn.execute(
            "SELECT id, project_id, description, deadline FROM obligations WHERE project_id = ?",
            (str(project_id),)
        ) as cursor:
            rows = await cursor.fetchall()
            return [Criterion(id=UUID(row[0]), project_id=UUID(row[1]), description=row[2]) for row in rows]

    async def code_exists(self, project_id: UUID, normalized_code: str) -> bool:
        # Stub logic mapping to domain rules
        return False

    async def active_snapshot(self, project_id: UUID) -> tuple[int, list[Criterion]]:
        criteria = await self.list_for_project(project_id)
        return (1, criteria)


# Stubs for remaining repositories required by the UnitOfWork Protocol[cite: 13]
class SQLiteReportRepository(ReportRepository):
    def __init__(self, conn: aiosqlite.Connection): self._conn = conn
    async def get(self, report_id: UUID) -> Report | None: return None
    async def add(self, report: Report) -> None: pass
    async def update(self, report: Report) -> None: pass
    async def list_for_project(self, project_id: UUID) -> list[Report]: return []
    async def external_identity_exists(self, project_id: UUID, ext_sys: str, ext_id: str) -> bool: return False

class SQLiteAnalysisJobRepository(AnalysisJobRepository):
    def __init__(self, conn: aiosqlite.Connection): self._conn = conn
    async def get(self, job_id: UUID) -> AnalysisJob | None: return None
    async def add(self, job: AnalysisJob) -> None: pass
    async def update(self, job: AnalysisJob) -> None: pass
    async def set_criteria_snapshot(self, job_id: UUID, criteria: list[Criterion]) -> None: pass
    async def get_criteria_snapshot(self, job_id: UUID) -> list[Criterion]: return []

class SQLiteCriterionProposalRepository(CriterionProposalRepository):
    def __init__(self, conn: aiosqlite.Connection): self._conn = conn
    async def get(self, proposal_id: UUID) -> CriterionProposal | None: return None
    async def add_many(self, proposals: list[CriterionProposal]) -> None: pass
    async def list_for_job(self, job_id: UUID) -> list[CriterionProposal]: return []
    async def get_review(self, proposal_id: UUID) -> CriterionProposalReviewRecord | None: return None
    async def add_review(self, review: CriterionProposalReviewRecord) -> None: pass

class SQLiteValidationRepository(ValidationRepository):
    def __init__(self, conn: aiosqlite.Connection): self._conn = conn
    async def get(self, validation_id: UUID) -> CriterionValidation | None: return None
    async def add_many(self, validations: list[CriterionValidation]) -> None: pass
    async def list_for_report(self, report_id: UUID) -> list[CriterionValidation]: return []
    async def get_decision(self, validation_id: UUID) -> UserDecision | None: return None
    async def add_decision(self, decision: UserDecision) -> None: pass


class SQLiteUnitOfWork(UnitOfWork):
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn
        self.projects = SQLiteProjectRepository(conn)
        self.documents = SQLiteDocumentRepository(conn)
        self.criteria = SQLiteCriterionRepository(conn)
        self.reports = SQLiteReportRepository(conn)
        self.jobs = SQLiteAnalysisJobRepository(conn)
        self.proposals = SQLiteCriterionProposalRepository(conn)
        self.validations = SQLiteValidationRepository(conn)

    async def __aenter__(self) -> Self:
        await self._conn.execute("BEGIN")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self._conn.rollback()
        else:
            await self.commit()

    async def commit(self) -> None:
        await self._conn.commit()


class SQLiteUnitOfWorkFactory(UnitOfWorkFactory):
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def __call__(self) -> UnitOfWork:
        conn = await aiosqlite.connect(self.db_path)
        # Enable foreign keys for SQLite
        await conn.execute("PRAGMA foreign_keys = ON")
        return SQLiteUnitOfWork(conn)