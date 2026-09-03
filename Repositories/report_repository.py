from __future__ import annotations

from DAO.reports_DAO import ReportDAO


class ReportRepository:
    COLUMNS = "id, project_id, document_id, sequence_number, kind, period_start, period_end, submitted_at, status, created_at, finalized_at"

    @staticmethod
    def add(cursor, project_id: int, document_id: int, sequence_number: int, kind: str,
            period_start: str, period_end: str, submitted_at: str | None = None) -> int:
        cursor.execute(
            """
            INSERT INTO reports(project_id, document_id, sequence_number, kind, period_start, period_end, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, document_id, sequence_number, kind, period_start, period_end, submitted_at),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def get_by_id(cursor, report_id: int) -> ReportDAO | None:
        cursor.execute(f"SELECT {ReportRepository.COLUMNS} FROM reports WHERE id = ?", (report_id,))
        row = cursor.fetchone()
        return ReportDAO.from_row(row) if row else None

    @staticmethod
    def get_all_by_project(cursor, project_id: int) -> list[ReportDAO]:
        cursor.execute(
            f"SELECT {ReportRepository.COLUMNS} FROM reports WHERE project_id = ? ORDER BY sequence_number",
            (project_id,),
        )
        return [ReportDAO.from_row(row) for row in cursor.fetchall()]

    @staticmethod
    def get_previous(cursor, report: ReportDAO) -> list[ReportDAO]:
        cursor.execute(
            f"""
            SELECT {ReportRepository.COLUMNS}
            FROM reports
            WHERE project_id = ? AND sequence_number < ?
            ORDER BY sequence_number DESC
            """,
            (report.project_id, report.sequence_number),
        )
        return [ReportDAO.from_row(row) for row in cursor.fetchall()]

    @staticmethod
    def set_status(cursor, report_id: int, status: str, finalized: bool = False) -> None:
        if finalized:
            cursor.execute(
                "UPDATE reports SET status=?, finalized_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, report_id),
            )
        else:
            cursor.execute("UPDATE reports SET status=? WHERE id=?", (status, report_id))
