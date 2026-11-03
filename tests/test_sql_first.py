
"""
ClaimLens AI - SQL-first regression tests.

Verify synthetic policy ingestion, policy isolation,
coverage subscriptions and document scoping.
"""

import sqlite3

import pytest

from backend.database.importer import import_synthetic_corpus
from backend.database.queries import get_policy_context


@pytest.fixture
def database():
    """Create a fresh synthetic SQLite database in memory."""

    connection = sqlite3.connect(":memory:")

    try:
        import_synthetic_corpus(connection)
        yield connection
    finally:
        connection.close()


def test_sql_import_integrity(database):
    """All synthetic records must be imported consistently."""

    expected_counts = {
        "policies": 3,
        "policy_documents": 6,
        "policy_coverages": 12,
    }

    for table, expected in expected_counts.items():
        actual = database.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        assert actual == expected

    subscribed = database.execute(
        "SELECT COUNT(*) FROM policy_coverages "
        "WHERE is_subscribed = 1"
    ).fetchone()[0]

    assert subscribed == 9

    not_subscribed = database.execute(
        "SELECT COUNT(*) FROM policy_coverages "
        "WHERE is_subscribed = 0"
    ).fetchone()[0]

    assert not_subscribed == 3

    assert database.execute(
        "PRAGMA foreign_key_check"
    ).fetchall() == []


def test_policy_context_isolation(database):
    """Each policy must expose only its own documents and coverages."""

    expected = {
        "SIM-A-0001": {
            "documents": {
                "contracts/contrat_A_protection_essentielle.pdf",
                "policy_schedules/conditions_particulieres_A.pdf",
            },
            "coverages": {
                "Incendie int\u00e9rieur": True,
                "Vol en logement": True,
                "Vol de v\u00e9lo en local commun": True,
                "Mobilier ext\u00e9rieur / Jardin": False,
            },
        },
        "SIM-B-0002": {
            "documents": {
                "contracts/contrat_B_mobilite_habitation.pdf",
                "policy_schedules/conditions_particulieres_B.pdf",
            },
            "coverages": {
                "SOCLE": True,
                "MOBILIT\u00c9+": True,
                "CASSE+": False,
                "JARDIN+": True,
            },
        },
        "SIM-C-0003": {
            "documents": {
                "contracts/contrat_C_serenite_etendue.pdf",
                "policy_schedules/conditions_particulieres_C.pdf",
            },
            "coverages": {
                "Incendie int\u00e9rieur": True,
                "D\u00e9g\u00e2t des eaux": True,
                "V\u00c9LO-S\u00c9CURIT\u00c9": False,
                "TERRASSE-ACCIDENT": True,
            },
        },
    }

    for policy_number, reference in expected.items():
        context = get_policy_context(database, policy_number)

        assert context is not None
        assert context["policy"]["policy_number"] == policy_number

        assert context["policy"]["valid_from"] == "2026-01-01"
        assert context["policy"]["valid_to"] == "2026-12-31"

        document_paths = {
            item["pdf_relative_path"]
            for item in context["documents"]
        }

        assert document_paths == reference["documents"]

        coverage_statuses = {
            item["coverage_label"]: item["is_subscribed"]
            for item in context["coverages"]
        }

        assert coverage_statuses == reference["coverages"]

        schedule_path = next(
            path for path in document_paths
            if path.startswith("policy_schedules/")
        )

        assert all(
            item["pdf_relative_path"] == schedule_path
            for item in context["coverages"]
        )


def test_unknown_policy_is_not_exposed(database):
    """Unknown or invalid policy references must not expose data."""

    assert get_policy_context(database, "SIM-UNKNOWN") is None

    with pytest.raises(ValueError):
        get_policy_context(database, "")

    with pytest.raises(ValueError):
        get_policy_context(database, None)


