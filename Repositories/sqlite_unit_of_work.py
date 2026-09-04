"""Unit of Work pattern for SQLite repository coordination with atomic transactions."""

import sqlite3
from typing import Optional
from DataBase.db_schema import create_database_schema
from Repositories.sqlite_project_repository import SQLiteProjectRepository
from Repositories.sqlite_document_repository import SQLiteDocumentRepository
from Repositories.sqlite_obligation_repository import SQLiteObligationRepository
from Repositories.sqlite_reference_repository import SQLiteReferenceRepository


class SQLiteUnitOfWork:
    """
    Coordinates multiple repositories within a single atomic transaction.

    All repository operations share a single connection and cursor.
    Commit or rollback happens atomically at the end of the context.

    Usage:
        with SQLiteUnitOfWork(db_path) as uow:
            uow.projects.insert(project)
            uow.obligations.insert(obligation)
            # Both committed together, or both rolled back on error
    """

    def __init__(self, db_path: str):
        """
        Initialize Unit of Work with database path.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

        # Repository instances (initialized in __enter__)
        self.projects: Optional[SQLiteProjectRepository] = None
        self.documents: Optional[SQLiteDocumentRepository] = None
        self.obligations: Optional[SQLiteObligationRepository] = None
        self.references: Optional[SQLiteReferenceRepository] = None

        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create database schema if it doesn't exist."""
        con = sqlite3.connect(self.db_path)
        try:
            create_database_schema(con)
            con.commit()
        finally:
            con.close()

    def __enter__(self):
        """
        Enter transaction context.

        Opens a single connection and cursor, initializes all repositories
        to use the shared cursor, and begins a transaction.

        Returns:
            Self for use in context manager
        """
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()

        # Initialize repositories with shared cursor
        self.projects = SQLiteProjectRepository(self.cursor)
        self.documents = SQLiteDocumentRepository(self.cursor)
        self.obligations = SQLiteObligationRepository(self.cursor)
        self.references = SQLiteReferenceRepository(self.cursor)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit transaction context.

        If no exception occurred, commits all changes atomically.
        If an exception occurred, rolls back all changes.
        Always closes the connection.

        Args:
            exc_type: Exception type if an error occurred
            exc_val: Exception value if an error occurred
            exc_tb: Exception traceback if an error occurred
        """
        try:
            if exc_type is not None:
                # An exception occurred, rollback
                self.connection.rollback()
            else:
                # No exception, commit all changes atomically
                self.connection.commit()
        finally:
            # Always close the connection
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()

        return False  # Don't suppress exceptions