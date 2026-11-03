
"""
ClaimLens AI - PDF evidence preview tests.

Verify that an authorized PDF page can be
rendered as a PNG with evidence highlighting.
"""

from backend.analysis.pdf_preview import (
    render_authorized_evidence_page,
)
from backend.schemas import (
    AuthorizedDocument,
    EvidenceLocation,
)


def test_render_authorized_pdf_evidence_as_png():
    """
    Render an authorized PDF page containing
    a real contractual evidence location.
    """

    document = AuthorizedDocument(
        document_kind="GENERAL_CONDITIONS",
        document_reference="HAB-B-CG-2026",
        pdf_relative_path=(
            "contracts/contrat_B_mobilite_habitation.pdf"
        ),
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
    )

    image_bytes = render_authorized_evidence_page(
        source_pdf=document.pdf_relative_path,
        document_reference=document.document_reference,
        page_number=2,
        locations=[location],
        authorized_documents=[document],
    )

    # Verify that the result is a PNG image.
    assert isinstance(image_bytes, bytes)
    assert image_bytes.startswith(
        b"\x89PNG\r\n\x1a\n"
    )
    assert len(image_bytes) > 1000
