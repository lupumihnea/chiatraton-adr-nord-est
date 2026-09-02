from dataclasses import dataclass
from typing import Optional

@dataclass
class ProjectDAO:
    id: str
    call_id: int
    name: Optional[str] = None

    @staticmethod
    def from_row(row):
        return ProjectDAO(id=row[0], call_id=row[1], name=row[2])







