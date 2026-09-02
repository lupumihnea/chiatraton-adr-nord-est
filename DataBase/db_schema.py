from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def database_path() -> str:
    """Resolve the shared SQLite file used by legacy code and the AI adapter."""
    explicit = os.getenv("ADR_DB_PATH")
    if explicit:
        return explicit

    url = os.getenv("DATABASE_URL", "")
    prefix = "sqlite:///"
    if url.startswith(prefix):
        return url[len(prefix):]

    return "documents.db"


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _count(con: sqlite3.Connection, table: str) -> int:
    try:
        return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return 0


def create_database_schema(con: sqlite3.Connection) -> None:
    """
    Canonical schema for the integrated hackathon build.

    The four original entities keep the exact schema used by the RAG prototype:
    project / document / obligation / references. The monitoring workflow is an
    additive extension, so existing extraction data remains usable.
    """
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS project(
            id INTEGER PRIMARY KEY,
            call_id INTEGER,
            time_ending TIMESTAMP,
            name TEXT
        );

        CREATE TABLE IF NOT EXISTS obligation(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            deadline TIMESTAMP,
            importance INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(project_id) REFERENCES project(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS document(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type INTEGER NOT NULL,
            path TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS "references"(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            obligation_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            page INTEGER,
            text TEXT NOT NULL,
            chapter TEXT,
            subchapter TEXT,
            FOREIGN KEY(obligation_id) REFERENCES obligation(id) ON DELETE CASCADE,
            FOREIGN KEY(document_id) REFERENCES document(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS project_documents(
            project_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'project_document',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(project_id, document_id),
            FOREIGN KEY(project_id) REFERENCES project(id) ON DELETE CASCADE,
            FOREIGN KEY(document_id) REFERENCES document(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reports(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            sequence_number INTEGER NOT NULL,
            kind TEXT NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            submitted_at TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finalized_at TIMESTAMP,
            UNIQUE(project_id, sequence_number),
            FOREIGN KEY(project_id) REFERENCES project(id) ON DELETE CASCADE,
            FOREIGN KEY(document_id) REFERENCES document(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS analysis_jobs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            report_id INTEGER,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            model_name TEXT,
            prompt_version TEXT,
            contract_version TEXT,
            revision INTEGER NOT NULL DEFAULT 1,
            started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            error_code TEXT,
            FOREIGN KEY(project_id) REFERENCES project(id) ON DELETE CASCADE,
            FOREIGN KEY(report_id) REFERENCES reports(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS criterion_validations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            obligation_id INTEGER NOT NULL,
            criterion_version INTEGER NOT NULL DEFAULT 1,
            revision INTEGER NOT NULL,
            applicable INTEGER NOT NULL DEFAULT 1,
            ai_outcome TEXT NOT NULL,
            ai_rationale TEXT,
            status TEXT NOT NULL DEFAULT 'awaiting_user',
            analysis_job_id INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(report_id, obligation_id, revision),
            FOREIGN KEY(report_id) REFERENCES reports(id) ON DELETE CASCADE,
            FOREIGN KEY(obligation_id) REFERENCES obligation(id) ON DELETE RESTRICT,
            FOREIGN KEY(analysis_job_id) REFERENCES analysis_jobs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS validation_sources(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            validation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            document_id INTEGER NOT NULL,
            page INTEGER,
            text TEXT NOT NULL,
            chapter TEXT,
            subchapter TEXT,
            FOREIGN KEY(validation_id) REFERENCES criterion_validations(id) ON DELETE CASCADE,
            FOREIGN KEY(document_id) REFERENCES document(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS user_decisions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            validation_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            final_outcome TEXT,
            corrected_text TEXT,
            comment TEXT,
            decided_by TEXT NOT NULL DEFAULT 'utilizator',
            decided_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(validation_id) REFERENCES criterion_validations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS generated_outputs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            path TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(report_id) REFERENCES reports(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_obligation_project ON obligation(project_id);
        CREATE INDEX IF NOT EXISTS idx_reference_obligation ON "references"(obligation_id);
        CREATE INDEX IF NOT EXISTS idx_report_project ON reports(project_id, sequence_number);
        CREATE INDEX IF NOT EXISTS idx_validation_report ON criterion_validations(report_id);
        CREATE INDEX IF NOT EXISTS idx_validation_job ON criterion_validations(analysis_job_id);
        CREATE INDEX IF NOT EXISTS idx_decision_validation ON user_decisions(validation_id);
        """
    )


def migrate_legacy_plural_schema(con: sqlite3.Connection) -> None:
    """
    One-way compatibility helper for the repository's original plural tables.
    It copies data only when the new canonical table is still empty.
    """
    mapping = [
        ("projects", "project", "id, call_id, time_ending, name"),
        ("documents", "document", "id, type, path"),
        ("obligations", "obligation", "id, project_id, description, deadline, importance"),
        (
            "referinte",
            '"references"',
            "id, obligation_id, document_id, page, text, chapter, subchapter",
        ),
    ]

    for old, new, columns in mapping:
        if _table_exists(con, old) and _count(con, new) == 0:
            try:
                con.execute(
                    f"INSERT OR IGNORE INTO {new} ({columns}) SELECT {columns} FROM {old}"
                )
            except sqlite3.Error:
                # Keep setup non-destructive even if an old experimental schema
                # has incompatible columns.
                pass


def setup_database(path: str | None = None) -> sqlite3.Connection:
    db_path = path or database_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    create_database_schema(con)
    migrate_legacy_plural_schema(con)
    con.commit()
    return con


if __name__ == "__main__":
    con = setup_database()
    print(f"Database ready: {database_path()}")
    con.close()
