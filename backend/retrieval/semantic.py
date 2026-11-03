
"""
ClaimLens AI - SQL-scoped semantic evidence retrieval.

Retrieve all evidence from the documents authorized by SQL,
then rank it using multilingual E5 embeddings.

This module retrieves evidence; it does not determine
whether an insurance claim is covered.
"""

import sqlite3

from backend.database.queries import get_policy_context
from backend.retrieval.embeddings import encode_texts
from backend.retrieval.search import load_authorized_export


def collect_authorized_evidence(
    connection: sqlite3.Connection,
    policy_number: str,
) -> list[dict]:
    """
    Collect evidence from SQL-authorized documents only.

    Preserve source PDFs, pages, bounding boxes,
    document references and individual table cells.
    """

    # SQL-first: never open JSON files before authorization.
    context = get_policy_context(
        connection,
        policy_number,
    )

    if context is None:
        return []

    evidence = []

    for document in context["documents"]:
        source_pdf = document["pdf_relative_path"]
        document_reference = document["document_reference"]

        data = load_authorized_export(source_pdf)

        # Ordinary text elements.
        for element in data["text_elements"]:
            text = element["text"]

            if not text.strip():
                continue

            locations = element["locations"]

            if not locations:
                raise ValueError(
                    f"Missing text provenance: "
                    f"{element['element_id']}"
                )

            evidence.append(
                {
                    "evidence_id": element["element_id"],
                    "evidence_type": "text",
                    "source_pdf": source_pdf,
                    "document_reference": document_reference,
                    "text": text,
                    "score": 0.0,
                    "semantic_score": 0.0,
                    "matched_terms": [],
                    "page_number": locations[0]["page_number"],
                    "locations": locations,
                    "cells": [],
                }
            )

        # Complete table rows with cell-level provenance.
        for row in data["table_rows"]:
            text = row["row_serialized"]

            if not text.strip():
                continue

            headers = row["column_headers"]
            values = row["row_cells"]
            locations = row["cell_locations"]

            if not (
                len(headers)
                == len(values)
                == len(locations)
            ) or not locations:
                raise ValueError(
                    f"Inconsistent table row: "
                    f"{row['table_id']}"
                )

            cells = []

            for header, value, location in zip(
                headers,
                values,
                locations,
                strict=True,
            ):
                cells.append(
                    {
                        "column_header": header,
                        "value": value,
                        "location": {
                            "page_number": row["page_number"],
                            "column_index": location[
                                "column_index"
                            ],
                            "bbox": location["bbox"],
                            "coord_origin": location[
                                "coord_origin"
                            ],
                        },
                    }
                )

            evidence.append(
                {
                    "evidence_id": (
                        f"{row['table_id']}:"
                        f"r{row['row_index']}"
                    ),
                    "evidence_type": "table_row",
                    "source_pdf": source_pdf,
                    "document_reference": document_reference,
                    "text": text,
                    "score": 0.0,
                    "semantic_score": 0.0,
                    "matched_terms": [],
                    "page_number": row["page_number"],
                    "locations": [
                        cell["location"]
                        for cell in cells
                    ],
                    "cells": cells,
                }
            )

    return evidence


def search_policy_semantic(
    connection: sqlite3.Connection,
    policy_number: str,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """
    Rank authorized evidence by semantic similarity.

    The embeddings are computed only after SQL
    has restricted the documentary scope.

    Similarity is not a coverage probability.
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError("Search query cannot be empty")

    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= 50
    ):
        raise ValueError("Limit must be between 1 and 50")

    evidence = collect_authorized_evidence(
        connection,
        policy_number,
    )

    if not evidence:
        return []

    # Encode the user's question.
    query_vector = encode_texts(
        [query],
        role="query",
    )[0]

    # Encode only evidence belonging to the selected policy.
    passage_vectors = encode_texts(
        [item["text"] for item in evidence],
        role="passage",
    )

    # Embeddings are normalized: dot product = cosine similarity.
    similarities = passage_vectors @ query_vector

    for item, similarity in zip(
        evidence,
        similarities,
        strict=True,
    ):
        score = float(similarity)

        item["semantic_score"] = score
        item["score"] = score

    # Deterministic ranking.
    evidence.sort(
        key=lambda item: (
            -item["semantic_score"],
            item["evidence_type"] != "table_row",
            item["source_pdf"],
            item["page_number"],
            item["evidence_id"],
        )
    )

    return evidence[:limit]
