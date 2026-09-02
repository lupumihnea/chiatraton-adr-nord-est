from dataclasses import dataclass
from typing import Optional

@dataclass
class ReferenceDAO:
    id: str
    obligation_id: str
    document_id: str
    page: Optional[int] = None
    text: Optional[str] = None
    chapter: Optional[str] = None
    subchapter: Optional[str] = None

    @staticmethod
    def from_row(row):
        return ReferenceDAO(id=row[0], obligation_id=row[1], document_id=row[2],
                             page=row[3], text=row[4], chapter=row[5], subchapter=row[6])