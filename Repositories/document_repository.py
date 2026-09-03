from __future__ import annotations

from typing import List

from DAO.documents_DAO import DocumentDAO


class DocumentRepository:
    @staticmethod
    def get_document_by_id(cursor, document_id: int) -> DocumentDAO | None:
        cursor.execute("SELECT id, type, path FROM document WHERE id = ?", (document_id,))
        row = cursor.fetchone()
        return DocumentDAO.from_row(row) if row else None

    @staticmethod
    def get_document_by_reference_id(cursor, ref_id: int) -> DocumentDAO | None:
        cursor.execute(
            """
            SELECT d.id, d.type, d.path
            FROM "references" r
            JOIN document d ON d.id = r.document_id
            WHERE r.id = ?
            """,
            (ref_id,),
        )
        row = cursor.fetchone()
        return DocumentDAO.from_row(row) if row else None

    @staticmethod
    def get_all(cursor) -> List[DocumentDAO]:
        cursor.execute("SELECT id, type, path FROM document ORDER BY id")
        return [DocumentDAO.from_row(row) for row in cursor.fetchall()]

    @staticmethod
    def add(cursor, type_: int, path: str) -> int:
        cursor.execute("INSERT INTO document(type, path) VALUES (?, ?)", (type_, path))
        return int(cursor.lastrowid)
