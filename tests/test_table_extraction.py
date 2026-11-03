
from pathlib import Path

from backend.ingestion.docling_factory import create_document_converter

from backend.ingestion.table_extractor import serialize_table_rows


PDF_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "contracts"
    / "contrat_A_protection_essentielle.pdf"
)


def test_table_rows_preserve_values_and_provenance():
    document = create_document_converter().convert(str(PDF_PATH)).document

    rows = serialize_table_rows(document, "HAB-A-CG-2026")

    # One row from table 1, six rows from table 2.
    assert len(rows) == 7

    assert sum(
        row["table_id"] == "HAB-A-CG-2026:t1"
        for row in rows
    ) == 1

    assert sum(
        row["table_id"] == "HAB-A-CG-2026:t2"
        for row in rows
    ) == 6

    # Each row must have a unique identifier.
    identifiers = {
        (row["table_id"], row["row_index"])
        for row in rows
    }
    assert len(identifiers) == 7

    # Check the serialized content and provenance.
    for row in rows:
        assert row["page_number"] == 1

        headers = row["column_headers"]
        values = row["row_cells"]
        locations = row["cell_locations"]

        assert len(headers) == len(values) == len(locations)

        expected_text = " | ".join(
            f"{header}: {value}"
            for header, value in zip(headers, values)
        )
        assert row["row_serialized"] == expected_text

        assert [loc["column_index"] for loc in locations] == list(
            range(len(values))
        )

        for location in locations:
            assert location["bbox"] is not None
            assert location["coord_origin"] in {
                "TOPLEFT",
                "BOTTOMLEFT",
            }

    # Verify an insurance coverage row.
    matches = [
        row for row in rows
        if "Vol de vélo en local commun" in row["row_cells"]
    ]

    assert len(matches) == 1

    bicycle_row = matches[0]

    assert bicycle_row["table_id"] == "HAB-A-CG-2026:t2"
    assert bicycle_row["row_index"] == 3

    assert bicycle_row["row_cells"] == [
        "Vol de vélo en local commun",
        "1 200 EUR",
        "120 EUR",
        "Porte verrouillée ET vélo attaché à un point fixe",
    ]

    assert len(bicycle_row["cell_locations"]) == 4
