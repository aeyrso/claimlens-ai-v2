
"""
ClaimLens AI - PDF citation utilities.

Convert Docling bounding boxes into PyMuPDF coordinates
to support verifiable citations and PDF highlighting.
"""

import pymupdf


def docling_bbox_to_pymupdf_rect(
    bbox,
    page: pymupdf.Page,
) -> pymupdf.Rect:
    """
    Convert a Docling bounding box to PyMuPDF coordinates.

    Supported:
        - TOPLEFT origin
        - BOTTOMLEFT origin
        - Non-rotated PDF pages

    Returns:
        pymupdf.Rect

    Raises:
        ValueError if coordinates are unsupported or invalid.
    """

    # Avoid incorrect highlights on rotated pages.
    if page.rotation != 0:
        raise ValueError(
            "Rotated PDF pages are not supported yet."
        )

    x0, y0, x1, y1 = bbox.as_tuple()

    origin = bbox.coord_origin.value.upper()

    if origin == "BOTTOMLEFT":

        page_height = page.rect.height

        rect = pymupdf.Rect(
            x0,
            page_height - y1,
            x1,
            page_height - y0,
        )

    elif origin == "TOPLEFT":

        rect = pymupdf.Rect(
            x0,
            y0,
            x1,
            y1,
        )

    else:
        raise ValueError(
            f"Unsupported coordinate origin: {origin}"
        )

    # Validate the resulting rectangle.
    if (
        rect.is_empty
        or not rect.is_valid
        or not page.rect.contains(rect)
    ):
        raise ValueError(
            f"Invalid PDF bounding box: {rect}"
        )

    return rect


def evidence_location_to_pymupdf_rect(
    location,
    page: pymupdf.Page,
) -> pymupdf.Rect:
    """
    Convert an API EvidenceLocation into PyMuPDF coordinates.

    Supports TOPLEFT and BOTTOMLEFT origins.
    Rejects rotated pages, mismatched page numbers,
    and invalid bounding boxes.
    """

    if page.rotation != 0:
        raise ValueError(
            "Rotated PDF pages are not supported yet."
        )

    if location.page_number != page.number + 1:
        raise ValueError(
            "Evidence location does not match PDF page."
        )

    x0, y0, x1, y1 = location.bbox

    if location.coord_origin == "BOTTOMLEFT":
        page_height = page.rect.height

        rect = pymupdf.Rect(
            x0,
            page_height - y1,
            x1,
            page_height - y0,
        )

    elif location.coord_origin == "TOPLEFT":
        rect = pymupdf.Rect(
            x0,
            y0,
            x1,
            y1,
        )

    else:
        raise ValueError(
            "Unsupported coordinate origin."
        )

    if (
        rect.is_empty
        or not rect.is_valid
        or not page.rect.contains(rect)
    ):
        raise ValueError(
            f"Invalid PDF bounding box: {rect}"
        )

    return rect
