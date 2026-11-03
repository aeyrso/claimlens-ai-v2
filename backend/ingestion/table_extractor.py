
"""
ClaimLens AI - Structured table row extraction.

Convert Docling tables into individually retrievable rows
while preserving column headers and PDF provenance.
"""

from collections import defaultdict


def serialize_table_rows(document, document_id: str) -> list[dict]:
    """
    Convert Docling tables into row-level records.

    Each record contains:
    - Document and table identifiers
    - PDF page number
    - Row index
    - Column headers
    - Cell values
    - Serialized row text
    - Individual cell bounding boxes

    Current scope: single-page tables with simple headers.
    """

    records = []

    for table_index, table in enumerate(document.tables, start=1):

        pages = {p.page_no for p in table.prov}

        if len(pages) != 1:
            raise ValueError(
                "Only single-page tables are supported."
            )

        page_number = next(iter(pages))

        # Group cells by their row and column indices
        grid = defaultdict(dict)

        for cell in table.data.table_cells:

            row_index = cell.start_row_offset_idx
            col_index = cell.start_col_offset_idx

            if col_index in grid[row_index]:
                raise ValueError(
                    "Duplicate cell coordinates detected."
                )

            grid[row_index][col_index] = cell

        if 0 not in grid:
            raise ValueError("Table header not found.")

        # First row contains the column headers
        header_columns = sorted(grid[0])

        if header_columns != list(range(len(header_columns))):
            raise ValueError("Invalid header columns.")

        headers = [
            grid[0][col].text.strip()
            for col in header_columns
        ]

        # Each remaining row becomes one record
        for row_index in sorted(r for r in grid if r > 0):

            cells = grid[row_index]

            if sorted(cells) != header_columns:
                raise ValueError(
                    f"Incomplete table row: {row_index}"
                )

            values = [
                cells[col].text.strip()
                for col in header_columns
            ]

            # Preserve each cell's original coordinates
            cell_locations = []

            for col in header_columns:

                bbox = cells[col].bbox

                cell_locations.append({
                    "column_index": col,
                    "bbox": list(bbox.as_tuple()) if bbox else None,
                    "coord_origin": (
                        bbox.coord_origin.value if bbox else None
                    ),
                })

            # Self-contained text for keyword/vector retrieval
            row_serialized = " | ".join(
                f"{header}: {value}"
                for header, value in zip(headers, values)
            )

            records.append({
                "document_id": document_id,
                "table_id": f"{document_id}:t{table_index}",
                "page_number": page_number,
                "row_index": row_index,
                "column_headers": headers,
                "row_cells": values,
                "row_serialized": row_serialized,
                "cell_locations": cell_locations,
            })

    return records
