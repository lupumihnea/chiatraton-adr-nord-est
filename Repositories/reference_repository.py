from DAO.references_DAO import ReferenceDAO
from typing import List
import aiosqlite

class ReferenceRepo:
    @staticmethod
    async def find_all_reference_by_obligation_id(cursor,obligation_id) ->List[ReferenceDAO]:
        select_statement = "SELECT * FROM referinte WHERE obligation_id = ?"
        await cursor.execute(select_statement,(obligation_id,))
        rows=await cursor.fetchall()
        return [ReferenceDAO.from_row(row) for row in rows]

    @staticmethod
    async def find_reference_by_id(cursor,ref_id) ->List[ReferenceDAO]:
        select_statement = "SELECT * FROM referinte WHERE id = ?"
        await cursor.execute(select_statement,(ref_id,))
        row=await cursor.fetchone()
        return ReferenceDAO.from_row(row)

    @staticmethod
    async def insert_reference(cursor,reference_id, obligation_id, document_id, page=None, text=None,
                          chapter=None, subchapter=None) -> ReferenceDAO:
        insert_statement = """
            INSERT INTO referinte (reference_id,obligation_id, document_id, page, text, chapter, subchapter)
            VALUES (?,?, ?, ?, ?, ?, ?)
        """
        await cursor.execute(insert_statement, (reference_id,obligation_id, document_id, page, text, chapter, subchapter))
        return ReferenceDAO(id=reference_id, obligation_id=obligation_id, document_id=document_id,
                             page=page, text=text, chapter=chapter, subchapter=subchapter)

    # @staticmethod
    # def update_reference(cursor, id, obligation_id, document_id, page=None, text=None,
    #                       chapter=None, subchapter=None) -> ReferenceDAO:
    #     update_statement = """
    #         UPDATE referinte
    #         SET obligation_id = ?, document_id = ?, page = ?, text = ?, chapter = ?, subchapter = ?
    #         WHERE id = ?
    #     """
    #     cursor.execute(update_statement, (obligation_id, document_id, page, text, chapter, subchapter, id))
    #     return ReferenceDAO(id=id, obligation_id=obligation_id, document_id=document_id,
    #                          page=page, text=text, chapter=chapter, subchapter=subchapter)

    @staticmethod
    async def delete_reference(cursor, reference_id):
        delete_statement = "DELETE FROM referinte WHERE id = ?"
        await cursor.execute(delete_statement, (reference_id,))