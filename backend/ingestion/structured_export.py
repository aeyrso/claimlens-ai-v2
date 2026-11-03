
"""
ClaimLens AI - Structured document export.

Prepare text elements and table rows for RAG indexing
while preserving their original PDF provenance.
"""

from pathlib import Path

from backend.ingestion.table_extractor import (
    serialize_table_rows,
)


def build_structured_export(document, source_path: str) -> dict:
    """
    Build a JSON-serializable representation of a Docling document.

    Preserve:
    - Source PDF identity
    - Text elements and their labels
    - Page numbers
    - Original bounding boxes and coordinate origins
    - Independently retrievable table rows

    The returned data is not yet stored in SQL or indexed.
    """

    source = Path(source_path).as_posix()
    document_id = Path(source).with_suffix("").as_posix()

    text_elements = []

    for element_index, (item, _) in enumerate(
        document.iterate_items(), start=1
    ):
        label = str(item.label)

        # Tables are indexed separately, one row at a time.
        if label == "table":
            continue

        text = (getattr(item, "text", None) or "").strip()

        if not text:
            continue

        provenances = getattr(item, "prov", None) or []

        if not provenances:
            raise ValueError(
                f"Missing provenance for element {element_index}"
            )

        locations = []

        for provenance in provenances:
            bbox = provenance.bbox

            if bbox is None:
                raise ValueError(
                    f"Missing bounding box for element {element_index}"
                )

            locations.append({
                "page_number": provenance.page_no,
                "bbox": list(bbox.as_tuple()),
                "coord_origin": bbox.coord_origin.value,
            })

        text_elements.append({
            "element_id": f"{document_id}:e{element_index}",
            "label": label,
            "text": text,
            "locations": locations,
        })

    table_rows = serialize_table_rows(
        document,
        document_id=document_id,
    )

    return {
        "document_id": document_id,
        "source_pdf": source,
        "page_count": len(document.pages),
        "text_elements": text_elements,
        "table_rows": table_rows,
    }
