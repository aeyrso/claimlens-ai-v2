
"""
ClaimLens AI - SQL-scoped retrieval regression tests.

Verify document isolation, lexical relevance,
table-cell provenance and input validation.
"""

import sqlite3

import pytest

from backend.database.importer import import_synthetic_corpus
from backend.database.queries import get_policy_context
from backend.retrieval.search import (
    load_authorized_export,
    search_policy_evidence,
)


@pytest.fixture
def database():
    """Create an isolated synthetic SQLite database."""

    connection = sqlite3.connect(":memory:")

    try:
        import_synthetic_corpus(connection)
        yield connection
    finally:
        connection.close()


def test_retrieval_respects_policy_document_scope(database):
    """No result may originate from another policy."""

    query = "vol de velo en local commun"

    for policy_number in (
        "SIM-A-0001",
        "SIM-B-0002",
        "SIM-C-0003",
    ):
        context = get_policy_context(database, policy_number)

        authorized_paths = {
            document["pdf_relative_path"]
            for document in context["documents"]
        }

        results = search_policy_evidence(
            database,
            policy_number,
            query,
            limit=50,
        )

        assert all(
            result["source_pdf"] in authorized_paths
            for result in results
        )


def test_bicycle_evidence_preserves_table_cells(database):
    """The bicycle risk must retain exact contractual values."""

    results = search_policy_evidence(
        database,
        "SIM-B-0002",
        "vol de velo en local commun",
        limit=10,
    )

    assert results

    strongest = results[0]

    assert strongest["evidence_type"] == "table_row"
    assert strongest["source_pdf"] == (
        "contracts/contrat_B_mobilite_habitation.pdf"
    )
    assert strongest["document_reference"] == "HAB-B-CG-2026"
    assert strongest["page_number"] == 1
    assert strongest["score"] == 4

    cells = {
        cell["column_header"]: cell["value"]
        for cell in strongest["cells"]
    }

    assert cells["Risque"] == (
        "Vol de v\u00e9lo en local commun"
    )
    assert cells["Plafond EUR"] == "2 000"
    assert cells["Franchise EUR"] == "100"
    assert cells["Module"] == "MOBILIT\u00c9+"

    assert len(strongest["cells"]) == 5

    for index, cell in enumerate(strongest["cells"]):
        location = cell["location"]

        assert location["page_number"] == 1
        assert location["column_index"] == index
        assert len(location["bbox"]) == 4
        assert location["coord_origin"] in {
            "TOPLEFT",
            "BOTTOMLEFT",
        }


def test_search_ranking_and_limit_are_deterministic(database):
    """Same query and policy must produce stable ranking."""

    arguments = (
        database,
        "SIM-B-0002",
        "vol de velo en local commun",
    )

    all_results = search_policy_evidence(
        *arguments,
        limit=50,
    )

    top_three = search_policy_evidence(
        *arguments,
        limit=3,
    )

    assert len(top_three) == 3
    assert top_three == all_results[:3]

    scores = [
        result["score"]
        for result in all_results
    ]

    assert scores == sorted(scores, reverse=True)


def test_unknown_policy_and_invalid_inputs(database):
    """Unknown policies return nothing; invalid queries fail."""

    assert search_policy_evidence(
        database,
        "SIM-UNKNOWN",
        "vol de velo",
    ) == []

    with pytest.raises(ValueError):
        search_policy_evidence(
            database,
            "SIM-B-0002",
            "",
        )

    with pytest.raises(ValueError):
        search_policy_evidence(
            database,
            "SIM-B-0002",
            "de la et",
        )

    for invalid_limit in (0, 51, True):
        with pytest.raises(ValueError):
            search_policy_evidence(
                database,
                "SIM-B-0002",
                "velo",
                limit=invalid_limit,
            )


def test_retrieval_rejects_path_traversal():
    """Document loading must reject paths outside the corpus."""

    with pytest.raises(ValueError):
        load_authorized_export(
            "../outside.pdf"
        )

    with pytest.raises(ValueError):
        load_authorized_export(
            "contracts/../../outside.pdf"
        )


