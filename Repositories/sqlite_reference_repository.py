"""SQLite implementation of reference repository."""

from typing import List, Optional
from DAO.references_DAO import ReferenceDAO
from Repositories.sqlite_base import SQLiteRepository


class SQLiteReferenceRepository(SQLiteRepository):
    """SQLite-backed reference repository using shared transaction."""

    def get_by_id(self, reference_id: str) -> Optional[ReferenceDAO]:
        """Retrieve reference by ID."""
        self._execute(
            """
            SELECT id, obligation_id, document_id, page, text, chapter, subchapter 
            FROM referinte WHERE id = ?
            """,
            (reference_id,)
        )
        row = self.cursor.fetchone()
        return ReferenceDAO.from_row(row) if row else None

    def get_by_obligation(self, obligation_id: str) -> List[ReferenceDAO]:
        """Retrieve all references for an obligation."""
        self._execute(
            """
            SELECT id, obligation_id, document_id, page, text, chapter, subchapter 
            FROM referinte WHERE obligation_id = ?
            """,
            (obligation_id,)
        )
        rows = self.cursor.fetchall()
        return [ReferenceDAO.from_row(row) for row in rows]

    def get_by_document(self, document_id: str) -> List[ReferenceDAO]:
        """Retrieve all references for a document."""
        self._execute(
            """
            SELECT id, obligation_id, document_id, page, text, chapter, subchapter 
            FROM referinte WHERE document_id = ?
            """,
            (document_id,)
        )
        rows = self.cursor.fetchall()
        return [ReferenceDAO.from_row(row) for row in rows]

    def insert(
        self,
        reference_id: str,
        obligation_id: str,
        document_id: str,
        page: Optional[int] = None,
        text: Optional[str] = None,
        chapter: Optional[str] = None,
        subchapter: Optional[str] = None,
    ) -> ReferenceDAO:
        """Insert new reference."""
        self._execute(
            """
            INSERT INTO referinte 
            (id, obligation_id, document_id, page, text, chapter, subchapter)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (reference_id, obligation_id, document_id, page, text, chapter, subchapter),
        )
        return ReferenceDAO(
            id=reference_id,
            obligation_id=obligation_id,
            document_id=document_id,
            page=page,
            text=text,
            chapter=chapter,
            subchapter=subchapter,
        )

    def delete(self, reference_id: str) -> None:
        """Delete reference by ID."""
        self._execute("DELETE FROM referinte WHERE id = ?", (reference_id,))