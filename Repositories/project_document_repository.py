from __future__ import annotations

from typing import Iterable

from DAO.documents_DAO import DocumentDAO


class ProjectDocumentRepository:
    @staticmethod
    def link(cursor, project_id: int, document_id: int, role: str = "project_document") -> None:
        cursor.execute(
            """
            INSERT INTO project_documents(project_id, document_id, role)
            VALUES (?, ?, ?)
            ON CONFLICT(project_id, document_id) DO UPDATE SET role=excluded.role
            """,
            (project_id, document_id, role),
        )

    @staticmethod
    def link_many(cursor, project_id: int, document_ids: Iterable[int], role: str = "project_document") -> None:
        for document_id in document_ids:
            ProjectDocumentRepository.link(cursor, project_id, int(document_id), role)

    @staticmethod
    def get_documents(cursor, project_id: int, include_report_documents: bool = False) -> list[DocumentDAO]:
        sql = """
            SELECT d.id, d.type, d.path
            FROM project_documents pd
            JOIN document d ON d.id = pd.document_id
            WHERE pd.project_id = ?
        """
        params: list[object] = [project_id]
        if not include_report_documents:
            sql += " AND pd.role <> 'report'"
        sql += " ORDER BY d.id"
        cursor.execute(sql, params)
        return [DocumentDAO.from_row(row) for row in cursor.fetchall()]

    @staticmethod
    def ensure_from_criterion_references(cursor, project_id: int) -> int:
        """Backfill project-document links from already grounded criteria."""
        cursor.execute(
            """
            SELECT DISTINCT r.document_id
            FROM obligation o
            JOIN "references" r ON r.obligation_id = o.id
            WHERE o.project_id = ?
            """,
            (project_id,),
        )
        ids = [int(row[0]) for row in cursor.fetchall()]
        for document_id in ids:
            ProjectDocumentRepository.link(cursor, project_id, document_id, "criterion_source")
        return len(ids)
