import os
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


SOURCE_PATH = Path(
    os.environ.get(
        "KNOWLEDGE_SOURCE_PATH",
        "examples/sample_knowledge.txt",
    )
)
OUTPUT_PATH = Path(
    os.environ.get(
        "KNOWLEDGE_EXTRACTED_PATH",
        "documents/extracted_text.txt",
    )
)
PHRASES = [
    "12 calendar production days",
    "4–7 business days",
    "Custom-size",
    "Import duties",
]


def add_non_empty_lines(text, lines):
    for line in text.splitlines():
        if line.strip():
            lines.append(line.strip())


def extract_text():
    lines = []

    if SOURCE_PATH.suffix.lower() == ".docx":
        # DOCX text must be extracted before it can be chunked later.
        document = Document(SOURCE_PATH)
        for item in document.iter_inner_content():
            if isinstance(item, Paragraph):
                add_non_empty_lines(item.text, lines)
            elif isinstance(item, Table):
                # Keep cells from the same table row together on one line.
                for row in item.rows:
                    row_cells = []
                    for cell in row.cells:
                        cell_lines = [
                            line.strip()
                            for line in cell.text.splitlines()
                            if line.strip()
                        ]
                        if cell_lines:
                            row_cells.append(" ".join(cell_lines))
                    if row_cells:
                        lines.append(" | ".join(row_cells))
    else:
        add_non_empty_lines(SOURCE_PATH.read_text(encoding="utf-8"), lines)

    extracted_text = "\n".join(lines) + "\n"
    OUTPUT_PATH.write_text(extracted_text, encoding="utf-8")
    return lines, extracted_text


def main():
    lines, extracted_text = extract_text()

    print(f"Total extracted characters: {len(extracted_text)}")
    print(f"Total non-empty text blocks/lines: {len(lines)}")

    print("\nFirst 25 extracted lines:")
    for line in lines[:25]:
        print(line)

    print("\nLast 10 extracted lines:")
    for line in lines[-10:]:
        print(line)

    print("\nPhrase verification:")
    for phrase in PHRASES:
        found = phrase in extracted_text
        print(f'{phrase}: {"FOUND" if found else "NOT FOUND"}')


if __name__ == "__main__":
    main()