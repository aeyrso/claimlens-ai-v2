
"""
ClaimLens AI - Reproducible synthetic corpus indexing.

Generate structured JSON exports from the PDF files
listed in the synthetic corpus manifest.
"""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from backend.ingestion.docling_factory import (
    create_document_converter,
)
from backend.ingestion.structured_export import (
    build_structured_export,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"
MANIFEST_PATH = DATA_ROOT / "manifest.json"


def index_synthetic_corpus() -> dict:
    """
    Generate missing JSON exports without overwriting
    previously validated extractions.
    """

    manifest = json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8")
    )

    converter = None
    generated = 0
    existing = 0

    for entry in manifest["files"]:
        relative_path = Path(entry["relative_path"])

        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            raise ValueError(
                f"Invalid PDF path: {relative_path}"
            )

        pdf_path = DATA_ROOT / relative_path

        if not pdf_path.is_file():
            raise FileNotFoundError(pdf_path)

        pdf_bytes = pdf_path.read_bytes()

        if len(pdf_bytes) != entry["size_bytes"]:
            raise ValueError(
                f"Invalid PDF size: {relative_path}"
            )

        actual_hash = hashlib.sha256(
            pdf_bytes
        ).hexdigest()

        if actual_hash != entry["sha256"]:
            raise ValueError(
                f"PDF checksum mismatch: {relative_path}"
            )

        json_path = (
            DATA_ROOT / "parsed" / relative_path
        ).with_suffix(".json")

        if json_path.exists():
            stored = json.loads(
                json_path.read_text(encoding="utf-8")
            )

            if stored.get("source_pdf") != relative_path.as_posix():
                raise ValueError(
                    f"Invalid existing export: {json_path}"
                )

            existing += 1
            continue

        if converter is None:
            converter = create_document_converter()

        document = converter.convert(
            str(pdf_path)
        ).document

        exported = build_structured_export(
            document,
            relative_path.as_posix(),
        )

        json_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        descriptor, temporary_path = tempfile.mkstemp(
            prefix=".claimlens-export-",
            suffix=".tmp",
            dir=json_path.parent,
        )

        try:
            with os.fdopen(
                descriptor, "w", encoding="utf-8"
            ) as file:
                json.dump(
                    exported,
                    file,
                    ensure_ascii=False,
                    indent=2,
                )

            # On Windows, rename refuses to
            # overwrite an existing destination.
            os.rename(temporary_path, json_path)

        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)

        generated += 1
        print(f"Generated: {relative_path}")

    return {
        "documents": len(manifest["files"]),
        "generated": generated,
        "existing": existing,
    }


if __name__ == "__main__":
    print(index_synthetic_corpus())