@pytest.mark.parametrize(
    ("query", "preferred_risk", "opposite_risk"),
    [
        (
            "vol de velo en local commun",
            "Vol de v\u00e9lo en local commun",
            "Vol de v\u00e9lo sur voie publique",
        ),
        (
            "vol de velo sur voie publique",
            "Vol de v\u00e9lo sur voie publique",
            "Vol de v\u00e9lo en local commun",
        ),
    ],
)
def test_contextual_ranking_prioritizes_requested_location(
    database,
    query,
    preferred_risk,
    opposite_risk,
):
    """A requested location must outrank the opposite location."""

    results = search_policy_evidence(
        database,
        "SIM-B-0002",
        query,
        limit=50,
    )

    risk_rows = {}

    for rank, result in enumerate(results, start=1):
        if result["evidence_type"] != "table_row":
            continue

        cells = {
            cell["column_header"]: cell["value"]
            for cell in result["cells"]
        }

        risk = cells.get("Risque")

        if risk is not None:
            risk_rows[risk] = (rank, result)

    assert preferred_risk in risk_rows
    assert opposite_risk in risk_rows

    preferred_rank, preferred = risk_rows[preferred_risk]
    opposite_rank, opposite = risk_rows[opposite_risk]

    assert preferred_rank == 1
    assert preferred_rank < opposite_rank

    assert preferred["score"] == 4
    assert opposite["score"] == 0


def test_ambiguous_bicycle_query_keeps_both_locations(database):
    """An unspecified location must not be inferred."""

    results = search_policy_evidence(
        database,
        "SIM-B-0002",
        "vol de velo",
        limit=50,
    )

    risks = {}

    for rank, result in enumerate(results, start=1):
        if result["evidence_type"] != "table_row":
            continue

        cells = {
            cell["column_header"]: cell["value"]
            for cell in result["cells"]
        }

        risk = cells.get("Risque")

        if risk in {
            "Vol de v\u00e9lo en local commun",
            "Vol de v\u00e9lo sur voie publique",
        }:
            risks[risk] = {
                "rank": rank,
                "score": result["score"],
            }

    assert len(risks) == 2

    assert risks["Vol de v\u00e9lo en local commun"] == {
        "rank": 1,
        "score": 2,
    }

    assert risks["Vol de v\u00e9lo sur voie publique"] == {
        "rank": 2,
        "score": 2,
    }


def test_compound_phrase_avoids_public_warning(database):
    """
    'Voie publique' must not match an isolated
    occurrence of 'publique' in a document warning.
    """

    queries = [
        "voie publique",
        "vol de velo sur voie publique",
    ]

    for query in queries:
        results = search_policy_evidence(
            database,
            "SIM-B-0002",
            query,
            limit=50,
        )

        assert results

        # The documentary disclaimer must not match.
        false_positives = [
            result
            for result in results
            if "document original fictif"
            in result["text"].casefold()
            and "monstration publique"
            in result["text"].casefold()
        ]

        assert false_positives == []

        # The relevant contractual risk must remain.
        matching_risks = [
            cell["value"]
            for result in results
            if result["evidence_type"] == "table_row"
            for cell in result["cells"]
            if cell["column_header"] == "Risque"
        ]

        assert (
            "Vol de v\u00e9lo sur voie publique"
            in matching_risks
        )


def test_ete_auxiliary_is_ignored_but_season_is_retained():
    """
    Ignore 'ete' when it is used as a verbal auxiliary.

    Preserve 'ete' when it refers to the summer season.

    The normalization function must remain unchanged.
    """

    from backend.retrieval.search import (
        tokenize,
        normalize_phrase,
    )

    auxiliary_cases = (
        "Ma baie vitree a ete heurtee par un objet.",
        "Ce document a ete redige pour une simulation.",
        "Les biens ont ete voles.",
        "Le logement avait ete endommage.",
        "Le dossier peut avoir ete modifie.",
        "J'ai ete victime d'un vol.",
    )

    seasonal_cases = (
        "Les dommages sont survenus en ete.",
        "La garantie est active cet ete.",
        "La tempete a eu lieu pendant l'ete.",
        "Un sinistre a ete declare cet ete.",
    )

    for phrase in auxiliary_cases:
        tokens = tokenize(phrase)

        assert "ete" not in tokens, (
            f"Auxiliary was not filtered: {phrase}"
        )

    for phrase in seasonal_cases:
        tokens = tokenize(phrase)

        assert "ete" in tokens, (
            f"Seasonal information was lost: {phrase}"
        )

    # Phrase normalization must preserve the original
    # normalized wording for contractual equivalences.
    assert normalize_phrase("a été") == "a ete"

    # Other meaningful lexical terms must survive.
    assert "vitree" in tokenize(
        "Ma baie vitree a ete heurtee."
    )

    assert "sinistre" in tokenize(
        "Le sinistre est survenu cet ete."
    )
