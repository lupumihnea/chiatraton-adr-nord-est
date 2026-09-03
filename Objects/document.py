from dataclasses import dataclass
from typing import Optional
from pathlib import Path

@dataclass
class Document:
    id: str
    type: int
    path: str

    @staticmethod
    def from_row(row):
        return Document(id=row[0], type=row[1], path=row[2])

    def get_link(self)->str:
        url = Path(self.path).as_uri()
        return url