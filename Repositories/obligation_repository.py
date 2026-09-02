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
        select_statement = "SELECT * FROM obligations WHERE project_id = ?"
        cursor.execute(select_statement,(project_id,))
        rows = cursor.fetchall()
        return [ObligationDAO.from_row(row) for row in rows]

    @staticmethod
    def insert_obligation(cursor,obligation_id, project_id, description=None, deadline=None) -> ObligationDAO:
        insert_statement = "INSERT INTO obligations (id,project_id, description, deadline) VALUES (?,?, ?, ?)"
        cursor.execute(insert_statement, (obligation_id,project_id, description, deadline))
        return ObligationDAO(id=cursor.lastrowid, project_id=project_id, description=description, deadline=deadline)

    @staticmethod
    def update_obligation_by_id(cursor, ob_id, project_id, description=None, deadline=None) -> ObligationDAO:
        update_statement = "UPDATE obligations SET project_id = ?, description = ?, deadline = ? WHERE id = ?"
        cursor.execute(update_statement, (project_id, description, deadline, ob_id))
        return ObligationDAO(id=ob_id, project_id=project_id, description=description, deadline=deadline)

    @staticmethod
    def delete_obligation(cursor, obligation_id):
        delete_statement = "DELETE FROM obligations WHERE id = ?"
        cursor.execute(delete_statement, (obligation_id,))


