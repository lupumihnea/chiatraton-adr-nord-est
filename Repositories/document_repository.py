import aiosqlite

from Objects.document import Document


class DocumentRepo:
    @staticmethod
    async def get_document_by_id(cursor,doc_id) -> Document:
        select_statement = "SELECT * FROM documents WHERE id = ?"
        await cursor.execute(select_statement, (doc_id,))
        row = await cursor.fetchone()
        return Document.from_row(row)

    @staticmethod
    async def insert_document(cursor,doc_id, doc_type, path=None) -> Document:

        insert_statement = "INSERT INTO documents (id,type, path) VALUES (?,?, ?)"
        await cursor.execute(insert_statement, (doc_id,doc_type, path))
        return Document(id=doc_id, type=doc_type, path=path)

    @staticmethod
    async def delete_document_by_id(cursor,doc_id) :
        select_statement = "DELETE FROM documents WHERE id = ?"
        await cursor.execute(select_statement, (doc_id,))

