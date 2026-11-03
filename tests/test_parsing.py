
from pathlib import Path

import pymupdf

from backend.ingestion.pdf_parser import extract_pdf_lines


# Project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Synthetic contract used for testing
PDF_PATH = (
    PROJECT_ROOT
    / "data"
    / "contracts"
    / "contrat_A_protection_essentielle.pdf"
)


def test_pdf_lines_have_valid_locations():
    """Check text extraction and PDF source coordinates."""

    # Extract lines using our own module
    rows = extract_pdf_lines(PDF_PATH)

    # The extraction must not be empty
    assert len(rows) > 0, "No text extracted"

    with pymupdf.open(str(PDF_PATH)) as document:

        # All three pages must contain extracted text
        extracted_pages = {
            row["page_number"] for row in rows
        }

        assert extracted_pages == {1, 2, 3}

        for row in rows:

            # Check source metadata
            assert row["document"] == PDF_PATH.name
            assert row["text"].strip()
            assert row["line_number"] > 0

            # Check page number
            page_number = row["page_number"]

            assert 1 <= page_number <= len(document)

            # Check bounding box
            x0, y0, x1, y1 = row["bbox"]

            page = document[page_number - 1]
            rect = page.rect

            assert 0 <= x0 < x1 <= rect.width
            assert 0 <= y0 < y1 <= rect.height
