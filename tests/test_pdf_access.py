
"""
ClaimLens AI - Authorized PDF access tests.

Ensure that the PDF viewer only opens documents
authorized for the selected synthetic policy.
"""

import pytest

from backend.config import PROJECT_ROOT
from backend.schemas import AuthorizedDocument
from backend.analysis.pdf_access import (
    resolve_authorized_pdf_path,
)


AUTHORIZED_DOCUMENT = AuthorizedDocument(
    document_kind="GENERAL_CONDITIONS",
    document_reference="HAB-B-CG-2026",
    pdf_relative_path=(
        "contracts/contrat_B_mobilite_habitation.pdf"
    ),
)


def test_authorized_pdf_path_is_resolved():
    """An authorized PDF must resolve inside data."""

    path = resolve_authorized_pdf_path(
        source_pdf=(
            "contracts/contrat_B_mobilite_habitation.pdf"
        ),
        document_reference="HAB-B-CG-2026",
        authorized_documents=[AUTHORIZED_DOCUMENT],
    )

    expected = (
        PROJECT_ROOT
        / "data"
        / "contracts"
        / "contrat_B_mobilite_habitation.pdf"
    ).resolve()

    assert path == expected
    assert path.is_file()


def test_unauthorized_document_is_rejected():
    """Reject a PDF not authorized for the policy."""

    with pytest.raises(
        ValueError,
        match="not authorized",
    ):
        resolve_authorized_pdf_path(
            source_pdf=(
                "contracts/contrat_A_protection_essentielle.pdf"
            ),
            document_reference="HAB-A-CG-2026",
            authorized_documents=[AUTHORIZED_DOCUMENT],
        )


def test_document_reference_mismatch_is_rejected():
    """The document reference must match its PDF."""

    with pytest.raises(
        ValueError,
        match="not authorized",
    ):
        resolve_authorized_pdf_path(
            source_pdf=AUTHORIZED_DOCUMENT.pdf_relative_path,
            document_reference="WRONG-REFERENCE",
            authorized_documents=[AUTHORIZED_DOCUMENT],
        )


def test_path_traversal_is_rejected():
    """Never allow a PDF path outside the data root."""

    malicious_document = AuthorizedDocument(
        document_kind="GENERAL_CONDITIONS",
        document_reference="TEST-TRAVERSAL",
        pdf_relative_path="../outside.pdf",
    )

    with pytest.raises(
        ValueError,
        match="outside",
    ):
        resolve_authorized_pdf_path(
            source_pdf="../outside.pdf",
            document_reference="TEST-TRAVERSAL",
            authorized_documents=[malicious_document],
        )
