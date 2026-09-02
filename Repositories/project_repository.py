from __future__ import annotations

from typing import List

from DAO.projects_DAO import ProjectDAO


class ProjectRepository:
    @staticmethod
    def get_project_by_id(cursor, project_id: int) -> ProjectDAO | None:
        cursor.execute("SELECT id, call_id, time_ending, name FROM project WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        return ProjectDAO.from_row(row) if row else None

    @staticmethod
    def get_all_projects(cursor) -> List[ProjectDAO]:
        cursor.execute("SELECT id, call_id, time_ending, name FROM project ORDER BY id")
        return [ProjectDAO.from_row(row) for row in cursor.fetchall()]

    @staticmethod
    def upsert(cursor, project: ProjectDAO) -> None:
        cursor.execute(
            """
            INSERT INTO project(id, call_id, time_ending, name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                call_id=excluded.call_id,
                time_ending=excluded.time_ending,
                name=excluded.name
            """,
            (project.id, project.call_id, project.time_ending, project.name),
        )
