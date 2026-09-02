from dataclasses import dataclass
from typing import Optional

@dataclass
class ObligationDAO:
    id: int
    project_id: int
    description: Optional[str] = None
    deadline: Optional[str] = None
    importance: Optional[int] = None

    @staticmethod
    def from_row(row):
        return ObligationDAO(id=row[0], project_id=row[1], description=row[2],
                              deadline=row[3], importance=row[4])