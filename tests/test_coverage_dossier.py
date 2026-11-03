
"""
ClaimLens AI - Contractual evidence dossier tests.

Verify SQL-first authorization, source isolation,
provenance consistency and dossier construction.

These tests use controlled retrieval responses
to exercise security and validation branches.

They do not determine insurance coverage.
"""

import copy
import sqlite3

import pytest

from backend.analysis import coverage as dossier_module
from backend.database.importer import import_synthetic_corpus
from backend.database.queries import get_policy_context
from backend.schemas import ContractualEvidenceDossier


POLICY = "SIM-B-0002"
QUERY = "Ma table de jardin a ete endommagee."


@pytest.fixture
def connection():
    """Create an isolated SQLite database."""

    db = sqlite3.connect(":memory:")

    try:
        import_synthetic_corpus(db)
        yield db
    finally:
        db.close()


@pytest.fixture
def policy_context(connection):
    """Retrieve the genuine SQL-authorized policy context."""

    context = get_policy_context(connection, POLICY)

    assert context is not None

    return context


@pytest.fixture
def hybrid_reply(monkeypatch, policy_context):
    """
    Mock only hybrid retrieval.

    SQL policy authorization remains real.
    """

    document = next(
        document
        for document in policy_context["documents"]
        if document["document_kind"] == "POLICY_SCHEDULE"
    )

    location = {
        "page_number": 1,
        "bbox": [64.0, 600.0, 95.0, 608.0],
        "coord_origin": "TOPLEFT",
        "column_index": 0,
    }

    evidence = {
        "evidence_id": (
            "policy_schedules/"
            "conditions_particulieres_B:t2:r4"
        ),
        "source_pdf": document["pdf_relative_path"],
        "document_reference": document[
            "document_reference"
        ],
        "evidence_type": "table_row",
        "text": (
            "Garantie / module: JARDIN+ | "
            "Statut: SOUSCRIT"
        ),
        "page_number": 1,
        "locations": [location],
        "cells": [
            {
                "column_header": "Statut",
                "value": "SOUSCRIT",
                "location": location,
            }
        ],
        "score": 0.047883,
        "hybrid_score": 0.047883,
        "lexical_score": 8.0,
        "semantic_score": 0.82,
        "lexical_rank": 1,
        "semantic_rank": 2,
        "matched_terms": ["jardin", "table"],
    }

    reply = {
        "policy_found": True,
        "original_query": QUERY,
        "expanded_query": (
            QUERY + " mobilier de jardin"
        ),
        "applied_rules": [],
        "unverified_locations": [],
        "results": [evidence],
    }

    def fake_hybrid_search(
        _connection,
        policy_number,
        query,
        limit=10,
    ):
        assert policy_number == POLICY
        assert query == QUERY
        assert limit == 10
        return reply

    monkeypatch.setattr(
        dossier_module,
        "search_policy_hybrid",
        fake_hybrid_search,
    )

    return reply


# --------------------------------------------------
# 1. Nominal dossier construction
# --------------------------------------------------

def test_dossier_preserves_policy_and_evidence(
    connection,
    hybrid_reply,
):
    """A valid dossier retains SQL and PDF information."""

    dossier = (
        dossier_module.build_contractual_evidence_dossier(
            connection,
            POLICY,
            QUERY,
        )
    )

    assert isinstance(
        dossier,
        ContractualEvidenceDossier,
    )

    assert dossier.policy.policy_number == POLICY
    assert len(dossier.documents) == 2
    assert len(dossier.coverages) == 4
    assert len(dossier.evidence) == 1

    evidence = dossier.evidence[0]

    assert evidence.evidence_id == (
        hybrid_reply["results"][0]["evidence_id"]
    )
    assert evidence.locations
    assert evidence.cells[0].value == "SOUSCRIT"

    assert dossier.expanded_query.endswith(
        " mobilier de jardin"
    )


# --------------------------------------------------
# 2. SQL-first authorization
# --------------------------------------------------

def test_unknown_policy_does_not_trigger_retrieval(
    connection,
    monkeypatch,
):
    """An unknown policy must not launch hybrid search."""

    def forbidden_search(*args, **kwargs):
        pytest.fail(
            "Retrieval was called for an unknown policy"
        )

    monkeypatch.setattr(
        dossier_module,
        "search_policy_hybrid",
        forbidden_search,
    )

    dossier = (
        dossier_module.build_contractual_evidence_dossier(
            connection,
            "POLICE-INCONNUE",
            QUERY,
        )
    )

    assert dossier is None


# --------------------------------------------------
# 3. Input validation
# --------------------------------------------------

@pytest.mark.parametrize(
    ("query", "limit"),
    [
        ("", 10),
        ("   ", 10),
        (QUERY, 0),
        (QUERY, 51),
        (QUERY, True),
    ],
)
def test_dossier_rejects_invalid_inputs(
    connection,
    query,
    limit,
):
    """Reject empty queries and invalid result limits."""

    with pytest.raises(ValueError):
        dossier_module.build_contractual_evidence_dossier(
            connection,
            POLICY,
            query,
            limit=limit,
        )


# --------------------------------------------------
# 4. Evidence authorization and consistency
# --------------------------------------------------

