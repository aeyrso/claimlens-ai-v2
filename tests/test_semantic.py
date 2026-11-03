
"""
ClaimLens AI - SQL-scoped semantic retrieval tests.

Verify documentary isolation, PDF provenance,
semantic ranking and safe input handling.
"""

import sqlite3

import numpy as np
import pytest

from backend.database.importer import import_synthetic_corpus
from backend.database.queries import get_policy_context
from backend.retrieval.semantic import (
    collect_authorized_evidence,
    search_policy_semantic,
)


@pytest.fixture(scope="module")
def connection():
    """Create one isolated synthetic database."""

    db = sqlite3.connect(":memory:")

    try:
        import_synthetic_corpus(db)
        yield db
    finally:
        db.close()


def test_collection_preserves_pdf_provenance(connection):
    """Every collected item must remain traceable to its PDF."""

    policy = "SIM-B-0002"

    context = get_policy_context(connection, policy)

    authorized_sources = {
        document["pdf_relative_path"]
        for document in context["documents"]
    }

    evidence = collect_authorized_evidence(
        connection,
        policy,
    )

    assert len(authorized_sources) == 2
    assert evidence

    for item in evidence:
        assert item["source_pdf"] in authorized_sources
        assert item["document_reference"]
        assert item["evidence_id"]
        assert item["text"].strip()
        assert item["page_number"] >= 1
        assert item["locations"]

        if item["evidence_type"] == "table_row":
            assert item["cells"]

            for cell in item["cells"]:
                assert cell["column_header"]
                assert cell["location"]["bbox"] is not None
                assert (
                    cell["location"]["page_number"]
                    == item["page_number"]
                )


def test_collection_respects_policy_isolation(connection):
    """Different policies must not share unauthorized documents."""

    evidence_a = collect_authorized_evidence(
        connection,
        "SIM-A-0001",
    )

    evidence_b = collect_authorized_evidence(
        connection,
        "SIM-B-0002",
    )

    sources_a = {
        item["source_pdf"]
        for item in evidence_a
    }

    sources_b = {
        item["source_pdf"]
        for item in evidence_b
    }

    assert evidence_a
    assert evidence_b

    assert len(sources_a) == 2
    assert len(sources_b) == 2

    assert sources_a.isdisjoint(sources_b)


def test_semantic_ranking_preserves_evidence(connection):
    """Semantic results must be ranked and remain auditable."""

    results = search_policy_semantic(
        connection,
        "SIM-B-0002",
        "On m'a pris ma bicyclette dans un garage collectif.",
        limit=10,
    )

    assert len(results) == 10

    scores = [
        item["semantic_score"]
        for item in results
    ]

    assert np.isfinite(scores).all()

    assert scores == sorted(
        scores,
        reverse=True,
    )

    for item in results:
        assert item["score"] == item["semantic_score"]
        assert item["source_pdf"]
        assert item["document_reference"]
        assert item["locations"]
        assert item["page_number"] >= 1


def test_unknown_policy_returns_no_evidence(
    connection,
    monkeypatch,
):
    """An unknown policy must not trigger embedding generation."""

    def forbidden_encoding(*args, **kwargs):
        raise AssertionError(
            "Embeddings must not run for unknown policies"
        )

    monkeypatch.setattr(
        "backend.retrieval.semantic.encode_texts",
        forbidden_encoding,
    )

    assert collect_authorized_evidence(
        connection,
        "POLICE-INCONNUE",
    ) == []

    assert search_policy_semantic(
        connection,
        "POLICE-INCONNUE",
        "Vol de velo",
    ) == []


def test_semantic_rejects_invalid_inputs(connection):
    """Invalid queries and result limits must be rejected."""

    for invalid_query in ("", "   ", None):
        with pytest.raises(ValueError):
            search_policy_semantic(
                connection,
                "SIM-B-0002",
                invalid_query,
            )

    for invalid_limit in (0, 51, True, -1):
        with pytest.raises(ValueError):
            search_policy_semantic(
                connection,
                "SIM-B-0002",
                "Vol de velo",
                limit=invalid_limit,
            )
