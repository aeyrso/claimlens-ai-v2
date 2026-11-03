
"""
ClaimLens AI - Database bootstrap security tests.

Verify that initialization never overwrites
a database created by another process.
"""

import os
from pathlib import Path

import pytest

import backend.database.bootstrap as bootstrap


def test_bootstrap_never_overwrites_concurrent_database(
    monkeypatch,
    tmp_path,
):
    """
    A database appearing during initialization
    must never be replaced.

    Simulate a collision and detect an unsafe rename
    without actually overwriting any file.
    """

    database_path = tmp_path / "claimlens.sqlite3"
    original_content = b"EXISTING_DATABASE_SENTINEL"

    monkeypatch.setattr(
        bootstrap,
        "SQLITE_DB_PATH",
        database_path,
    )

    def simulated_import(connection):
        # Another process creates the destination
        # after the initial existence check.
        database_path.write_bytes(original_content)

        return {
            "policies": 3,
            "documents": 6,
            "coverages": 12,
        }

    monkeypatch.setattr(
        bootstrap,
        "import_synthetic_corpus",
        simulated_import,
    )

    original_rename = os.rename

    def guarded_rename(source, destination):
        if Path(destination).exists():
            raise AssertionError(
                "Unsafe rename could overwrite existing database"
            )

        return original_rename(source, destination)

    # Intercept unsafe rename attempts.
    # No existing file will actually be overwritten.
    monkeypatch.setattr(
        bootstrap.os,
        "rename",
        guarded_rename,
    )

    # Correct behavior: explicitly reject the collision.
    with pytest.raises(FileExistsError):
        bootstrap.initialize_demo_database()

    # The previously created file must be preserved.
    assert database_path.read_bytes() == original_content

    # No temporary SQLite initialization file remains.
    assert list(
        tmp_path.glob(".claimlens-init-*.sqlite3")
    ) == []


def test_bootstrap_creates_fresh_database(
    monkeypatch,
    tmp_path,
):
    """
    Verify a fresh database can be initialized safely.

    The test uses a temporary directory and must
    never touch the main ClaimLens AI database.
    """

    import sqlite3
    from contextlib import closing

    database_path = tmp_path / "claimlens.sqlite3"

    monkeypatch.setattr(
        bootstrap,
        "SQLITE_DB_PATH",
        database_path,
    )

    assert not database_path.exists()

    # Initialize a real database from the
    # existing synthetic insurance corpus.
    counts = bootstrap.initialize_demo_database()

    assert counts == {
        "policies": 3,
        "documents": 6,
        "coverages": 12,
    }

    assert database_path.is_file()

    # The temporary initialization file must
    # have been removed after successful publishing.
    assert list(
        tmp_path.glob(".claimlens-init-*.sqlite3")
    ) == []

    # Verify the resulting database in read-only mode.
    database_uri = (
        f"{database_path.resolve().as_uri()}?mode=ro"
    )

    with closing(
        sqlite3.connect(database_uri, uri=True)
    ) as connection:

        assert connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0] == "ok"

        assert connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall() == []

        triggers = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
                """
            ).fetchall()
        }

        assert {
            "trg_coverage_source_insert",
            "trg_coverage_source_update",
            "trg_document_source_update",
        } <= triggers

    # A second initialization must not
    # overwrite the database just created.
    with pytest.raises(FileExistsError):
        bootstrap.initialize_demo_database()

    assert database_path.is_file()


def test_bootstrap_cleans_up_after_import_failure(
    monkeypatch,
    tmp_path,
):
    """
    A failed database import must leave no final
    database and no temporary SQLite file.
    """

    database_path = tmp_path / "claimlens.sqlite3"

    monkeypatch.setattr(
        bootstrap,
        "SQLITE_DB_PATH",
        database_path,
    )

    def failing_import(connection):
        # Simulate a partially initialized database.
        connection.execute(
            """
            CREATE TABLE incomplete_data (
                value TEXT
            )
            """
        )

        connection.execute(
            """
            INSERT INTO incomplete_data (value)
            VALUES (?)
            """,
            ("PARTIAL_IMPORT",),
        )

        raise RuntimeError(
            "Simulated import failure"
        )

    monkeypatch.setattr(
        bootstrap,
        "import_synthetic_corpus",
        failing_import,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated import failure",
    ):
        bootstrap.initialize_demo_database()

    # No incomplete final database must exist.
    assert not database_path.exists()

    # The temporary database must be removed.
    assert list(
        tmp_path.glob(".claimlens-init-*.sqlite3")
    ) == []
