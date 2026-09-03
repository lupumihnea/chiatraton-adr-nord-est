from dataclasses import dataclass
from typing import Optional

@dataclass
class Project:
    id: str
    call_id: int
    name: Optional[str] = None
    client: Optional[str] = None

    @staticmethod
    def from_row(row):
        return Project(id=row[0], call_id=row[1], name=row[2], client=row[3])
