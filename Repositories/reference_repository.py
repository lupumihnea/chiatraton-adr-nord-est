from DAO.references_DAO import ReferenceDAO
from typing import List

class ReferenceRepository:
    @staticmethod
    def find_all_reference_by_obligation_id(cursor,obligation_id) ->List[ReferenceDAO]:
        select_statement = "SELECT * FROM referinte WHERE obligation_id = ?"
        cursor.execute(select_statement,(obligation_id,))
        rows=cursor.fetchall()
        return [ReferenceDAO.from_row(row) for row in rows]