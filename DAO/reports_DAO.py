from dataclasses import dataclass
from typing import Optional


@dataclass
class ReportDAO:
    id: int
    project_id: int
    document_id: int
    sequence_number: int
    kind: str
    period_start: str
    period_end: str
    submitted_at: Optional[str] = None
    status: str = "pending"
    created_at: Optional[str] = None
    finalized_at: Optional[str] = None

    @staticmethod
    def from_row(row):
        return ReportDAO(
            id=row[0], project_id=row[1], document_id=row[2], sequence_number=row[3],
            kind=row[4], period_start=row[5], period_end=row[6], submitted_at=row[7],
            status=row[8], created_at=row[9], finalized_at=row[10]
        )
