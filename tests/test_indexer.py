
"""
Tests for reproducible synthetic corpus indexing.
"""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.ingestion import indexer


def test_indexer_generates_preserves_and_verifies(
    tmp_path,
    monkeypatch,
):
    """Verify JSON creation, reuse and PDF integrity."""

    relative_path = "contracts/example.pdf"
    pdf_path = tmp_path / relative_path
    pdf_path.parent.mkdir(parents=True)

    pdf_content = b"synthetic test document"
    pdf_path.write_bytes(pdf_content)

    manifest = {
        "files": [
            {
                "relative_path": relative_path,
                "size_bytes": len(pdf_content),
                "sha256": hashlib.sha256(
                    pdf_content
                ).hexdigest(),
            }
        ]
    }

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    monkeypatch.setattr(indexer, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(
        indexer,
        "MANIFEST_PATH",
        manifest_path,
    )

    conversions = []

    def fake_convert(path):
        conversions.append(path)
        return SimpleNamespace(document="fake-document")

    monkeypatch.setattr(
        indexer,
        "create_document_converter",
        lambda: SimpleNamespace(convert=fake_convert),
    )

    expected_export = {
        "document_id": "contracts/example",
        "source_pdf": relative_path,
        "page_count": 1,
        "text_elements": [],
        "table_rows": [],
    }

    monkeypatch.setattr(
        indexer,
        "build_structured_export",
        lambda document, source: expected_export,
    )

    # First run: generate missing JSON.
    first = indexer.index_synthetic_corpus()

    assert first == {
        "documents": 1,
        "generated": 1,
        "existing": 0,
    }

    json_path = (
        tmp_path / "parsed" / relative_path
    ).with_suffix(".json")

    assert json.loads(
        json_path.read_text(encoding="utf-8")
    ) == expected_export

    original_json = json_path.read_bytes()

    # Second run: preserve existing JSON.
    second = indexer.index_synthetic_corpus()

    assert second == {
        "documents": 1,
        "generated": 0,
        "existing": 1,
    }

    assert json_path.read_bytes() == original_json
    assert len(conversions) == 1

    # Reject a modified PDF, even with the same size.
    pdf_path.write_bytes(
        b"X" * len(pdf_content)
    )

    with pytest.raises(
        ValueError,
        match="PDF checksum mismatch",
    ):
        indexer.index_synthetic_corpus()

    assert json_path.read_bytes() == original_json
