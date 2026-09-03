from __future__ import annotations

import hashlib
import json
from typing import Any


EXCEPTION_OUTCOMES = {
    "nonconcordance",
    "missing_information",
    "different_value_or_date",
    "insufficient_evidence",
    "cross_report_contradiction",
    "human_review_required",
}


class MonitoringRepository:
    @staticmethod
    def create_job(
        cursor,
        project_id: int,
        report_id: int,
        idempotency_key: str,
        model_name: str,
        revision: int,
        kind: str = "analyze_report",
    ) -> int:
        cursor.execute(
            """
            INSERT INTO analysis_jobs(
                project_id, report_id, kind, status, idempotency_key,
                model_name, prompt_version, contract_version, revision
            ) VALUES (?, ?, ?, 'running', ?, ?, 'report-exceptions-v1', '1.0', ?)
            """,
            (project_id, report_id, kind, idempotency_key, model_name, revision),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def get_succeeded_job_by_key(cursor, key: str):
        cursor.execute(
            "SELECT * FROM analysis_jobs WHERE idempotency_key=? AND status='succeeded'",
            (key,),
        )
        return cursor.fetchone()

    @staticmethod
    def next_job_revision(cursor, report_id: int) -> int:
        row = cursor.execute(
            "SELECT COALESCE(MAX(revision), 0) + 1 FROM analysis_jobs WHERE report_id=?",
            (report_id,),
        ).fetchone()
        return int(row[0])

    @staticmethod
    def finish_job(cursor, job_id: int, status: str = "succeeded", error_code: str | None = None) -> None:
        cursor.execute(
            """
            UPDATE analysis_jobs
            SET status=?, error_code=?, completed_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (status, error_code, job_id),
        )

    @staticmethod
    def next_validation_revision(cursor, report_id: int, obligation_id: int) -> int:
        row = cursor.execute(
            """
            SELECT COALESCE(MAX(revision), 0) + 1
            FROM criterion_validations
            WHERE report_id=? AND obligation_id=?
            """,
            (report_id, obligation_id),
        ).fetchone()
        return int(row[0])

    @staticmethod
    def add_validation(
        cursor,
        report_id: int,
        obligation_id: int,
        revision: int,
        applicable: bool,
        outcome: str,
        rationale: str,
        analysis_job_id: int,
    ) -> int:
        status = "awaiting_user" if outcome in EXCEPTION_OUTCOMES else "proposed"
        if outcome == "insufficient_evidence":
            status = "insufficient_evidence"
        cursor.execute(
            """
            INSERT INTO criterion_validations(
                report_id, obligation_id, revision, applicable, ai_outcome,
                ai_rationale, status, analysis_job_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                obligation_id,
                revision,
                1 if applicable else 0,
                outcome,
                rationale,
                status,
                analysis_job_id,
            ),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def add_source(
        cursor,
        validation_id: int,
        role: str,
        document_id: int,
        page: int | None,
        text: str,
        chapter: str | None = None,
        subchapter: str | None = None,
    ) -> int:
        cursor.execute(
            """
            INSERT INTO validation_sources(
                validation_id, role, document_id, page, text, chapter, subchapter
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (validation_id, role, document_id, page, text, chapter, subchapter),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def latest_validations(cursor, report_id: int, exceptions_only: bool = False) -> list[dict[str, Any]]:
        filters = ""
        params: list[Any] = [report_id]
        if exceptions_only:
            placeholders = ",".join("?" for _ in EXCEPTION_OUTCOMES)
            filters = f" AND v.ai_outcome IN ({placeholders})"
            params.extend(sorted(EXCEPTION_OUTCOMES))

        rows = cursor.execute(
            f"""
            SELECT v.id, v.report_id, v.obligation_id, v.revision, v.applicable,
                   v.ai_outcome, v.ai_rationale, v.status, v.analysis_job_id,
                   v.created_at, o.description, o.deadline, o.importance
            FROM criterion_validations v
            JOIN obligation o ON o.id = v.obligation_id
            JOIN (
                SELECT obligation_id, MAX(revision) AS max_revision
                FROM criterion_validations
                WHERE report_id=?
                GROUP BY obligation_id
            ) latest
              ON latest.obligation_id=v.obligation_id AND latest.max_revision=v.revision
            WHERE v.report_id=? {filters}
            ORDER BY o.importance DESC, v.id
            """,
            [report_id, report_id] + params[1:],
        ).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            validation_id = int(row[0])
            sources = [dict(s) for s in cursor.execute(
                """
                SELECT id, role, document_id, page, text, chapter, subchapter
                FROM validation_sources
                WHERE validation_id=?
                ORDER BY CASE role
                    WHEN 'criterion_source' THEN 1
                    WHEN 'current_report' THEN 2
                    WHEN 'previous_report' THEN 3
                    WHEN 'project_context' THEN 4
                    ELSE 5 END, id
                """,
                (validation_id,),
            ).fetchall()]
            decision = cursor.execute(
                """
                SELECT id, action, final_outcome, corrected_text, comment, decided_by, decided_at
                FROM user_decisions
                WHERE validation_id=?
                ORDER BY id DESC LIMIT 1
                """,
                (validation_id,),
            ).fetchone()
            result.append(
                {
                    "id": validation_id,
                    "report_id": row[1],
                    "criterion_id": row[2],
                    "revision": row[3],
                    "applicable": bool(row[4]),
                    "outcome": row[5],
                    "rationale": row[6] or "",
                    "status": row[7],
                    "analysis_job_id": row[8],
                    "created_at": row[9],
                    "criterion_text": row[10],
                    "deadline": row[11],
                    "importance": row[12],
                    "sources": sources,
                    "decision": dict(decision) if decision else None,
                }
            )
        return result

    @staticmethod
    def add_decision(
        cursor,
        validation_id: int,
        action: str,
        final_outcome: str | None = None,
        corrected_text: str | None = None,
        comment: str | None = None,
        decided_by: str = "utilizator",
    ) -> int:
        cursor.execute(
            """
            INSERT INTO user_decisions(
                validation_id, action, final_outcome, corrected_text, comment, decided_by
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (validation_id, action, final_outcome, corrected_text, comment, decided_by),
        )
        cursor.execute(
            "UPDATE criterion_validations SET status='decided' WHERE id=?",
            (validation_id,),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def add_generated_output(cursor, report_id: int, kind: str, content: str, path: str | None) -> int:
        cursor.execute(
            "INSERT INTO generated_outputs(report_id, kind, content, path) VALUES (?, ?, ?, ?)",
            (report_id, kind, content, path),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def latest_output(cursor, report_id: int, kind: str):
        row = cursor.execute(
            """
            SELECT id, report_id, kind, content, path, created_at
            FROM generated_outputs
            WHERE report_id=? AND kind=?
            ORDER BY id DESC LIMIT 1
            """,
            (report_id, kind),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def history(cursor, report_id: int) -> dict[str, Any]:
        jobs = [dict(row) for row in cursor.execute(
            """
            SELECT id, kind, status, model_name, prompt_version, contract_version,
                   revision, started_at, completed_at, error_code
            FROM analysis_jobs
            WHERE report_id=? ORDER BY id DESC
            """,
            (report_id,),
        ).fetchall()]
        decisions = [dict(row) for row in cursor.execute(
            """
            SELECT d.id, d.validation_id, d.action, d.final_outcome, d.corrected_text,
                   d.comment, d.decided_by, d.decided_at
            FROM user_decisions d
            JOIN criterion_validations v ON v.id=d.validation_id
            WHERE v.report_id=?
            ORDER BY d.id DESC
            """,
            (report_id,),
        ).fetchall()]
        outputs = [dict(row) for row in cursor.execute(
            """
            SELECT id, kind, path, created_at
            FROM generated_outputs
            WHERE report_id=? ORDER BY id DESC
            """,
            (report_id,),
        ).fetchall()]
        return {"jobs": jobs, "decisions": decisions, "outputs": outputs}

    @staticmethod
    def criteria_fingerprint(criteria: list[dict[str, Any]]) -> str:
        payload = json.dumps(criteria, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
