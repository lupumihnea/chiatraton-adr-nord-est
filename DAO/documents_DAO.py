from dataclasses import dataclass
from typing import Optional

@dataclass
class DocumentDAO:
    id: int
    type: int
    path: Optional[str] = None

    @staticmethod
    def from_row(row):
        return DocumentDAO(id=row[0], type=row[1], path=row[2])