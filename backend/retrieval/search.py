
"""
ClaimLens AI - SQL-scoped lexical evidence retrieval.

Search persisted structured JSON exports only after
SQL has identified the authorized policy documents.

This module retrieves evidence; it does not decide
whether an insurance claim is covered.
"""

import json
import re
import sqlite3
import unicodedata
from pathlib import Path

from backend.database.queries import get_policy_context


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARSED_ROOT = PROJECT_ROOT / "data" / "parsed"

STOPWORDS = {
    "a", "au", "aux", "avec", "ce", "ces",
    "dans", "de", "des", "du", "en", "est",
    "et", "la", "le", "les", "ou", "par",
    "pour", "que", "qui", "sur", "un", "une",
}



def tokenize(text: str) -> set[str]:
    """
    Normalize case and accents for lexical matching.

    Ignore 'ete' when used immediately after an
    auxiliary form of 'avoir', while preserving
    seasonal references such as 'cet ete'.

    Original evidence text is never modified.
    """

    normalized = unicodedata.normalize(
        "NFKD",
        text.casefold(),
    )

    normalized = "".join(
        char
        for char in normalized
        if not unicodedata.combining(char)
    )

    words = re.findall(
        r"[a-z0-9]+",
        normalized,
    )

    auxiliary_predecessors = {
        "ai",
        "as",
        "a",
        "avons",
        "avez",
        "ont",
        "avais",
        "avait",
        "avions",
        "aviez",
        "avaient",
        "aurai",
        "auras",
        "aura",
        "aurons",
        "aurez",
        "auront",
        "aurais",
        "aurait",
        "aurions",
        "auriez",
        "auraient",
        "avoir",
        "ayant",
    }

    tokens = set()

    for index, word in enumerate(words):
        if len(word) < 2 or word in STOPWORDS:
            continue

        # Ignore the verbal auxiliary in expressions
        # such as "a ete", "ont ete" or "avoir ete".
        if (
            word == "ete"
            and index > 0
            and words[index - 1] in auxiliary_predecessors
        ):
            continue

        tokens.add(word)

    return tokens


def normalize_phrase(text: str) -> str:
    """Normalize text for contextual phrase comparison."""

    normalized = unicodedata.normalize(
        "NFKD",
        text.casefold(),
    )

    normalized = "".join(
        char
        for char in normalized
        if not unicodedata.combining(char)
    )

    return " ".join(
        re.findall(r"[a-z0-9]+", normalized)
    )


def matching_query_terms(
    query_terms: set[str],
    query: str,
    evidence_text: str,
) -> set[str]:
    """
    Match query terms while respecting contextual expressions.

    For the phrase 'voie publique', isolated occurrences
    of 'voie' or 'publique' are not sufficient.
    """

    matched = query_terms & tokenize(evidence_text)

    requested = normalize_phrase(query)
    evidence = normalize_phrase(evidence_text)

    if (
        "voie publique" in requested
        and "voie publique" not in evidence
    ):
        matched.difference_update({"voie", "publique"})

    return matched


def context_penalty(query: str, evidence_text: str) -> int:
    """
    Penalize evidence describing an explicitly different location.

    Do not penalize evidence discussing both locations.
    Do not infer a location when the query is ambiguous.
    """

    requested = normalize_phrase(query)
    evidence = normalize_phrase(evidence_text)

    local = "local commun"
    street = "voie publique"

    if (
        local in requested
        and street not in requested
        and street in evidence
        and local not in evidence
    ):
        return 2

    if (
        street in requested
        and local not in requested
        and local in evidence
        and street not in evidence
    ):
        return 2

    return 0

