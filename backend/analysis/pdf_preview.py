
"""
ClaimLens AI - Authorized PDF evidence preview.

Render pages from SQL-authorized synthetic PDFs
with highlighted contractual evidence locations.

Original PDF files are never modified on disk.
"""

from typing import Iterable

import pymupdf

from backend.analysis.citations import (
    evidence_location_to_pymupdf_rect,
)
from backend.analysis.pdf_access import (
    resolve_authorized_pdf_path,
)
from backend.schemas import (
    AuthorizedDocument,
    EvidenceLocation,
)


def render_authorized_evidence_page(
    source_pdf: str,
    document_reference: str,
    page_number: int,
    locations: Iterable[EvidenceLocation],
    authorized_documents: Iterable[AuthorizedDocument],
) -> bytes:
    """
    Render an authorized PDF page as PNG bytes.

    Highlight the evidence rectangles directly
    on the in-memory PDF page.

    Document authorization must already have been
    established through the SQL-backed dossier.

    Raises:
        ValueError: Unauthorized document, invalid page,
                    or invalid evidence location.
        FileNotFoundError: Authorized PDF is missing.
    """

    # 1. Verify document identity and resolve its safe path.
    pdf_path = resolve_authorized_pdf_path(
        source_pdf=source_pdf,
        document_reference=document_reference,
        authorized_documents=authorized_documents,
    )

    # 2. Open the original PDF without modifying its file.
    with pymupdf.open(str(pdf_path)) as pdf:

        # 3. Validate the requested page number.
        if not 1 <= page_number <= len(pdf):
            raise ValueError(
                "Requested page number is outside the PDF."
            )

        page = pdf[page_number - 1]

        # 4. Convert and highlight each evidence location.
        for location in locations:

            rect = evidence_location_to_pymupdf_rect(
                location,
                page,
            )

            # Yellow highlighting, drawn in memory only.
            page.draw_rect(
                rect,
                color=(1.0, 0.65, 0.0),
                fill=(1.0, 0.95, 0.25),
                width=1.5,
                fill_opacity=0.26,
                stroke_opacity=0.95,
                overlay=True,
            )

        # 5. Render the page at 150% resolution.
        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(1.5, 1.5),
            alpha=False,
        )

        # 6. Return the image directly in memory.
        return pixmap.tobytes("png")
