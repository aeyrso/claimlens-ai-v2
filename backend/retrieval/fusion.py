
"""
ClaimLens AI - Evidence ranking fusion.

Combine SQL-authorized lexical and semantic rankings
using weighted Reciprocal Rank Fusion (RRF).

Fusion scores measure retrieval priority.
They are NOT insurance coverage probabilities.
"""

LEXICAL_WEIGHT = 2.0
SEMANTIC_WEIGHT = 1.0
RRF_K = 60


def fuse_ranked_evidence(
    lexical_results: list[dict],
    semantic_results: list[dict],
    authorized_sources: set[str],
    limit: int = 10,
) -> list[dict]:
    """
    Fuse two rankings while preserving PDF provenance.

    Evidence identity: (source_pdf, evidence_id).

    The authorized_sources set must come from the
    SQL-selected policy context.

    Unauthorized sources raise an error.
    """

    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= 50
    ):
        raise ValueError(
            "Limit must be between 1 and 50"
        )

    if not authorized_sources:
        return []

    merged = {}

    rankings = [
        ("lexical", lexical_results, LEXICAL_WEIGHT),
        ("semantic", semantic_results, SEMANTIC_WEIGHT),
    ]

    for method, results, weight in rankings:
        seen_in_ranking = set()

        for rank, item in enumerate(results, start=1):
            source_pdf = item["source_pdf"]
            evidence_id = item["evidence_id"]

            if source_pdf not in authorized_sources:
                raise ValueError(
                    f"Unauthorized evidence source: {source_pdf}"
                )

            key = (source_pdf, evidence_id)

            if key in seen_in_ranking:
                raise ValueError(
                    f"Duplicate evidence in {method} ranking: {key}"
                )

            seen_in_ranking.add(key)

            if key not in merged:
                merged[key] = {
                    **item,
                    "score": 0.0,
                    "hybrid_score": 0.0,
                    "lexical_score": None,
                    "semantic_score": None,
                    "lexical_rank": None,
                    "semantic_rank": None,
                    "matched_terms": [],
                }

            candidate = merged[key]

            # Identical evidence IDs must refer to the
            # same documentary content and PDF page.
            if (
                candidate["text"] != item["text"]
                or candidate["page_number"]
                != item["page_number"]
                or candidate["evidence_type"]
                != item["evidence_type"]
            ):
                raise ValueError(
                    f"Inconsistent evidence provenance: {key}"
                )

            if method == "lexical":
                candidate["lexical_score"] = item["score"]
                candidate["lexical_rank"] = rank
                candidate["matched_terms"] = item[
                    "matched_terms"
                ]

            else:
                candidate["semantic_score"] = item[
                    "semantic_score"
                ]
                candidate["semantic_rank"] = rank

            # Weighted Reciprocal Rank Fusion.
            contribution = weight / (RRF_K + rank)

            candidate["hybrid_score"] += contribution
            candidate["score"] = candidate["hybrid_score"]

    fused = list(merged.values())

    fused.sort(
        key=lambda item: (
            -item["hybrid_score"],
            item["evidence_type"] != "table_row",
            item["source_pdf"],
            item["page_number"],
            item["evidence_id"],
        )
    )

    return fused[:limit]