def load_authorized_export(
    pdf_relative_path: str,
) -> dict:
    """
    Read one structured export from the parsed-data folder.

    Reject paths outside that folder and mismatched sources.
    """

    relative = Path(pdf_relative_path)

    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.suffix.lower() != ".pdf"
    ):
        raise ValueError(
            f"Invalid PDF relative path: {pdf_relative_path}"
        )

    root = PARSED_ROOT.resolve()

    json_path = (
        root / relative
    ).with_suffix(".json").resolve()

    if not json_path.is_relative_to(root):
        raise ValueError(
            f"JSON path outside parsed data: {json_path}"
        )

    data = json.loads(
        json_path.read_text(encoding="utf-8")
    )

    if data.get("source_pdf") != relative.as_posix():
        raise ValueError(
            f"Source mismatch in {json_path}"
        )

    return data


def search_policy_evidence(
    connection: sqlite3.Connection,
    policy_number: str,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """
    Retrieve lexical evidence from one policy only.

    SQL determines which documents may be searched.
    Each result retains its PDF source and locations.

    Unknown policies return no evidence.
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError("Search query cannot be empty")

    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= 50
    ):
        raise ValueError("Limit must be between 1 and 50")

    query_terms = tokenize(query)

    if not query_terms:
        raise ValueError(
            "Search query contains no searchable terms"
        )
    
    # Ignore low-information words for lexical ranking
    # when the query also contains more specific terms.
    #
    # These words remain in the original query and
    # continue to be available to semantic retrieval.
    low_information_terms = {
        "couvert",
        "couverte",
        "couverts",
        "couvertes",
        "etait",
        "sous",
    }

    informative_terms = query_terms - low_information_terms

    if informative_terms:
        query_terms = informative_terms


    # SQL-first: select the policy before opening any JSON.
    context = get_policy_context(
        connection,
        policy_number,
    )

    if context is None:
        return []

    results = []

    for authorized_document in context["documents"]:
        source_pdf = authorized_document[
            "pdf_relative_path"
        ]

        data = load_authorized_export(source_pdf)

        # 1. Search ordinary text with page-level provenance.
        for element in data["text_elements"]:
            text = element["text"]
            matched = matching_query_terms(query_terms, query, text)

            if not matched:
                continue

            locations = element["locations"]

            if not locations:
                raise ValueError(
                    f"Missing text provenance: "
                    f"{element['element_id']}"
                )

            results.append(
                {
                    "evidence_id": element["element_id"],
                    "evidence_type": "text",
                    "source_pdf": source_pdf,
                    "document_reference": authorized_document[
                        "document_reference"
                    ],
                    "text": text,
                    "score": max(
                        0,
                        len(matched) - context_penalty(query, text),
                    ),
                    "matched_terms": sorted(matched),
                    "page_number": locations[0][
                        "page_number"
                    ],
                    "locations": locations,
                    "cells": [],
                }
            )

        # 2. Search complete table rows.
        for row in data["table_rows"]:
            text = row["row_serialized"]
            matched = matching_query_terms(query_terms, query, text)

            if not matched:
                continue

            headers = row["column_headers"]
            values = row["row_cells"]
            locations = row["cell_locations"]

            if not (
                len(headers)
                == len(values)
                == len(locations)
            ):
                raise ValueError(
                    f"Inconsistent table row: "
                    f"{row['table_id']}"
                )

            # Preserve individual cells for exact citations.
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

            results.append(
                {
                    "evidence_id": (
                        f"{row['table_id']}:"
                        f"r{row['row_index']}"
                    ),
                    "evidence_type": "table_row",
                    "source_pdf": source_pdf,
                    "document_reference": authorized_document[
                        "document_reference"
                    ],
                    "text": text,
                    "score": max(
                        0,
                        len(matched) - context_penalty(query, text),
                    ),
                    "matched_terms": sorted(matched),
                    "page_number": row["page_number"],
                    "locations": [
                        cell["location"]
                        for cell in cells
                    ],
                    "cells": cells,
                }
            )

    # Deterministic ranking: more matching terms first.
    results.sort(
        key=lambda result: (
            -result["score"],
            result["evidence_type"] != "table_row",
            result["source_pdf"],
            result["page_number"],
            result["evidence_id"],
        )
    )

    return results[:limit]
