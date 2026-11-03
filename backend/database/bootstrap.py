
"""
ClaimLens AI - Synthetic demo database initialization.

Create a persistent SQLite database from the
existing synthetic insurance corpus.
"""

import os
import sqlite3
import tempfile

from backend.config import SQLITE_DB_PATH
from backend.database.importer import import_synthetic_corpus


def initialize_demo_database() -> dict:
    """Initialize the demo database without overwriting existing data."""

    if SQLITE_DB_PATH.exists():
        raise FileExistsError(
            f"Database already exists: {SQLITE_DB_PATH}"
        )

    SQLITE_DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".claimlens-init-",
        suffix=".sqlite3",
        dir=SQLITE_DB_PATH.parent,
    )
    os.close(descriptor)

    try:
        connection = sqlite3.connect(temporary_path)

        try:
            counts = import_synthetic_corpus(connection)
        finally:
            connection.close()

        # Publish without replacing an existing destination.
        # Creating a hard link fails with FileExistsError if
        # another process has already created the database.
        # Both paths are in the same directory/filesystem.
        os.link(temporary_path, SQLITE_DB_PATH)

        return counts

    finally:
        # Removing the temporary name does not remove the
        # final database once its hard link has been created.
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


if __name__ == "__main__":
    print(initialize_demo_database())
