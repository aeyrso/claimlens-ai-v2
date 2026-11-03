
"""
ClaimLens AI - SQLite connection management.

Provide isolated, read-only database connections
for the local contractual analysis API.

Security principles:
- Fail when the database is unavailable.
- Do not create databases implicitly.
- Restrict API connections to read-only access.
- Close connections after every request.
- Avoid exposing internal database errors to clients.

This module does not provide user authentication
or policy-level access control.
"""

import sqlite3
from collections.abc import Generator

from fastapi import HTTPException, status

from backend.config import SQLITE_DB_PATH


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Provide a read-only SQLite connection for FastAPI.

    Each dependency invocation creates its own
    connection and closes it after the request.

    HTTP 503 is returned if the database cannot
    be opened or initialized for reading.
    """

    if not SQLITE_DB_PATH.is_file():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )

    connection: sqlite3.Connection | None = None

    try:
        # Use SQLite's URI read-only mode.
        # This also prevents implicit database creation.
        database_uri = (
            f"{SQLITE_DB_PATH.resolve().as_uri()}?mode=ro"
        )

        connection = sqlite3.connect(
            database_uri,
            uri=True,
            check_same_thread=False,
            timeout=5.0,
        )

        # Maintain foreign-key enforcement settings.
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        # Additional protection against accidental writes.
        connection.execute(
            "PRAGMA query_only = ON"
        )

    except sqlite3.Error as exc:
        if connection is not None:
            connection.close()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc

    try:
        yield connection

    finally:
        connection.close()
