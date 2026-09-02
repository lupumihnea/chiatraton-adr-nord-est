from dataclasses import dataclass
from typing import Optional


@dataclass
class ProjectDAO:
    id: int
    call_id: int
    time_ending: str
    name: Optional[str] = None

    @staticmethod
    def from_row(row):
        return ProjectDAO(id=row[0], call_id=row[1], time_ending=row[2], name=row[3])







