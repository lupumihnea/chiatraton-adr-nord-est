from dataclasses import dataclass
from typing import Optional

@dataclass
class Document:
    id: str
    type: int
    path: Optional[str] = None

    @staticmethod
    def from_row(row):
        return Document(id=row[0], type=row[1], path=row[2])