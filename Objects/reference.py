from dataclasses import dataclass
from typing import Optional

from DAO.references_DAO import ReferenceDAO
from document import Document


@dataclass
class Reference:
    reference_id: str
    document_link:str
    page:Optional[str]
    text:Optional[str]
    chapter:Optional[str]
    subject:Optional[str]

    @staticmethod
    def from_DAO(dao: ReferenceDAO, document:Document) -> Reference:
        link = document.get_link()
        if dao.page is not None:
            link = f"{link}#page={dao.page}"

        return Reference(
            reference_id=dao.id,
            document_link=link,
            page=str(dao.page) if dao.page is not None else None,
            text=dao.text,
            chapter=dao.chapter,
            subject=dao.subchapter,
        )

