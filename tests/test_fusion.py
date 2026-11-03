
"""
ClaimLens AI - Reciprocal Rank Fusion tests.

Validate weighted ranking, provenance preservation,
document authorization and malformed input rejection.

These tests use real synthetic corpus evidence but
simulated lexical and semantic rankings.
"""

import math
import sqlite3

import pytest

from backend.database.importer import import_synthetic_corpus
from backend.database.queries import get_policy_context
from backend.retrieval.fusion import fuse_ranked_evidence
from backend.retrieval.semantic import collect_authorized_evidence


@pytest.fixture(scope="module")
def sample():
    """Load genuine PDF evidence authorized for policy B."""

    connection = sqlite3.connect(":memory:")

    try:
        import_synthetic_corpus(connection)

        context = get_policy_context(
            connection,
            "SIM-B-0002",
        )

        assert context is not None

        authorized = {
            document["pdf_relative_path"]
            for document in context["documents"]
        }

        evidence = collect_authorized_evidence(
            connection,
            "SIM-B-0002",
        )

    finally:
        connection.close()

    def find(prefix):
        return next(
            item
            for item in evidence
            if item["text"].startswith(prefix)
        )

    return {
        "authorized": authorized,
        "local": find(
            "Risque: Vol de v\u00e9lo en local commun"
        ),
        "street": find(
            "Risque: Vol de v\u00e9lo sur voie publique"
        ),
        "header": find(
            "CONDITIONS G\u00c9N\u00c9RALES"
        ),
    }


def build_rankings(sample):
    """Construct two intentionally different rankings."""

    local = sample["local"]
    street = sample["street"]
    header = sample["header"]

    lexical = [
        {
            **local,
            "score": 3,
            "matched_terms": ["velo", "local", "commun"],
        },
        {
            **street,
            "score": 1,
            "matched_terms": ["velo"],
        },
    ]

    semantic = [
        {
            **street,
            "semantic_score": 0.87,
        },
        {
            **local,
            "semantic_score": 0.86,
        },
        {
            **header,
            "semantic_score": 0.83,
        },
    ]

    return lexical, semantic


def test_rrf_ranking_and_formula(sample):
    """Weighted RRF should combine the two rankings."""

    lexical, semantic = build_rankings(sample)

    results = fuse_ranked_evidence(
        lexical,
        semantic,
        authorized_sources=sample["authorized"],
    )

    assert len(results) == 3

    assert results[0]["evidence_id"] == (
        sample["local"]["evidence_id"]
    )

    assert results[1]["evidence_id"] == (
        sample["street"]["evidence_id"]
    )

    assert results[2]["evidence_id"] == (
        sample["header"]["evidence_id"]
    )

    expected_local = 2.0 / 61 + 1.0 / 62
    expected_street = 2.0 / 62 + 1.0 / 61
    expected_header = 1.0 / 63

    assert math.isclose(
        results[0]["hybrid_score"],
        expected_local,
        rel_tol=1e-10,
    )

    assert math.isclose(
        results[1]["hybrid_score"],
        expected_street,
        rel_tol=1e-10,
    )

    assert math.isclose(
        results[2]["hybrid_score"],
        expected_header,
        rel_tol=1e-10,
    )

    assert results[0]["lexical_rank"] == 1
    assert results[0]["semantic_rank"] == 2
    assert results[0]["lexical_score"] == 3
    assert results[0]["semantic_score"] == 0.86


def test_fusion_preserves_pdf_provenance(sample):
    """Fusion must preserve the original document citations."""

    lexical, semantic = build_rankings(sample)

    results = fuse_ranked_evidence(
        lexical,
        semantic,
        authorized_sources=sample["authorized"],
    )

    local = results[0]
    original = sample["local"]

    assert local["source_pdf"] == original["source_pdf"]
    assert local["document_reference"] == (
        original["document_reference"]
    )
    assert local["page_number"] == original["page_number"]
    assert local["locations"] == original["locations"]
    assert local["cells"] == original["cells"]

    assert len(local["cells"]) == 5

    assert local["matched_terms"] == [
        "velo",
        "local",
        "commun",
    ]


def test_fusion_keeps_semantic_only_evidence(sample):
    """Semantic-only evidence should remain retrievable."""

    lexical, semantic = build_rankings(sample)

    results = fuse_ranked_evidence(
        lexical,
        semantic,
        authorized_sources=sample["authorized"],
    )

    header = results[2]

    assert header["lexical_rank"] is None
    assert header["lexical_score"] is None
    assert header["semantic_rank"] == 3
    assert header["semantic_score"] == 0.83
    assert header["matched_terms"] == []
    assert header["locations"]


def test_fusion_rejects_unauthorized_sources(sample):
    """Never admit documents outside the SQL policy scope."""

    unauthorized = {
        **sample["local"],
        "source_pdf": "contracts/unauthorized.pdf",
    }

    with pytest.raises(
        ValueError,
        match="Unauthorized evidence source",
    ):
        fuse_ranked_evidence(
            [unauthorized],
            [],
            authorized_sources=sample["authorized"],
        )

    # No authorized documents means no results.
    assert fuse_ranked_evidence(
        [unauthorized],
        [],
        authorized_sources=set(),
    ) == []


def test_fusion_rejects_duplicates_and_conflicts(sample):
    """Reject repeated or inconsistent documentary identities."""

    local = sample["local"]

    with pytest.raises(
        ValueError,
        match="Duplicate evidence",
    ):
        fuse_ranked_evidence(
            [local, local],
            [],
            authorized_sources=sample["authorized"],
        )

    conflicting = {
        **local,
        "page_number": local["page_number"] + 1,
        "semantic_score": 0.85,
    }

    with pytest.raises(
        ValueError,
        match="Inconsistent evidence provenance",
    ):
        fuse_ranked_evidence(
            [local],
            [conflicting],
            authorized_sources=sample["authorized"],
        )


def test_fusion_limits_and_determinism(sample):
    """Reject invalid limits and maintain stable ranking."""

    lexical, semantic = build_rankings(sample)

    first = fuse_ranked_evidence(
        lexical,
        semantic,
        authorized_sources=sample["authorized"],
        limit=2,
    )

    second = fuse_ranked_evidence(
        lexical,
        semantic,
        authorized_sources=sample["authorized"],
        limit=2,
    )

    assert first == second
    assert len(first) == 2

    for invalid_limit in (0, 51, True, -1):
        with pytest.raises(ValueError):
            fuse_ranked_evidence(
                lexical,
                semantic,
                authorized_sources=sample["authorized"],
                limit=invalid_limit,
            )
