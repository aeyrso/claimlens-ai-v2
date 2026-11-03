
"""
ClaimLens AI - Verifiable PDF citation tests.

Validate table-cell citations and reclassified warning
text using the PyPdfium Docling backend.
"""

import json
import unicodedata
from pathlib import Path

import pymupdf

from backend.analysis.citations import (
    docling_bbox_to_pymupdf_rect,
)
from backend.ingestion.docling_factory import (
    create_document_converter,
)


DATA_ROOT = Path(__file__).resolve().parents[1] / "data"

WARNING_LEFT = (
    "Document original fictif, aucune compagnie réelle"
)

WARNING_RIGHT = (
    "Démonstration publique, ingestion RAG, partage "
    "et redistribution dans le cadre du projet"
)


def normalize_citation_text(text: str) -> str:
    """Normalize typography without removing meaningful content."""

    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u2019", "'")
    text = text.replace("\u2018", "'")

    return " ".join(text.split()).casefold()


def extract_text_at_location(page, bbox) -> str:
    """Retrieve original PDF text at a Docling location."""

    rect = docling_bbox_to_pymupdf_rect(bbox, page)

    padded_rect = pymupdf.Rect(
        rect.x0 - 1,
        rect.y0 - 1,
        rect.x1 + 1,
        rect.y1 + 1,
    ) & page.rect

    return page.get_text("text", clip=padded_rect)


def test_table_cells_match_original_pdf():
    manifest = json.loads(
        (DATA_ROOT / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    converter = create_document_converter()

    verified_cells = 0
    verified_warning_rectangles = 0

    for entry in manifest["files"]:
        pdf_path = DATA_ROOT / entry["relative_path"]

        document = converter.convert(str(pdf_path)).document

        with pymupdf.open(str(pdf_path)) as pdf:

            # 1. Verify every data cell in the detected tables.
            for table_index, table in enumerate(
                document.tables, start=1
            ):
                pages = {p.page_no for p in table.prov}

                assert len(pages) == 1, (
                    f"Unsupported multipage table: {pdf_path.name}"
                )

                page = pdf[next(iter(pages)) - 1]

                for cell in table.data.table_cells:

                    if cell.start_row_offset_idx == 0:
                        continue

                    assert cell.bbox is not None

                    original_text = extract_text_at_location(
                        page, cell.bbox
                    )

                    expected = normalize_citation_text(
                        cell.text
                    )
                    actual = normalize_citation_text(
                        original_text
                    )

                    assert expected == actual, (
                        f"Citation mismatch: {pdf_path.name}, "
                        f"table {table_index}, "
                        f"row {cell.start_row_offset_idx}, "
                        f"column {cell.start_col_offset_idx}: "
                        f"Docling={cell.text!r}, "
                        f"PDF={original_text!r}"
                    )

                    verified_cells += 1

            # 2. Verify warnings reclassified as text by PyPdfium.
            if pdf_path.name != "contrat_A_protection_essentielle.pdf":

                matches = [
                    item for item, _ in document.iterate_items()
                    if "document original fictif" in
                    normalize_citation_text(
                        getattr(item, "text", "") or ""
                    )
                ]

                assert len(matches) == 1, (
                    f"Warning element missing or duplicated: "
                    f"{pdf_path.name}"
                )

                warning = matches[0]

                assert len(warning.prov) == 2, (
                    f"Expected two warning locations: "
                    f"{pdf_path.name}"
                )

                locations = sorted(
                    warning.prov,
                    key=lambda p: p.bbox.as_tuple()[0],
                )

                expected_texts = [
                    WARNING_LEFT,
                    WARNING_RIGHT,
                ]

                for provenance, expected_text in zip(
                    locations, expected_texts
                ):
                    assert provenance.bbox is not None
                    assert provenance.page_no == 1

                    page = pdf[provenance.page_no - 1]

                    original_text = extract_text_at_location(
                        page, provenance.bbox
                    )

                    assert (
                        normalize_citation_text(original_text)
                        == normalize_citation_text(expected_text)
                    ), (
                        f"Warning citation mismatch: "
                        f"{pdf_path.name}, "
                        f"expected={expected_text!r}, "
                        f"actual={original_text!r}"
                    )

                    verified_warning_rectangles += 1

    # Preserve all previously verified citation locations.
    assert verified_cells == 184
    assert verified_warning_rectangles == 10


def test_api_evidence_location_matches_original_pdf():
    """
    Verify that API evidence coordinates identify
    the correct text in the original PDF.
    """

    from backend.analysis import citations
    from backend.schemas import EvidenceLocation

    pdf_path = (
        DATA_ROOT
        / "contracts"
        / "contrat_B_mobilite_habitation.pdf"
    )

    # Genuine coordinates returned by the RAG API.
    location = EvidenceLocation(
        page_number=2,
        bbox=(
            57.780521392822266,
            352.7746887207031,
            531.5479125976562,
            389.53558349609375,
        ),
        coord_origin="BOTTOMLEFT",
        column_index=None,
    )

    with pymupdf.open(str(pdf_path)) as pdf:
        page = pdf[location.page_number - 1]

        rect = citations.evidence_location_to_pymupdf_rect(
            location,
            page,
        )

        assert page.rect.contains(rect)

        original_text = page.get_text(
            "text",
            clip=rect,
        )

        assert "bougie" in normalize_citation_text(
            original_text
        )


def test_api_evidence_location_rejects_wrong_page():
    """
    Reject evidence coordinates associated
    with a different PDF page.
    """

    import pytest

    from backend.analysis.citations import (
        evidence_location_to_pymupdf_rect,
    )
    from backend.schemas import EvidenceLocation

    pdf_path = (
        DATA_ROOT
        / "contracts"
        / "contrat_B_mobilite_habitation.pdf"
    )

    location = EvidenceLocation(
        page_number=2,
        bbox=(
            57.780521392822266,
            352.7746887207031,
            531.5479125976562,
            389.53558349609375,
        ),
        coord_origin="BOTTOMLEFT",
        column_index=None,
    )

    with pymupdf.open(str(pdf_path)) as pdf:
        wrong_page = pdf[0]

        with pytest.raises(
            ValueError,
            match="does not match PDF page",
        ):
            evidence_location_to_pymupdf_rect(
                location,
                wrong_page,
            )
