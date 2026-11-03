
"""
ClaimLens AI - End-to-end hybrid retrieval tests.

Verify SQL-first authorization, controlled expansion,
RRF ranking, and PDF provenance on synthetic claims.

Retrieval results are not coverage decisions.
"""

import sqlite3

import pytest

from backend.database.importer import import_synthetic_corpus
from backend.database.queries import get_policy_context
from backend.retrieval.hybrid import search_policy_hybrid


POLICY = "SIM-B-0002"

SCENARIOS = {
    "garage": (
        "On m'a pris ma bicyclette dans le "
        "garage collectif de mon immeuble."
    ),
    "trottoir": (
        "On m'a vole mon velo attache dehors "
        "sur le trottoir."
    ),
    "unknown": (
        "Mon velo a disparu, je ne sais pas ou."
    ),
}


@pytest.fixture(scope="module")
def hybrid_samples():
    """Run the real hybrid engine once per scenario."""

    connection = sqlite3.connect(":memory:")

    try:
        import_synthetic_corpus(connection)

        context = get_policy_context(
            connection,
            POLICY,
        )

        assert context is not None

        authorized = {
            doc["pdf_relative_path"]
            for doc in context["documents"]
        }

        responses = {
            name: search_policy_hybrid(
                connection,
                POLICY,
                query,
                limit=10,
            )
            for name, query in SCENARIOS.items()
        }

        return authorized, responses

    finally:
        connection.close()


def find_risk_rank(results, expected_risk):
    """Find the position of an exact contractual risk."""

    for rank, item in enumerate(results, start=1):
        if item["evidence_type"] != "table_row":
            continue

        cells = {
            cell["column_header"]: cell["value"]
            for cell in item["cells"]
        }

        if cells.get("Risque") == expected_risk:
            return rank

    return None


LOCAL_RISK = "Vol de v\u00e9lo en local commun"
STREET_RISK = "Vol de v\u00e9lo sur voie publique"


def test_hybrid_preserves_sql_scope_and_provenance(
    hybrid_samples,
):
    """All retrieved results must retain authorized citations."""

    authorized, responses = hybrid_samples

    assert len(authorized) == 2

    for response in responses.values():
        assert response["policy_found"] is True
        assert response["lexical_candidates"] > 0
        assert response["semantic_candidates"] > 0
        assert response["results"]

        scores = [
            item["hybrid_score"]
            for item in response["results"]
        ]

        assert scores == sorted(scores, reverse=True)

        for item in response["results"]:
            assert item["source_pdf"] in authorized
            assert item["document_reference"]
            assert item["locations"]
            assert item["page_number"] >= 1

            if item["evidence_type"] == "table_row":
                assert item["cells"]

                for cell in item["cells"]:
                    assert cell["location"]["bbox"] is not None


def test_garage_collectif_remains_unverified(
    hybrid_samples,
):
    """Find bicycle clauses without classifying the garage."""

    _, responses = hybrid_samples
    response = responses["garage"]

    assert "garage collectif" in response[
        "unverified_locations"
    ]

    assert "local commun" not in response[
        "expanded_query"
    ]

    local_rank = find_risk_rank(
        response["results"],
        LOCAL_RISK,
    )

    street_rank = find_risk_rank(
        response["results"],
        STREET_RISK,
    )

    assert local_rank is not None
    assert street_rank is not None
    assert local_rank < street_rank


def test_trottoir_does_not_establish_public_status(
    hybrid_samples,
):
    """The street clause may rank first without proving location."""

    _, responses = hybrid_samples
    response = responses["trottoir"]

    assert "trottoir" in response[
        "unverified_locations"
    ]

    assert "voie publique" not in response[
        "expanded_query"
    ]

    local_rank = find_risk_rank(
        response["results"],
        LOCAL_RISK,
    )

    street_rank = find_risk_rank(
        response["results"],
        STREET_RISK,
    )

    assert local_rank is not None
    assert street_rank is not None
    assert street_rank < local_rank


def test_unknown_location_preserves_both_clauses(
    hybrid_samples,
):
    """Missing location must not produce an invented location."""

    _, responses = hybrid_samples
    response = responses["unknown"]

    assert response["original_query"] == (
        response["expanded_query"]
    )

    assert response["applied_rules"] == []

    assert find_risk_rank(
        response["results"],
        LOCAL_RISK,
    ) is not None

    assert find_risk_rank(
        response["results"],
        STREET_RISK,
    ) is not None


def test_unknown_policy_does_not_launch_retrieval(
    monkeypatch,
):
    """Authorization failure must stop all retrieval engines."""

    connection = sqlite3.connect(":memory:")

    try:
        import_synthetic_corpus(connection)

        def forbidden(*args, **kwargs):
            raise AssertionError(
                "No retrieval allowed for an unknown policy"
            )

        monkeypatch.setattr(
            "backend.retrieval.hybrid.search_policy_evidence",
            forbidden,
        )

        monkeypatch.setattr(
            "backend.retrieval.hybrid.search_policy_semantic",
            forbidden,
        )

        monkeypatch.setattr(
            "backend.retrieval.hybrid.expand_policy_query",
            forbidden,
        )

        result = search_policy_hybrid(
            connection,
            "POLICE-INCONNUE",
            "Vol de velo",
        )

        assert result["policy_found"] is False
        assert result["results"] == []
        assert result["lexical_candidates"] == 0
        assert result["semantic_candidates"] == 0

    finally:
        connection.close()


def test_hybrid_rejects_invalid_inputs():
    """Invalid requests must fail before searching documents."""

    connection = sqlite3.connect(":memory:")

    try:
        for query in ("", "   ", None, "la et"):
            with pytest.raises(ValueError):
                search_policy_hybrid(
                    connection,
                    POLICY,
                    query,
                )

        for limit in (0, 51, True, -1):
            with pytest.raises(ValueError):
                search_policy_hybrid(
                    connection,
                    POLICY,
                    "Vol de velo",
                    limit=limit,
                )

    finally:
        connection.close()
