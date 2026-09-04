"""SQLite implementation of obligation repository."""

from typing import List, Optional
from datetime import datetime
from DAO.obligations_DAO import ObligationDAO
from Repositories.sqlite_base import SQLiteRepository


class SQLiteObligationRepository(SQLiteRepository):
    """SQLite-backed obligation repository using shared transaction."""

    def get_by_id(self, obligation_id: str) -> Optional[ObligationDAO]:
        """Retrieve obligation by ID."""
        self._execute(
            "SELECT id, project_id, description, deadline FROM obligations WHERE id = ?",
            (obligation_id,)
        )
        row = self.cursor.fetchone()
        return ObligationDAO.from_row(row) if row else None

    def get_by_project(self, project_id: str) -> List[ObligationDAO]:
        """Retrieve all obligations for a project."""
        self._execute(
            "SELECT id, project_id, description, deadline FROM obligations WHERE project_id = ?",
            (project_id,)
        )
        rows = self.cursor.fetchall()
        return [ObligationDAO.from_row(row) for row in rows]

    def insert(
        self,
        obligation_id: str,
        project_id: str,
        description: Optional[str] = None,
        deadline: Optional[datetime] = None
    ) -> ObligationDAO:
        """Insert new obligation."""
        self._execute(
            "INSERT INTO obligations (id, project_id, description, deadline) VALUES (?, ?, ?, ?)",
            (obligation_id, project_id, description, deadline),
        )
        return ObligationDAO(
            id=obligation_id,
            project_id=project_id,
            description=description,
            deadline=deadline
        )

    def update(
        self,
        obligation_id: str,
        project_id: str,
        description: Optional[str] = None,
        deadline: Optional[datetime] = None
    ) -> ObligationDAO:
        """Update existing obligation."""
        self._execute(
            "UPDATE obligations SET project_id = ?, description = ?, deadline = ? WHERE id = ?",
            (project_id, description, deadline, obligation_id),
        )
        return ObligationDAO(
            id=obligation_id,
            project_id=project_id,
            description=description,
            deadline=deadline
        )

    def delete(self, obligation_id: str) -> None:
        """Delete obligation by ID."""
        self._execute("DELETE FROM obligations WHERE id = ?", (obligation_id,))