def test_sql_rejects_invalid_subscription_value(database):
    """
    The database schema must reject subscription
    values other than 0 and 1.
    """

    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            UPDATE policy_coverages
            SET is_subscribed = ?
            WHERE policy_number = ?
            """,
            (2, "SIM-A-0001"),
        )




def test_policy_context_rejects_cross_policy_coverage(
    database,
):
    """
    Verify that Python rejects cross-policy coverage sources.

    Simulate a legacy database containing inconsistent
    documentary references.

    Foreign-key enforcement and the coverage-update
    trigger are temporarily disabled only in this
    isolated in-memory test database.
    """

    # Verify that the protection normally exists.
    trigger = database.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'trigger'
          AND name = ?
        """,
        ("trg_coverage_source_update",),
    ).fetchone()

    assert trigger is not None

    # Find a policy B document.
    foreign_document_id = database.execute(
        """
        SELECT id
        FROM policy_documents
        WHERE policy_number = ?
          AND document_kind = ?
        """,
        ("SIM-B-0002", "POLICY_SCHEDULE"),
    ).fetchone()[0]

    # Foreign-key settings must be changed
    # outside an active SQLite transaction.
    database.commit()
    database.execute("PRAGMA foreign_keys = OFF")

    try:
        assert database.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0] == 0

        # Simulate the absence of the new trigger
        # in a legacy database.
        database.execute(
            "DROP TRIGGER trg_coverage_source_update"
        )

        # Associate a policy A coverage with
        # a document belonging to policy B.
        database.execute(
            """
            UPDATE policy_coverages
            SET source_document_id = ?
            WHERE id = (
                SELECT id
                FROM policy_coverages
                WHERE policy_number = ?
                ORDER BY id
                LIMIT 1
            )
            """,
            (foreign_document_id, "SIM-A-0001"),
        )

        database.commit()

    finally:
        database.rollback()
        database.execute("PRAGMA foreign_keys = ON")

    # Restore foreign-key enforcement.
    assert database.execute(
        "PRAGMA foreign_keys"
    ).fetchone()[0] == 1

    # The deliberately corrupted data must
    # now be detectable by SQLite.
    violations = database.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    assert violations

    # Python must independently reject
    # the inconsistent contractual evidence.
    with pytest.raises(
        ValueError,
        match="Invalid coverage source document",
    ):
        get_policy_context(
            database,
            "SIM-A-0001",
        )



def test_policy_context_rejects_general_conditions_as_source(
    database,
):
    """
    Python must reject a coverage sourced from
    GENERAL_CONDITIONS instead of POLICY_SCHEDULE.

    Simulate legacy data by removing the update trigger
    in this isolated in-memory test database only.
    """

    # Verify that the database normally has the trigger.
    trigger = database.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'trigger'
          AND name = ?
        """,
        ("trg_coverage_source_update",),
    ).fetchone()

    assert trigger is not None

    # Simulate a legacy database without this trigger.
    database.execute(
        "DROP TRIGGER trg_coverage_source_update"
    )

    general_document_id = database.execute(
        """
        SELECT id
        FROM policy_documents
        WHERE policy_number = ?
          AND document_kind = ?
        """,
        ("SIM-A-0001", "GENERAL_CONDITIONS"),
    ).fetchone()[0]

    database.execute(
        """
        UPDATE policy_coverages
        SET source_document_id = ?
        WHERE id = (
            SELECT id
            FROM policy_coverages
            WHERE policy_number = ?
            ORDER BY id
            LIMIT 1
        )
        """,
        (general_document_id, "SIM-A-0001"),
    )

    database.commit()

    # The reference belongs to the correct policy,
    # so the composite foreign key remains satisfied.
    assert database.execute(
        "PRAGMA foreign_key_check"
    ).fetchall() == []

    # Python must independently reject the wrong type.
    with pytest.raises(
        ValueError,
        match="Invalid coverage source document",
    ):
        get_policy_context(database, "SIM-A-0001")


def test_policy_context_resists_sql_injection(database):
    """
    SQL injection attempts must not bypass
    the policy-number filter.
    """

    malicious_policy = "SIM-A-0001' OR 1=1 --"

    result = get_policy_context(
        database,
        malicious_policy,
    )

    assert result is None

    # A normal lookup must still work.
    valid_result = get_policy_context(
        database,
        "SIM-A-0001",
    )

    assert valid_result is not None
    assert (
        valid_result["policy"]["policy_number"]
        == "SIM-A-0001"
    )


def test_database_rejects_cross_policy_document_reference(
    database,
):
    """
    SQLite must reject a coverage referencing
    a document belonging to another policy.

    This protection must be enforced by the
    database, independently of Python validation.
    """

    assert database.execute(
        "PRAGMA foreign_keys"
    ).fetchone()[0] == 1

    foreign_document_id = database.execute(
        """
        SELECT id
        FROM policy_documents
        WHERE policy_number = ?
          AND document_kind = ?
        """,
        ("SIM-B-0002", "POLICY_SCHEDULE"),
    ).fetchone()[0]

    coverage_id = database.execute(
        """
        SELECT id
        FROM policy_coverages
        WHERE policy_number = ?
        ORDER BY id
        LIMIT 1
        """,
        ("SIM-A-0001",),
    ).fetchone()[0]

    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            UPDATE policy_coverages
            SET source_document_id = ?
            WHERE id = ?
            """,
            (foreign_document_id, coverage_id),
        )


