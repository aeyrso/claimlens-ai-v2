
"""
ClaimLens AI - Multi-document PDF ingestion.

Read the synthetic corpus manifest, validate each PDF,
and export Markdown and structured JSON using one
Docling converter.
"""

import json
from hashlib import sha256
from pathlib import Path

from backend.ingestion.docling_factory import (
    create_document_converter,
)
from backend.ingestion.structured_export import (
    build_structured_export,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_ROOT = PROJECT_ROOT / "data"
MANIFEST_PATH = DATA_ROOT / "manifest.json"
OUTPUT_ROOT = DATA_ROOT / "parsed"


def main():
    # 1. Load the corpus manifest.
    manifest = json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8")
    )

    files = manifest["files"]

    # 2. Initialize Docling only once.
    converter = create_document_converter()

    processed = 0
    total_tables = 0
    total_rows = 0

    # 3. Process each document separately.
    for entry in files:
        relative_path = Path(entry["relative_path"])
        pdf_path = DATA_ROOT / relative_path

        if not pdf_path.is_file():
            raise FileNotFoundError(
                f"Missing PDF: {pdf_path}"
            )

        # 4. Verify PDF integrity before ingestion.
        content = pdf_path.read_bytes()

        if len(content) != entry["size_bytes"]:
            raise ValueError(
                f"Incorrect PDF size: {pdf_path.name}"
            )

        if sha256(content).hexdigest() != entry["sha256"]:
            raise ValueError(
                f"Incorrect PDF checksum: {pdf_path.name}"
            )

        print(f"Processing: {relative_path.as_posix()}")

        # 5. Extract the document with Docling.
        result = converter.convert(str(pdf_path))
        document = result.document

        # 6. Prepare Markdown and structured JSON.
        markdown = document.export_to_markdown()

        structured = build_structured_export(
            document,
            relative_path.as_posix(),
        )

        # 7. Preserve the source folder structure.
        markdown_path = (
            OUTPUT_ROOT / relative_path
        ).with_suffix(".md")

        json_path = markdown_path.with_suffix(".json")

        markdown_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # 8. Save readable Markdown.
        markdown_path.write_text(
            markdown,
            encoding="utf-8",
        )

        # 9. Save structured data with citation provenance.
        json_path.write_text(
            json.dumps(
                structured,
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        # 10. Update ingestion statistics.
        table_count = len(document.tables)
        row_count = len(structured["table_rows"])

        processed += 1
        total_tables += table_count
        total_rows += row_count

        print(f"Markdown output: {markdown_path}")
        print(f"JSON output: {json_path}")
        print(f"Characters: {len(markdown)}")
        print(f"Tables: {table_count}")
        print(f"Structured rows: {row_count}")
        print("---")

    print(f"DOCUMENTS PROCESSED: {processed}/{len(files)}")
    print(f"TOTAL TABLES: {total_tables}")
    print(f"TOTAL STRUCTURED ROWS: {total_rows}")
    print("INGESTION COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
