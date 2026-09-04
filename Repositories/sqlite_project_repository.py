"""SQLite implementation of project repository."""

from typing import List, Optional
from Objects.project import Project
from Repositories.sqlite_base import SQLiteRepository


class SQLiteProjectRepository(SQLiteRepository):
    """SQLite-backed project repository using shared transaction."""

    def get_by_id(self, project_id: str) -> Optional[Project]:
        """Retrieve project by ID."""
        self._execute(
            "SELECT id, call_id, name, client FROM projects WHERE id = ?",
            (project_id,)
        )
        row = self.cursor.fetchone()
        return Project.from_row(row) if row else None

    def get_all(self) -> List[Project]:
        """Retrieve all projects."""
        self._execute("SELECT id, call_id, name, client FROM projects")
        rows = self.cursor.fetchall()
        return [Project.from_row(row) for row in rows]

    def insert(self, project: Project) -> Project:
        """Insert new project."""
        self._execute(
            "INSERT INTO projects (id, call_id, name, client) VALUES (?, ?, ?, ?)",
            (project.id, project.call_id, project.name, project.client),
        )
        return project

    def update(self, project: Project) -> Project:
        """Update existing project."""
        self._execute(
            "UPDATE projects SET call_id = ?, name = ?, client = ? WHERE id = ?",
            (project.call_id, project.name, project.client, project.id),
        )
        return project

    def upsert(self, project: Project) -> Project:
        """Insert or update project."""
        self._execute(
            """
            INSERT INTO projects (id, call_id, name, client)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                call_id = excluded.call_id,
                name = excluded.name,
                client = excluded.client
            """,
            (project.id, project.call_id, project.name, project.client),
        )
        return project

    def delete(self, project_id: str) -> None:
        """Delete project by ID."""
        self._execute("DELETE FROM projects WHERE id = ?", (project_id,))