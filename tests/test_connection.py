
"""
ClaimLens AI - SQLite connection security tests.

Verify:
- API database connections are read-only.
- Write operations are rejected.
- Connections are properly closed.
- Missing databases produce a controlled HTTP 503.
"""

import sqlite3
from contextlib import closing

import pytest
from fastapi import HTTPException

from backend.database import connection as db_module


def test_get_db_is_read_only_and_closes_connection(
    tmp_path,
    monkeypatch,
):
    """
    The API must read existing data without
    modifying the underlying SQLite database.
    """

    database_path = tmp_path / "test.sqlite3"

    # Prepare an isolated test database.
    with closing(sqlite3.connect(database_path)) as setup:
        with setup:
            setup.execute(
                """
                CREATE TABLE documents (
                    id INTEGER PRIMARY KEY
                )
                """
            )

            setup.execute(
                "INSERT INTO documents (id) VALUES (1)"
            )

    monkeypatch.setattr(
        db_module,
        "SQLITE_DB_PATH",
        database_path,
    )

    dependency = db_module.get_db()
    connection = next(dependency)

    try:
        # Reading must remain possible.
        count = connection.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

        assert count == 1

        # SQLite must explicitly enforce read-only queries.
        query_only = connection.execute(
            "PRAGMA query_only"
        ).fetchone()[0]

        assert query_only == 1

        # Writing through the API connection must fail.
        with pytest.raises(sqlite3.OperationalError):
            connection.execute(
                "INSERT INTO documents (id) VALUES (2)"
            )

        # The original data must remain unchanged.
        count_after = connection.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

        assert count_after == 1

    finally:
        dependency.close()

    # A closed SQLite connection must reject further use.
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")

    # Confirm that the database was not modified.
    with closing(sqlite3.connect(database_path)) as verification:
        final_count = verification.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

    assert final_count == 1


def test_get_db_rejects_missing_database(
    tmp_path,
    monkeypatch,
):
    """
    A missing database must not be created implicitly.

    The API must return a controlled HTTP 503 instead.
    """

    missing_path = tmp_path / "missing.sqlite3"

    assert not missing_path.exists()

    monkeypatch.setattr(
        db_module,
        "SQLITE_DB_PATH",
        missing_path,
    )

    dependency = db_module.get_db()

    with pytest.raises(HTTPException) as error:
        next(dependency)

    assert error.value.status_code == 503
    assert error.value.detail == "Database unavailable"

    assert not missing_path.exists()
