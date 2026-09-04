"""Base SQLite repository with shared transaction management."""

import sqlite3
from typing import Optional


class SQLiteRepository:
    """Base class for SQLite repositories using shared connections."""

    def __init__(self, cursor: sqlite3.Cursor):
        """
        Initialize repository with a shared cursor.

        Args:
            cursor: Active SQLite cursor from the Unit of Work transaction
        """
        self.cursor = cursor

    def _execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a query using the shared cursor.

        Args:
            query: SQL query string
            params: Query parameters for safe binding

        Returns:
            The cursor for fetching results
        """
        self.cursor.execute(query, params)
        return self.cursor

    def _execute_many(self, query: str, params_list: list) -> None:
        """
        Execute multiple queries in batch.

        Args:
            query: SQL query string
            params_list: List of parameter tuples
        """
        self.cursor.executemany(query, params_list)