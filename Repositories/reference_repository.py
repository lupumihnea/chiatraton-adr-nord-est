from __future__ import annotations

from typing import List

from DAO.references_DAO import ReferenceDAO


class ReferenceRepository:
    @staticmethod
    def find_all_reference_by_obligation_id(cursor, obligation_id: int) -> List[ReferenceDAO]:
        cursor.execute(
            """
            SELECT id, obligation_id, document_id, page, text, chapter, subchapter
            FROM "references"
            WHERE obligation_id = ?
            ORDER BY id
            """,
            (obligation_id,),
        )
        return [ReferenceDAO.from_row(row) for row in cursor.fetchall()]
