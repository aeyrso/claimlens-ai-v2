
"""
ClaimLens AI - SQL-first hybrid evidence retrieval.

Combine:
1. SQL policy authorization
2. Controlled query expansion
3. Lexical contextual retrieval
4. Multilingual semantic retrieval
5. Weighted Reciprocal Rank Fusion

This module retrieves documentary evidence.
It does not decide insurance coverage.
"""

import sqlite3

from backend.database.queries import get_policy_context
from backend.retrieval.fusion import fuse_ranked_evidence
from backend.retrieval.query_expansion import (
    expand_policy_query,
)
from backend.retrieval.search import (
    search_policy_evidence,
    tokenize,
)
from backend.retrieval.semantic import (
    search_policy_semantic,
)


CANDIDATE_LIMIT = 50


def search_policy_hybrid(
    connection: sqlite3.Connection,
    policy_number: str,
    query: str,
    limit: int = 10,
) -> dict:
    """
    Retrieve and fuse evidence for one authorized policy.

    Return:
    - policy_found
    - original_query
    - expanded_query
    - applied_rules
    - unverified_locations
    - lexical_candidates
    - semantic_candidates
    - results

    Search scores are retrieval scores, not
    probabilities of insurance coverage.
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError(
            "Search query cannot be empty"
        )

    if not tokenize(query):
        raise ValueError(
            "Search query contains no searchable terms"
        )

    if (
        type(limit) is not int
        or not 1 <= limit <= 50
    ):
        raise ValueError(
            "Limit must be between 1 and 50"
        )

    response = {
        "policy_found": False,
        "original_query": query,
        "expanded_query": query,
        "applied_rules": [],
        "unverified_locations": [],
        "lexical_candidates": 0,
        "semantic_candidates": 0,
        "results": [],
    }

    # Step 1: authorize the policy using SQL.
    # No documentary evidence is read before this.
    context = get_policy_context(
        connection,
        policy_number,
    )

    if context is None:
        return response

    authorized_sources = {
        document["pdf_relative_path"]
        for document in context["documents"]
    }

    # Step 2: controlled expansion.
    # Contractual equivalences require documentary proof.
    expansion = expand_policy_query(
        connection,
        policy_number,
        query,
    )

    if not expansion["policy_found"]:
        raise ValueError(
            "Policy authorization changed during retrieval"
        )

    response["policy_found"] = True
    response["expanded_query"] = expansion[
        "expanded_query"
    ]
    response["applied_rules"] = expansion[
        "applied_rules"
    ]
    response["unverified_locations"] = expansion[
        "unverified_locations"
    ]

    # Step 3A: lexical search uses the enriched query.
    lexical_results = search_policy_evidence(
        connection,
        policy_number,
        expansion["expanded_query"],
        limit=CANDIDATE_LIMIT,
    )

    
    # Step 3B: semantic search uses controlled query expansion.
    # Expanded terms support retrieval only.
    # They must never be interpreted as new claim facts.
    semantic_results = search_policy_semantic(
        connection,
        policy_number,
        expansion["expanded_query"],
        limit=CANDIDATE_LIMIT,
    )


    # Step 4: combine ranks, not raw score scales.
    # Source authorization is checked again in fusion.
    fused_results = fuse_ranked_evidence(
        lexical_results,
        semantic_results,
        authorized_sources=authorized_sources,
        limit=limit,
    )

    response["lexical_candidates"] = len(
        lexical_results
    )
    response["semantic_candidates"] = len(
        semantic_results
    )
    response["results"] = fused_results

    return response
