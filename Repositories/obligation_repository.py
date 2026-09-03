from __future__ import annotations

from typing import List

from DAO.obligations_DAO import ObligationDAO


class ObligationRepository:
    @staticmethod
    def get_obligation_by_id(cursor, obligation_id: int) -> ObligationDAO | None:
        cursor.execute(
            "SELECT id, project_id, description, deadline, importance FROM obligation WHERE id = ?",
            (obligation_id,),
        )
        row = cursor.fetchone()
        return ObligationDAO.from_row(row) if row else None

    @staticmethod
    def get_all_by_project_id(cursor, project_id: int) -> List[ObligationDAO]:
        cursor.execute(
            """
            SELECT id, project_id, description, deadline, importance
            FROM obligation
            WHERE project_id = ?
            ORDER BY importance DESC, id
            """,
            (project_id,),
        )
        return [ObligationDAO.from_row(row) for row in cursor.fetchall()]
