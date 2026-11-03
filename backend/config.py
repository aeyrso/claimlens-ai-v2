
"""
ClaimLens AI - Application configuration.

Local SQLite database for the synthetic demo corpus.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

SQLITE_DB_PATH = (
    PROJECT_ROOT / "data" / "claimlens.sqlite3"
)
