
"""
ClaimLens AI - Contractual evidence dossier builder.

Combine SQL-authorized policy information with
hybrid documentary retrieval.

This module builds a structured evidence dossier.

It does NOT:
- decide insurance coverage
- approve or reject claims
- calculate indemnification
"""

import sqlite3

from backend.database.queries import get_policy_context
from backend.retrieval.hybrid import search_policy_hybrid
from backend.schemas import ContractualEvidenceDossier


def build_contractual_evidence_dossier(
    connection: sqlite3.Connection,
    policy_number: str,
    query: str,
    limit: int = 10,
) -> ContractualEvidenceDossier | None:
    """
    Build a structured evidence dossier for one policy.

    Return None when the policy does not exist.

    Security:
    - SQL authorization comes first.
    - Only the selected policy's documents are allowed.
    - Coverage records and evidence sources are checked.
    - Documentary references must match their PDF.
    - Duplicate retrieved evidence is rejected.

    The output organizes evidence, not claim decisions.
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError(
            "Search query cannot be empty"
        )

    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError(
            "Limit must be between 1 and 50"
        )

    # --------------------------------------------------
    # 1. SQL-first policy authorization
    # --------------------------------------------------

    context = get_policy_context(
        connection,
        policy_number,
    )

    if context is None:
        return None

    authorized_documents = {
        document["pdf_relative_path"]: document[
            "document_reference"
        ]
        for document in context["documents"]
    }

    if len(authorized_documents) != len(
        context["documents"]
    ):
        raise ValueError(
            "Duplicate authorized document sources"
        )

    # --------------------------------------------------
    # 2. Verify the SQL coverage sources
    # --------------------------------------------------

    for coverage in context["coverages"]:
        source_pdf = coverage["pdf_relative_path"]

        if source_pdf not in authorized_documents:
            raise ValueError(
                f"Unauthorized coverage source: {source_pdf}"
            )

        if coverage["document_reference"] != (
            authorized_documents[source_pdf]
        ):
            raise ValueError(
                "Inconsistent coverage document reference"
            )

    # --------------------------------------------------
    # 3. Retrieve evidence using the hybrid engine
    # --------------------------------------------------

    response = search_policy_hybrid(
        connection,
        policy_number,
        query,
        limit=limit,
    )

    if not response["policy_found"]:
        raise ValueError(
            "Policy authorization changed during retrieval"
        )

    if response["original_query"] != query:
        raise ValueError(
            "Unexpected original query in retrieval"
        )

    # --------------------------------------------------
    # 4. Verify each retrieved evidence item
    # --------------------------------------------------

    seen_evidence = set()

    for item in response["results"]:
        source_pdf = item["source_pdf"]
        evidence_id = item["evidence_id"]

        if source_pdf not in authorized_documents:
            raise ValueError(
                f"Unauthorized evidence source: {source_pdf}"
            )

        if item["document_reference"] != (
            authorized_documents[source_pdf]
        ):
            raise ValueError(
                "Inconsistent evidence document reference"
            )

        
        # Ensure the evidence identifier belongs to
        # its declared PDF source.
        #
        # Example:
        # source_pdf: contracts/contrat_B.pdf
        # evidence_id: contracts/contrat_B:t1:r6

        expected_evidence_prefix = (
            source_pdf.removesuffix(".pdf") + ":"
        )

        if (
            not isinstance(evidence_id, str)
            or not evidence_id.startswith(
                expected_evidence_prefix
            )
        ):
            raise ValueError(
                "Inconsistent evidence identity: "
                f"{evidence_id!r} does not belong "
                f"to {source_pdf!r}"
            )

        identity = (
            source_pdf,
            evidence_id,
        )

        if identity in seen_evidence:
            raise ValueError(
                f"Duplicate evidence: {identity}"
            )

        seen_evidence.add(identity)

    # --------------------------------------------------
    # 5. Build and validate the structured dossier
    # --------------------------------------------------

    dossier_data = {
        **context,
        "original_query": response["original_query"],
        "expanded_query": response["expanded_query"],
        "applied_rules": response["applied_rules"],
        "unverified_locations": response[
            "unverified_locations"
        ],
        "evidence": response["results"],
    }

    return ContractualEvidenceDossier.model_validate(
        dossier_data
    )
