
"""
ClaimLens AI - Importer security regression tests.

Verify that unsafe document paths are rejected, contractual
metadata remains unambiguous, and failed database imports
never modify existing data or leave a partial initialization.
"""

import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest

import backend.database.importer as importer
from backend.database.importer import read_export, read_schedule


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../manifest.json",
        r"..\manifest.json",
        "/tmp/secret.pdf",
        r"C:\temp\secret.pdf",
    ],
)
def test_read_export_rejects_unsafe_paths_before_read(
    monkeypatch,
    unsafe_path,
):
    """
    Reject parent traversal and absolute paths before
    attempting any filesystem read.
    """

    def forbidden_read(self, *args, **kwargs):
        raise AssertionError("Unsafe path reached filesystem")

    monkeypatch.setattr(Path, "read_text", forbidden_read)

    with pytest.raises(ValueError, match="Unsafe PDF path"):
        read_export(unsafe_path)


def test_read_export_rejects_symlink_outside_parsed(
    monkeypatch,
    tmp_path,
):
    """
    Reject a real symbolic link to a file outside data/parsed.

    Skip only when the operating system does not permit
    symbolic-link creation.
    """

    data_root = tmp_path / "data"
    parsed_root = data_root / "parsed"
    contracts_dir = parsed_root / "contracts"
    contracts_dir.mkdir(parents=True)

    external_file = tmp_path / "outside.json"
    external_file.write_text(
        '{"source_pdf": "contracts/linked.pdf"}',
        encoding="utf-8",
    )

    linked_file = contracts_dir / "linked.json"

    try:
        linked_file.symlink_to(external_file)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symbolic links unavailable: {exc}")

    monkeypatch.setattr(importer, "DATA_ROOT", data_root)

    def forbidden_read(self, *args, **kwargs):
        raise AssertionError(
            "Symlink target reached filesystem read"
        )

    monkeypatch.setattr(Path, "read_text", forbidden_read)

    with pytest.raises(ValueError, match="Unsafe PDF path"):
        read_export("contracts/linked.pdf")


def test_read_export_rejects_resolved_path_escape(
    monkeypatch,
    tmp_path,
):
    """
    Simulate a symbolic link resolving outside data/parsed,
    without requiring symlink privileges on Windows.
    """

    data_root = tmp_path / "data"
    parsed_root = data_root / "parsed"
    parsed_root.mkdir(parents=True)

    requested_pdf = "contracts/linked.pdf"
    candidate_json = parsed_root / "contracts" / "linked.json"
    external_json = tmp_path / "outside.json"

    original_resolve = Path.resolve

    def simulated_resolve(self, *args, **kwargs):
        if self == candidate_json:
            return external_json
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", simulated_resolve)
    monkeypatch.setattr(importer, "DATA_ROOT", data_root)

    def forbidden_read(self, *args, **kwargs):
        raise AssertionError("External file read was attempted")

    monkeypatch.setattr(Path, "read_text", forbidden_read)

    with pytest.raises(ValueError, match="Unsafe PDF path"):
        read_export(requested_pdf)


def test_read_schedule_rejects_duplicate_metadata():
    """
    A repeated contractual metadata field must not
    silently overwrite the original extracted value.
    """

    schedule = read_export(
        "policy_schedules/conditions_particulieres_A.pdf"
    )

    original_row = next(
        row
        for row in schedule["table_rows"]
        if set(row["column_headers"]) == {"Champ", "Valeur"}
    )

    duplicate_row = deepcopy(original_row)
    value_index = duplicate_row["column_headers"].index("Valeur")
    duplicate_row["row_cells"][value_index] = "CONFLICTING_VALUE"
    schedule["table_rows"].append(duplicate_row)

    with pytest.raises(ValueError, match="Duplicate metadata field"):
        read_schedule(schedule)


def test_import_rejects_existing_data_without_schema_changes():
    """
    Reimporting into a populated database must not modify
    its schema, security triggers, or contractual records.
    """

    connection = sqlite3.connect(":memory:")

    try:
        importer.import_synthetic_corpus(connection)

        # Simulate a legacy database lacking one security trigger.
        connection.execute(
            "DROP TRIGGER trg_coverage_source_insert"
        )
        connection.commit()

        def schema_snapshot():
            return connection.execute(
                """
                SELECT type, name, sql
                FROM sqlite_master
                WHERE name NOT GLOB 'sqlite_*'
                ORDER BY type, name
                """
            ).fetchall()

        def data_snapshot():
            return {
                table: connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                for table in (
                    "policies",
                    "policy_documents",
                    "policy_coverages",
                )
            }

        before_schema = schema_snapshot()
        before_data = data_snapshot()

        with pytest.raises(ValueError, match="Database is not empty"):
            importer.import_synthetic_corpus(connection)

        assert schema_snapshot() == before_schema
        assert data_snapshot() == before_data

    finally:
        connection.close()


def test_import_rejects_partial_schema_without_changes():
    """
    An existing but empty and incompatible schema
    must be rejected without creating new SQL objects.
    """

    connection = sqlite3.connect(":memory:")

    try:
        connection.execute(
            """
            CREATE TABLE policies (
                legacy_marker TEXT
            )
            """
        )
        connection.commit()

        def schema_snapshot():
            return connection.execute(
                """
                SELECT type, name, sql
                FROM sqlite_master
                WHERE name NOT GLOB 'sqlite_*'
                ORDER BY type, name
                """
            ).fetchall()

        before_schema = schema_snapshot()

        with pytest.raises(
            ValueError,
            match="Existing database schema",
        ):
            importer.import_synthetic_corpus(connection)

        assert schema_snapshot() == before_schema

    finally:
        connection.close()


def test_failed_initial_import_rolls_back_schema_and_data(
    monkeypatch,
):
    """
    A failed first import must roll back both DDL and DML,
    leave no open transaction, and allow a clean retry.
    """

    connection = sqlite3.connect(":memory:")
    original_read_schedule = importer.read_schedule
    processed_schedules = 0

    def interrupted_read_schedule(data):
        nonlocal processed_schedules
        processed_schedules += 1

        # The first policy is inserted, then the second fails.
        if processed_schedules == 2:
            raise RuntimeError("Simulated mid-import failure")

        return original_read_schedule(data)

    monkeypatch.setattr(
        importer,
        "read_schedule",
        interrupted_read_schedule,
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="Simulated mid-import failure",
        ):
            importer.import_synthetic_corpus(connection)

        assert processed_schedules == 2
        assert connection.in_transaction is False

        # The rollback must remove all created tables,
        # indexes and triggers, not only the inserted rows.
        remaining_objects = connection.execute(
            """
            SELECT type, name
            FROM sqlite_master
            WHERE name NOT GLOB 'sqlite_*'
            ORDER BY type, name
            """
        ).fetchall()

        assert remaining_objects == []

        # Restore normal parsing and retry on the same connection.
        monkeypatch.setattr(
            importer,
            "read_schedule",
            original_read_schedule,
        )

        counts = importer.import_synthetic_corpus(connection)

        assert counts == {
            "policies": 3,
            "documents": 6,
            "coverages": 12,
        }

        assert connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall() == []

        assert connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0] == "ok"

    finally:
        connection.close()
