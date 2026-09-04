"""SQLite implementation of document repository."""

from typing import List, Optional
from Objects.document import Document
from Repositories.sqlite_base import SQLiteRepository


class SQLiteDocumentRepository(SQLiteRepository):
    """SQLite-backed document repository using shared transaction."""

    def get_by_id(self, doc_id: str) -> Optional[Document]:
        """Retrieve document by ID."""
        self._execute(
            "SELECT id, type, path FROM documents WHERE id = ?",
            (doc_id,)
        )
        row = self.cursor.fetchone()
        return Document.from_row(row) if row else None

    def get_all(self) -> List[Document]:
        """Retrieve all documents."""
        self._execute("SELECT id, type, path FROM documents")
        rows = self.cursor.fetchall()
        return [Document.from_row(row) for row in rows]

    def insert(self, doc_id: str, doc_type: int, path: str) -> Document:
        """Insert new document."""
        self._execute(
            "INSERT INTO documents (id, type, path) VALUES (?, ?, ?)",
            (doc_id, doc_type, path),
        )
        return Document(id=doc_id, type=doc_type, path=path)

    def update(self, doc_id: str, doc_type: int, path: str) -> Document:
        """Update existing document."""
        self._execute(
            "UPDATE documents SET type = ?, path = ? WHERE id = ?",
            (doc_type, path, doc_id),
        )
        return Document(id=doc_id, type=doc_type, path=path)

    def delete(self, doc_id: str) -> None:
        """Delete document by ID."""
        self._execute("DELETE FROM documents WHERE id = ?", (doc_id,))