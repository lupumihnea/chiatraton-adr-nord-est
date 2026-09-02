from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class ObligationDAO:
    id: str
    project_id: str
    description: Optional[str] = None
    deadline: Optional[datetime] = None

    @staticmethod
    def from_row(row):
        return ObligationDAO(id=row[0], project_id=row[1], description=row[2],
                              deadline=row[3])