from DAO.obligations_DAO import ObligationDAO
from typing import List

class ObligationRepository:
    @staticmethod
    def get_obligation_by_id(cursor,obligation_id) ->ObligationDAO:
        select_statement = "SELECT * FROM obligations WHERE id = ?"
        cursor.execute(select_statement,(obligation_id,))
        row=cursor.fetchone()
        return ObligationDAO.from_row(row)

    @staticmethod
    def get_all_by_project_id(cursor,project_id) ->List[ObligationDAO]:
        select_statement = "SELECT * FROM obligations WHERE project_id = ? ORDER BY importance DESC"
        cursor.execute(select_statement,(project_id,))
        rows = cursor.fetchall()
        return [ObligationDAO.from_row(row) for row in rows]