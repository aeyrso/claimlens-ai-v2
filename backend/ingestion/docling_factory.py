
"""
ClaimLens AI - Docling converter configuration.

Centralized PDF converter factory using PyPdfium
and conservative parallelism settings.

The backend is being evaluated for Windows stability.
"""

from docling.backend.pypdfium2_backend import (
    PyPdfiumDocumentBackend,
)
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
)
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
)


def create_document_converter() -> DocumentConverter:
    """
    Create a Docling converter using PyPdfium.

    Configuration:
    - PyPdfium PDF backend
    - One inference thread
    - Page queue size of 1

    Reuse the converter across multiple documents.
    """

    pipeline_options = PdfPipelineOptions(
        queue_max_size=1,
    )

    pipeline_options.accelerator_options.num_threads = 1

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=PyPdfiumDocumentBackend,
            )
        }
    )
