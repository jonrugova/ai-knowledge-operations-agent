import json
import os
import re
from pathlib import Path


INPUT_PATH = Path(
    os.environ.get(
        "KNOWLEDGE_EXTRACTED_PATH",
        "documents/extracted_text.txt",
    )
)
OUTPUT_PATH = Path(
    os.environ.get(
        "KNOWLEDGE_CHUNKS_PATH",
        "documents/chunks.json",
    )
)
MAX_CHARS = 1800
HEADING_PATTERN = re.compile(r"^\d+\.\s+[A-Z][A-Z0-9 &,/()\-]+$")
CONCEPTS = [
    "12 calendar production days",
    "4–7 business days",
    "Custom-size",
    "Import duties",
]


def split_into_sections(lines):
    sections = []
    heading = lines[0]
    section_lines = [heading]

    for line in lines[1:]:
        if HEADING_PATTERN.fullmatch(line):
            sections.append((heading, section_lines))
            heading = line
            section_lines = [heading]
        else:
            section_lines.append(line)

    sections.append((heading, section_lines))
    return sections


def split_large_section(heading, lines):
    parts = []
    current_lines = [heading]

    for line in lines[1:]:
        candidate = "\n".join(current_lines + [line])

        # Very large chunks can reduce retrieval precision.
        if len(candidate) > MAX_CHARS and len(current_lines) > 1:
            parts.append("\n".join(current_lines))
            # Keeping the heading in every part improves later retrieval.
            current_lines = [heading, line]
        else:
            current_lines.append(line)

    parts.append("\n".join(current_lines))
    return parts


def build_chunks():
    lines = [
        line.strip()
        for line in INPUT_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # One document is split into focused chunks for more precise retrieval.
    sections = split_into_sections(lines)
    chunks = []

    for section, section_lines in sections:
        for content in split_large_section(section, section_lines):
            chunks.append(
                {
                    "chunk_index": len(chunks),
                    "section": section,
                    "content": content,
                }
            )

    OUTPUT_PATH.write_text(
        json.dumps(chunks, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return chunks


def main():
    chunks = build_chunks()

    print(f"Total number of chunks: {len(chunks)}")
    for chunk in chunks:
        preview = chunk["content"][:120].replace("\n", " ")
        print(
            f'Chunk {chunk["chunk_index"]} | '
            f'Section: {chunk["section"]} | '
            f'Characters: {len(chunk["content"])} | '
            f"Preview: {preview}"
        )

    no_empty_chunks = all(chunk["content"].strip() for chunk in chunks)
    print(f"\nNo empty chunks: {'PASS' if no_empty_chunks else 'FAIL'}")

    combined_content = "\n".join(chunk["content"] for chunk in chunks)
    print("Concept verification:")
    for concept in CONCEPTS:
        found = concept in combined_content
        print(f'{concept}: {"FOUND" if found else "NOT FOUND"}')


if __name__ == "__main__":
    main()