def test_database_rejects_general_conditions_as_coverage_source(
    database,
):
    """
    SQLite must reject a coverage subscription whose
    source document is GENERAL_CONDITIONS instead
    of POLICY_SCHEDULE.
    """

    general_document_id = database.execute(
        """
        SELECT id
        FROM policy_documents
        WHERE policy_number = ?
          AND document_kind = ?
        """,
        ("SIM-A-0001", "GENERAL_CONDITIONS"),
    ).fetchone()[0]

    coverage_id = database.execute(
        """
        SELECT id
        FROM policy_coverages
        WHERE policy_number = ?
        ORDER BY id
        LIMIT 1
        """,
        ("SIM-A-0001",),
    ).fetchone()[0]

    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """
            UPDATE policy_coverages
            SET source_document_id = ?
            WHERE id = ?
            """,
            (general_document_id, coverage_id),
        )


def test_database_rejects_general_conditions_on_coverage_insert(
    database,
):
    """
    SQLite must reject a newly inserted coverage
    referencing GENERAL_CONDITIONS.
    """

    general_document_id = database.execute(
        """
        SELECT id
        FROM policy_documents
        WHERE policy_number = ?
          AND document_kind = ?
        """,
        ("SIM-A-0001", "GENERAL_CONDITIONS"),
    ).fetchone()[0]

    with pytest.raises(
        sqlite3.IntegrityError,
        match="Invalid coverage source document",
    ):
        database.execute(
            """
            INSERT INTO policy_coverages (
                policy_number,
                coverage_label,
                is_subscribed,
                source_status,
                observation,
                source_document_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "SIM-A-0001",
                "INTEGRITY_TEST_OPTION",
                1,
                "TEST",
                "Synthetic regression test",
                general_document_id,
            ),
        )

    # The rejected coverage must not be stored.
    count = database.execute(
        """
        SELECT COUNT(*)
        FROM policy_coverages
        WHERE coverage_label = ?
        """,
        ("INTEGRITY_TEST_OPTION",),
    ).fetchone()[0]

    assert count == 0


def test_database_rejects_referenced_document_type_change(
    database,
):
    """
    SQLite must prevent a referenced POLICY_SCHEDULE
    from being converted into GENERAL_CONDITIONS.
    """

    general_document_id = database.execute(
        """
        SELECT id
        FROM policy_documents
        WHERE policy_number = ?
          AND document_kind = ?
        """,
        ("SIM-A-0001", "GENERAL_CONDITIONS"),
    ).fetchone()[0]

    schedule_document_id = database.execute(
        """
        SELECT id
        FROM policy_documents
        WHERE policy_number = ?
          AND document_kind = ?
        """,
        ("SIM-A-0001", "POLICY_SCHEDULE"),
    ).fetchone()[0]

    # Remove the unused general-conditions document
    # to avoid a UNIQUE constraint masking the trigger.
    # This only affects the in-memory test database.
    database.execute(
        """
        DELETE FROM policy_documents
        WHERE id = ?
        """,
        (general_document_id,),
    )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="Referenced coverage document cannot be changed",
    ):
        database.execute(
            """
            UPDATE policy_documents
            SET document_kind = ?
            WHERE id = ?
            """,
            ("GENERAL_CONDITIONS", schedule_document_id),
        )

    # The referenced document must remain valid.
    document_kind = database.execute(
        """
        SELECT document_kind
        FROM policy_documents
        WHERE id = ?
        """,
        (schedule_document_id,),
    ).fetchone()[0]

    assert document_kind == "POLICY_SCHEDULE"
