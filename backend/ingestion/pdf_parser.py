
from pathlib import Path

import pymupdf


def extract_pdf_lines(pdf_path: Path) -> list[dict]:
    """
    Extract text lines from a PDF with their source locations.

    Each line contains:
    - source document
    - page number (starting at 1)
    - line number
    - original text
    - bounding box coordinates
    """

    pdf_path = Path(pdf_path)

    if not pdf_path.is_file():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    extracted_lines = []

    with pymupdf.open(str(pdf_path)) as document:

        for page_index, page in enumerate(document):

            page_data = page.get_text("dict", sort=True)

            line_number = 0

            for block in page_data["blocks"]:

                # Ignore images and non-text blocks
                if block.get("type") != 0:
                    continue

                for line in block.get("lines", []):

                    text = "".join(
                        span["text"]
                        for span in line["spans"]
                    ).strip()

                    if not text:
                        continue

                    line_number += 1

                    extracted_lines.append({
                        "document": pdf_path.name,
                        "page_number": page_index + 1,
                        "line_number": line_number,
                        "text": text,
                        "bbox": list(line["bbox"]),
                    })

    return extracted_lines
