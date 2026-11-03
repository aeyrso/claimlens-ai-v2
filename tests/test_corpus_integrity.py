
"""
ClaimLens AI - Synthetic corpus integrity tests.

Validate PDF checksums and contractual associations
before documents enter the RAG ingestion pipeline.
"""

from hashlib import sha256
import json
import re
from pathlib import Path

import pymupdf


DATA_ROOT = Path(__file__).resolve().parents[1] / "data"


def load_manifest():
    path = DATA_ROOT / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def read_pdf_text(relative_path):
    path = DATA_ROOT / relative_path

    with pymupdf.open(str(path)) as pdf:
        return "\n".join(
            page.get_text("text")
            for page in pdf
        )


def test_corpus_integrity():
    manifest = load_manifest()
    entries = manifest["files"]

    assert len(entries) == 6

    listed_paths = [
        item["relative_path"]
        for item in entries
    ]

    # Ensure each PDF is listed exactly once.
    assert len(set(listed_paths)) == 6

    actual_paths = {
        path.relative_to(DATA_ROOT).as_posix()
        for folder in ("contracts", "policy_schedules")
        for path in (DATA_ROOT / folder).glob("*.pdf")
    }

    assert set(listed_paths) == actual_paths

    for item in entries:
        path = DATA_ROOT / item["relative_path"]

        assert path.is_file(), f"Missing PDF: {path}"

        content = path.read_bytes()

        assert len(content) == item["size_bytes"], (
            f"Incorrect size: {path.name}"
        )

        assert sha256(content).hexdigest() == item["sha256"], (
            f"Incorrect SHA-256: {path.name}"
        )


def test_contract_associations():
    manifest = load_manifest()
    pairs = manifest["pairs"]

    assert len(pairs) == 3
    assert {pair["id"] for pair in pairs} == {"A", "B", "C"}

    listed_paths = {
        item["relative_path"]
        for item in manifest["files"]
    }

    for pair in pairs:
        dossier = pair["id"]

        cg_path = pair["general_conditions"]
        cp_path = pair["policy_schedule"]

        assert cg_path in listed_paths
        assert cp_path in listed_paths

        cg_text = read_pdf_text(cg_path)
        cp_text = read_pdf_text(cp_path)

        expected_cg = f"HAB-{dossier}-CG-2026"
        expected_cp = f"HAB-{dossier}-CP-2026"

        cg_refs = set(
            re.findall(r"HAB-[ABC]-CG-2026", cg_text)
        )

        cp_cg_refs = set(
            re.findall(r"HAB-[ABC]-CG-2026", cp_text)
        )

        cp_refs = set(
            re.findall(r"HAB-[ABC]-CP-2026", cp_text)
        )

        policy_refs = set(
            re.findall(r"SIM-[ABC]-\d{4}", cp_text)
        )

        assert cg_refs == {expected_cg}
        assert cp_cg_refs == {expected_cg}
        assert cp_refs == {expected_cp}

        assert len(policy_refs) == 1
        assert next(iter(policy_refs)).startswith(
            f"SIM-{dossier}-"
        )
