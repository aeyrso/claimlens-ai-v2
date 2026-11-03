
"""
ClaimLens AI - Authorized PDF file access.

Resolve PDF files only when their source path and
document reference match an authorized document.

Designed for the local synthetic demonstration corpus.
"""

from pathlib import Path
from typing import Iterable

from backend.config import PROJECT_ROOT
from backend.schemas import AuthorizedDocument


DATA_ROOT = (PROJECT_ROOT / "data").resolve()


def resolve_authorized_pdf_path(
    source_pdf: str,
    document_reference: str,
    authorized_documents: Iterable[AuthorizedDocument],
) -> Path:
    """
    Resolve a PDF path after checking document authorization.

    The authorized document list must originate from the
    SQL-validated contractual dossier.

    Raises:
        ValueError: Unauthorized document or unsafe PDF path.
        FileNotFoundError: Authorized PDF does not exist.
    """

    # 1. Verify the document identity against the authorized list.
    authorized = any(
        document.pdf_relative_path == source_pdf
        and document.document_reference == document_reference
        for document in authorized_documents
    )

    if not authorized:
        raise ValueError(
            "PDF document is not authorized for this policy."
        )

    # 2. Reject absolute paths.
    relative_path = Path(source_pdf)

    if relative_path.is_absolute():
        raise ValueError(
            "PDF path is outside the authorized data directory."
        )

    # 3. Resolve the path, including any symbolic links.
    pdf_path = (DATA_ROOT / relative_path).resolve()

    # 4. Ensure the resolved path remains inside data/.
    if not pdf_path.is_relative_to(DATA_ROOT):
        raise ValueError(
            "PDF path is outside the authorized data directory."
        )

    # 5. Only PDF files can be opened.
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(
            "Authorized document must be a PDF file."
        )

    # 6. Verify that the file exists.
    if not pdf_path.is_file():
        raise FileNotFoundError(
            "Authorized PDF file was not found."
        )

    return pdf_path
