

from Objects.document import Document


class DocumentRepository:
    @staticmethod
    def get_document_by_id(cursor,doc_id) -> Document:
        select_statement = "SELECT * FROM obligations WHERE id = ?"
        cursor.execute(select_statement, (doc_id,))
        row = cursor.fetchone()
        return Document.from_row(row)

    @staticmethod
    def insert_document(cursor,doc_id, doc_type, path=None) -> Document:

        insert_statement = "INSERT INTO documents (id,type, path) VALUES (?,?, ?)"
        cursor.execute(insert_statement, (doc_id,doc_type, path))
        return Document(id=doc_id, type=doc_type, path=path)

    @staticmethod
    def delete_document_by_id(cursor,doc_id) :
        select_statement = "DELETE FROM obligations WHERE id = ?"
        cursor.execute(select_statement, (doc_id,))

