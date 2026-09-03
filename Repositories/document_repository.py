from typing import List
from xml.dom.minidom import Document

from DAO.documents_DAO import DocumentDAO

class DocumentRepository:
    @staticmethod
    def insert_document(cursor, doc_type: int, path: str) -> int:
        insert_statement = "INSERT INTO documents (type, path) VALUES (?, ?)"
        cursor.execute(insert_statement, (doc_type, path))
        return cursor.lastrowid

    @staticmethod
    def get_document_by_reference_id(cursor,ref_id) -> Document:
        select_statement = "SELECT * FROM obligations WHERE id = ?"
        cursor.execute(select_statement, (ref_id,))
        row = cursor.fetchone()
        return DocumentDAO.from_row(row)
