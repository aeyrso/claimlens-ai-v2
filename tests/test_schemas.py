
"""
ClaimLens AI - Structured evidence schema tests.

Validate PDF locations, table cells, and hybrid
retrieval evidence using Pydantic.

These tests check data structure and provenance.
They do not determine insurance coverage.
"""

import pytest

from pydantic import ValidationError

from backend.schemas import (
    EvidenceLocation,
    EvidenceCell,
    RetrievedEvidence,
)


@pytest.fixture
def raw_location():
    """A representative Docling PDF location."""

    return {
        "page_number": 1,
        "bbox": [64.0, 600.0, 95.0, 608.0],
        "coord_origin": "TOPLEFT",
        "column_index": 0,
    }


@pytest.fixture
def raw_evidence(raw_location):
    """A representative hybrid retrieval result."""

    return {
        "evidence_id": (
            "policy_schedules/"
            "conditions_particulieres_B:t2:r4"
        ),
        "source_pdf": (
            "policy_schedules/"
            "conditions_particulieres_B.pdf"
        ),
        "document_reference": "SIM-B-0002",
        "evidence_type": "table_row",
        "text": (
            "Garantie / module: JARDIN+ | "
            "Statut: SOUSCRIT"
        ),
        "page_number": 1,
        "locations": [raw_location],
        "cells": [
            {
                "column_header": "Statut",
                "value": "SOUSCRIT",
                "location": raw_location,
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


# --------------------------------------------------
# 1. PDF location validation
# --------------------------------------------------

def test_location_preserves_pdf_coordinates(raw_location):
    """Valid PDF coordinates must be retained."""

    location = EvidenceLocation.model_validate(
        raw_location
    )

    assert location.page_number == 1
    assert location.coord_origin == "TOPLEFT"
    assert location.column_index == 0
    assert location.bbox == (
        64.0,
        600.0,
        95.0,
        608.0,
    )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("page_number", 0),
        ("bbox", [10.0, 20.0, 30.0]),
        ("coord_origin", "CENTER"),
    ],
)
def test_location_rejects_invalid_structure(
    raw_location,
    field,
    invalid_value,
):
    """Reject invalid pages, box shapes and origins."""

    invalid = {
        **raw_location,
        field: invalid_value,
    }

    with pytest.raises(ValidationError):
        EvidenceLocation.model_validate(invalid)


# --------------------------------------------------
# 2. Contractual table cell validation
# --------------------------------------------------

def test_cell_preserves_value_and_pdf_location(
    raw_location,
):
    """A table cell retains its content and location."""

    cell = EvidenceCell.model_validate(
        {
            "column_header": "Statut",
            "value": "SOUSCRIT",
            "location": raw_location,
        }
    )

    assert cell.column_header == "Statut"
    assert cell.value == "SOUSCRIT"

    assert cell.location.page_number == 1
    assert cell.location.coord_origin == "TOPLEFT"


def test_cell_requires_pdf_location():
    """A contractual cell must have provenance."""

    invalid_cell = {
        "column_header": "Statut",
        "value": "SOUSCRIT",
    }

    with pytest.raises(ValidationError):
        EvidenceCell.model_validate(
            invalid_cell
        )


# --------------------------------------------------
# 3. Complete retrieval evidence validation
# --------------------------------------------------

def test_retrieved_evidence_preserves_metadata(
    raw_evidence,
):
    """
    Preserve identity, PDF provenance, table cells,
    retrieval scores and original ranking metadata.
    """

    evidence = RetrievedEvidence.model_validate(
        raw_evidence
    )

    assert evidence.evidence_id == (
        raw_evidence["evidence_id"]
    )

    assert evidence.source_pdf == (
        raw_evidence["source_pdf"]
    )

    assert evidence.page_number == 1
    assert evidence.evidence_type == "table_row"

    assert evidence.locations
    assert evidence.cells

    assert evidence.cells[0].value == "SOUSCRIT"
    assert evidence.cells[0].location.page_number == 1

    assert evidence.hybrid_score == 0.047883
    assert evidence.lexical_rank == 1
    assert evidence.semantic_rank == 2

    assert evidence.matched_terms == [
        "jardin",
        "table",
    ]


@pytest.mark.parametrize(
    "missing_field",
    [
        "evidence_id",
        "source_pdf",
        "document_reference",
    ],
)
def test_retrieved_evidence_requires_identity(
    raw_evidence,
    missing_field,
):
    """Evidence must have its documentary identity."""

    invalid = {
        key: value
        for key, value in raw_evidence.items()
        if key != missing_field
    }

    with pytest.raises(ValidationError):
        RetrievedEvidence.model_validate(
            invalid
        )


@pytest.mark.parametrize(
    "rank_field",
    [
        "lexical_rank",
        "semantic_rank",
    ],
)
def test_retrieved_evidence_rejects_invalid_rank(
    raw_evidence,
    rank_field,
):
    """Retrieval ranks must start at one."""

    invalid = {
        **raw_evidence,
        rank_field: 0,
    }

    with pytest.raises(ValidationError):
        RetrievedEvidence.model_validate(
            invalid
        )


def test_text_evidence_allows_empty_cell_list(
    raw_evidence,
):
    """
    Plain text evidence does not require table cells.
    PDF page and documentary identity remain required.
    """

    text_evidence = {
        **raw_evidence,
        "evidence_type": "text",
        "cells": [],
    }

    evidence = RetrievedEvidence.model_validate(
        text_evidence
    )

    assert evidence.evidence_type == "text"
    assert evidence.cells == []

    assert evidence.source_pdf
    assert evidence.evidence_id
    assert evidence.page_number == 1


@pytest.mark.parametrize(
    "score_field",
    [
        "score",
        "hybrid_score",
        "lexical_score",
        "semantic_score",
    ],
)
@pytest.mark.parametrize(
    "invalid_score",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_retrieved_evidence_rejects_nonfinite_scores(
    raw_evidence,
    score_field,
    invalid_score,
):
    """
    Retrieval scores must always be finite numbers.

    Reject NaN, positive infinity and negative infinity
    for every mandatory or optional retrieval score.
    """

    invalid = {
        **raw_evidence,
        score_field: invalid_score,
    }

    with pytest.raises(ValidationError):
        RetrievedEvidence.model_validate(invalid)


@pytest.mark.parametrize(
    "invalid_coordinate",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
@pytest.mark.parametrize(
    "coordinate_index",
    [0, 1, 2, 3],
)
def test_location_rejects_nonfinite_bbox(
    raw_location,
    coordinate_index,
    invalid_coordinate,
):
    """
    Reject nonfinite PDF bounding-box coordinates.

    Every coordinate must be a finite number.
    """

    invalid_bbox = list(raw_location["bbox"])
    invalid_bbox[coordinate_index] = invalid_coordinate

    invalid_location = {
        **raw_location,
        "bbox": invalid_bbox,
    }

    with pytest.raises(ValidationError):
        EvidenceLocation.model_validate(
            invalid_location
        )
