
"""
ClaimLens AI - Synthetic corpus SQLite importer.

Import verified structured JSON exports into the
SQL-first insurance policy database.
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

SUBSCRIPTION_STATUSES = {
    "SOUSCRIT": 1,
    "SOUSCRITE": 1,
    "NON SOUSCRIT": 0,
    "NON SOUSCRITE": 0,
}


def read_export(relative_pdf_path: str) -> dict:
    """
    Read a persisted JSON extraction for one PDF.

    Reject unsafe paths before reading file contents.
    All JSON exports must remain inside data/parsed.
    """

    if (
        not isinstance(relative_pdf_path, str)
        or not relative_pdf_path
    ):
        raise ValueError("Unsafe PDF path")

    # Manifest paths use forward slashes only.
    # Reject absolute paths, Windows drives and null bytes.
    if (
        relative_pdf_path.startswith("/")
        or "\\" in relative_pdf_path
        or ":" in relative_pdf_path
        or "\x00" in relative_pdf_path
    ):
        raise ValueError("Unsafe PDF path")

    parts = relative_pdf_path.split("/")

    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("Unsafe PDF path")

    if Path(relative_pdf_path).suffix.lower() != ".pdf":
        raise ValueError("Unsafe PDF path")

    parsed_root = (DATA_ROOT / "parsed").resolve()
    json_path = (
        parsed_root / relative_pdf_path
    ).with_suffix(".json").resolve()

    # Resolve symlinks and reject destinations outside parsed/.
    if not json_path.is_relative_to(parsed_root):
        raise ValueError("Unsafe PDF path")

    data = json.loads(
        json_path.read_text(encoding="utf-8")
    )

    if data["source_pdf"] != relative_pdf_path:
        raise ValueError(
            f"Incorrect source document: {json_path}"
        )

    return data


def get_document_reference(data: dict, kind: str) -> str:
    """Find the official synthetic document reference."""

    if kind not in {"CG", "CP"}:
        raise ValueError(f"Invalid document kind: {kind}")

    pattern = re.compile(
        rf"\bHAB-[A-Z0-9]+-{kind}-\d{{4}}\b"
    )

    references = {
        match.group(0)
        for element in data["text_elements"]
        for match in pattern.finditer(element["text"])
    }

    if len(references) != 1:
        raise ValueError(
            f"Expected one {kind} reference in "
            f"{data['source_pdf']}, found: {references}"
        )

    return references.pop()


def read_schedule(data: dict) -> tuple[dict, list[dict]]:
    """Extract policy metadata and subscribed options."""

    metadata = {}
    coverages = []

    for row in data["table_rows"]:
        values = dict(
            zip(
                row["column_headers"],
                row["row_cells"],
                strict=True,
            )
        )

        if set(values) == {"Champ", "Valeur"}:
            field_name = values["Champ"]

            # Contractual metadata must never be overwritten.
            if field_name in metadata:
                raise ValueError(
                    f"Duplicate metadata field: {field_name}"
                )

            metadata[field_name] = values["Valeur"]
            continue

        coverage_label = values.get(
            "Garantie / option",
            values.get("Garantie / module"),
        )

        if coverage_label is None:
            raise ValueError(
                f"Unrecognized table row: {values}"
            )

        status = values["Statut"].strip().upper()

        if status not in SUBSCRIPTION_STATUSES:
            raise ValueError(
                f"Unknown subscription status: {status}"
            )

        coverages.append(
            {
                "label": coverage_label,
                "is_subscribed": SUBSCRIPTION_STATUSES[status],
                "source_status": status,
                "observation": values["Observation"],
            }
        )

    period = metadata["Période assurée"]
    start_text, end_text = period.split(" au ")

    start_date = datetime.strptime(
        start_text, "%d/%m/%Y"
    ).date().isoformat()

    end_date = datetime.strptime(
        end_text, "%d/%m/%Y"
    ).date().isoformat()

    plan_name = metadata.get(
        "Formule",
        metadata.get("Niveau de garanties"),
    )

    if not plan_name:
        raise ValueError("Missing insurance plan")

    if not coverages:
        raise ValueError("No coverages extracted")

    policy = {
        "policy_number": metadata["Référence de police"],
        "holder_reference": metadata["Titulaire"],
        "product_name": metadata["Produit"],
        "plan_name": plan_name,
        "valid_from": start_date,
        "valid_to": end_date,
        "general_reference": metadata[
            "Conditions générales associées"
        ],
    }

    return policy, coverages


def import_synthetic_corpus(
    connection: sqlite3.Connection,
) -> dict:
    """
    Import the synthetic corpus into a completely empty database.

    Refuse existing data or schema objects. Schema creation and
    all data inserts are committed or rolled back together.
    """

    # executescript() commits a pending transaction first.
    # Never commit changes owned by the caller implicitly.
    if connection.in_transaction:
        raise RuntimeError(
            "Cannot initialize inside an active transaction"
        )

    connection.execute("PRAGMA foreign_keys = ON")

    if connection.execute(
        "PRAGMA foreign_keys"
    ).fetchone()[0] != 1:
        raise RuntimeError("SQLite foreign keys are disabled")

    required_tables = (
        "policies",
        "policy_documents",
        "policy_coverages",
    )

    existing_tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }

    # Preserve the existing error for populated databases.
    for table in required_tables:
        if table not in existing_tables:
            continue

        count = connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        if count:
            raise ValueError(
                f"Database is not empty: {table}"
            )

    existing_schema_objects = connection.execute(
        """
        SELECT type, name
        FROM sqlite_master
        WHERE name NOT GLOB 'sqlite_*'
        ORDER BY type, name
        """
    ).fetchall()

    if existing_schema_objects:
        raise ValueError(
            "Existing database schema: "
            "initialization requires an empty database"
        )

    # Read resources before changing any database objects.
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    manifest = json.loads(
        (DATA_ROOT / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    # BEGIN IMMEDIATE is explicitly part of the script:
    # executescript() does not start a transaction itself.
    # The connection context manager commits on success
    # and rolls back BOTH DDL and DML on failure.
    with connection:
        connection.executescript(
            "BEGIN IMMEDIATE;\n" + schema_sql
        )

        for pair in manifest["pairs"]:
            general_path = pair["general_conditions"]
            schedule_path = pair["policy_schedule"]

            general = read_export(general_path)
            schedule = read_export(schedule_path)

            policy, coverages = read_schedule(schedule)

            general_ref = get_document_reference(
                general, "CG"
            )
            schedule_ref = get_document_reference(
                schedule, "CP"
            )

            if general_ref != policy["general_reference"]:
                raise ValueError(
                    "General conditions mismatch: "
                    f"{policy['policy_number']}"
                )

            if (
                f"-{pair['id']}-" not in general_ref
                or f"-{pair['id']}-" not in schedule_ref
            ):
                raise ValueError(
                    f"Manifest pair mismatch: {pair['id']}"
                )

            connection.execute(
                """
                INSERT INTO policies (
                    policy_number,
                    holder_reference,
                    product_name,
                    plan_name,
                    valid_from,
                    valid_to
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    policy["policy_number"],
                    policy["holder_reference"],
                    policy["product_name"],
                    policy["plan_name"],
                    policy["valid_from"],
                    policy["valid_to"],
                ),
            )

            connection.execute(
                """
                INSERT INTO policy_documents (
                    policy_number,
                    document_kind,
                    document_reference,
                    pdf_relative_path
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    policy["policy_number"],
                    "GENERAL_CONDITIONS",
                    general_ref,
                    general_path,
                ),
            )

            cursor = connection.execute(
                """
                INSERT INTO policy_documents (
                    policy_number,
                    document_kind,
                    document_reference,
                    pdf_relative_path
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    policy["policy_number"],
                    "POLICY_SCHEDULE",
                    schedule_ref,
                    schedule_path,
                ),
            )

            schedule_document_id = cursor.lastrowid

            for coverage in coverages:
                connection.execute(
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
                        policy["policy_number"],
                        coverage["label"],
                        coverage["is_subscribed"],
                        coverage["source_status"],
                        coverage["observation"],
                        schedule_document_id,
                    ),
                )

        # Validate relationships before committing the import.
        if connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall():
            raise sqlite3.IntegrityError(
                "Imported corpus violates foreign keys"
            )

        if connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0] != "ok":
            raise sqlite3.DatabaseError(
                "SQLite integrity check failed"
            )

    return {
        "policies": connection.execute(
            "SELECT COUNT(*) FROM policies"
        ).fetchone()[0],
        "documents": connection.execute(
            "SELECT COUNT(*) FROM policy_documents"
        ).fetchone()[0],
        "coverages": connection.execute(
            "SELECT COUNT(*) FROM policy_coverages"
        ).fetchone()[0],
    }