def test_dossier_rejects_unauthorized_evidence(
    connection,
    hybrid_reply,
):
    """Evidence from another policy must be rejected."""

    hybrid_reply["results"][0]["source_pdf"] = (
        "contracts/contrat_A_protection_essentielle.pdf"
    )

    with pytest.raises(
        ValueError,
        match="Unauthorized evidence source",
    ):
        dossier_module.build_contractual_evidence_dossier(
            connection,
            POLICY,
            QUERY,
        )


def test_dossier_rejects_wrong_evidence_reference(
    connection,
    hybrid_reply,
):
    """The evidence reference must match its PDF."""

    hybrid_reply["results"][0][
        "document_reference"
    ] = "REFERENCE-INCORRECTE"

    with pytest.raises(
        ValueError,
        match="Inconsistent evidence document reference",
    ):
        dossier_module.build_contractual_evidence_dossier(
            connection,
            POLICY,
            QUERY,
        )


def test_dossier_rejects_duplicate_evidence(
    connection,
    hybrid_reply,
):
    """The same PDF evidence cannot appear twice."""

    duplicate = copy.deepcopy(
        hybrid_reply["results"][0]
    )

    hybrid_reply["results"].append(duplicate)

    with pytest.raises(
        ValueError,
        match="Duplicate evidence",
    ):
        dossier_module.build_contractual_evidence_dossier(
            connection,
            POLICY,
            QUERY,
        )


# --------------------------------------------------
# 5. Coverage subscription source validation
# --------------------------------------------------

def test_dossier_rejects_unauthorized_coverage_source(
    connection,
    policy_context,
    hybrid_reply,
    monkeypatch,
):
    """Coverage sources must belong to the selected policy."""

    altered = copy.deepcopy(policy_context)

    altered["coverages"][0]["pdf_relative_path"] = (
        "contracts/contrat_A_protection_essentielle.pdf"
    )

    monkeypatch.setattr(
        dossier_module,
        "get_policy_context",
        lambda *_args: altered,
    )

    with pytest.raises(
        ValueError,
        match="Unauthorized coverage source",
    ):
        dossier_module.build_contractual_evidence_dossier(
            connection,
            POLICY,
            QUERY,
        )


def test_dossier_rejects_wrong_coverage_reference(
    connection,
    policy_context,
    hybrid_reply,
    monkeypatch,
):
    """Coverage document references must remain consistent."""

    altered = copy.deepcopy(policy_context)

    altered["coverages"][0][
        "document_reference"
    ] = "REFERENCE-INCORRECTE"

    monkeypatch.setattr(
        dossier_module,
        "get_policy_context",
        lambda *_args: altered,
    )

    with pytest.raises(
        ValueError,
        match="Inconsistent coverage document reference",
    ):
        dossier_module.build_contractual_evidence_dossier(
            connection,
            POLICY,
            QUERY,
        )


# --------------------------------------------------
# 6. Duplicate authorized documents
# --------------------------------------------------

def test_dossier_rejects_duplicate_document_sources(
    connection,
    policy_context,
    hybrid_reply,
    monkeypatch,
):
    """Authorized PDF paths must be unique."""

    altered = copy.deepcopy(policy_context)

    altered["documents"][1]["pdf_relative_path"] = (
        altered["documents"][0]["pdf_relative_path"]
    )

    monkeypatch.setattr(
        dossier_module,
        "get_policy_context",
        lambda *_args: altered,
    )

    with pytest.raises(
        ValueError,
        match="Duplicate authorized document sources",
    ):
        dossier_module.build_contractual_evidence_dossier(
            connection,
            POLICY,
            QUERY,
        )


# --------------------------------------------------
# 7. Retrieval response integrity
# --------------------------------------------------

def test_dossier_rejects_authorization_change(
    connection,
    hybrid_reply,
):
    """Retrieval must not silently lose policy authorization."""

    hybrid_reply["policy_found"] = False

    with pytest.raises(
        ValueError,
        match="Policy authorization changed",
    ):
        dossier_module.build_contractual_evidence_dossier(
            connection,
            POLICY,
            QUERY,
        )


def test_dossier_rejects_modified_original_query(
    connection,
    hybrid_reply,
):
    """The original claim description must remain unchanged."""

    hybrid_reply["original_query"] = (
        "Une autre declaration"
    )

    with pytest.raises(
        ValueError,
        match="Unexpected original query",
    ):
        dossier_module.build_contractual_evidence_dossier(
            connection,
            POLICY,
            QUERY,
        )

# --------------------------------------------------
# 8. Evidence identity consistency
# --------------------------------------------------

def test_dossier_rejects_mismatched_evidence_identity(
    connection,
    hybrid_reply,
):
    """
    An evidence ID must belong to its declared PDF.

    An evidence ID from policy A cannot be
    presented as evidence from policy B.
    """

    hybrid_reply["results"][0]["evidence_id"] = (
        "contracts/contrat_A_protection_essentielle:t2:r1"
    )

    with pytest.raises(
        ValueError,
        match="Inconsistent evidence identity",
    ):
        dossier_module.build_contractual_evidence_dossier(
            connection,
            POLICY,
            QUERY,
        )
