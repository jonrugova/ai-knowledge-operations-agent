import json
import os
from pathlib import Path

import psycopg
from openai import OpenAI
from pgvector.psycopg import register_vector


CHUNKS_PATH = Path(
    os.environ.get(
        "KNOWLEDGE_CHUNKS_PATH",
        "documents/chunks.json",
    )
)
SOURCE_FILE = Path(
    os.environ.get(
        "KNOWLEDGE_SOURCE_PATH",
        "examples/sample_knowledge.txt",
    )
).name
EXPECTED_RECORDS = [
    (0, "1. STANDARD PRODUCTION TIME"),
    (1, "2. SHIPPING WINDOW"),
    (6, "7. RUSH REQUESTS"),
]


def load_chunks():
    # chunks.json is now the source for database ingestion.
    chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))

    if not chunks:
        raise ValueError("chunks.json must contain at least one chunk.")

    for chunk in chunks:
        if "chunk_index" not in chunk:
            raise ValueError("Every chunk must have a chunk_index.")
        if not chunk.get("section"):
            raise ValueError("Every chunk must have a section.")
        if not chunk.get("content", "").strip():
            raise ValueError("Every chunk must have non-empty content.")

    return chunks


def main():
    database_url = os.environ.get("DATABASE_URL")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    chunks = load_chunks()
    contents = [chunk["content"] for chunk in chunks]

    client = OpenAI(api_key=api_key)

    # Each chunk receives its own embedding in one batched request.
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=contents,
    )
    embeddings = [item.embedding for item in response.data]

    if len(embeddings) != len(contents):
        raise RuntimeError("The number of embeddings does not match the chunks.")

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            # This replaces the manually seeded test dataset from Checkpoint 1.
            cursor.execute("DROP TABLE IF EXISTS knowledge_chunks;")
            cursor.execute(
                """
                CREATE TABLE knowledge_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    source_file TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    section TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding VECTOR(1536) NOT NULL
                );
                """
            )

            register_vector(connection)

            # Metadata describes where a chunk came from and is stored
            # separately from its content.
            rows_to_insert = [
                (
                    SOURCE_FILE,
                    chunk["chunk_index"],
                    chunk["section"],
                    chunk["content"],
                    embedding,
                )
                for chunk, embedding in zip(chunks, embeddings)
            ]

            # Metadata, content, and the corresponding embedding stay paired.
            cursor.executemany(
                """
                INSERT INTO knowledge_chunks (
                    source_file,
                    chunk_index,
                    section,
                    content,
                    embedding
                )
                VALUES (%s, %s, %s, %s, %s);
                """,
                rows_to_insert,
            )
            connection.commit()

            cursor.execute("SELECT COUNT(*) FROM knowledge_chunks;")
            total_rows = cursor.fetchone()[0]
            print(f"Total rows stored: {total_rows}")

            cursor.execute(
                """
                SELECT
                    id,
                    source_file,
                    chunk_index,
                    section,
                    vector_dims(embedding)
                FROM knowledge_chunks
                ORDER BY id;
                """
            )
            for row in cursor.fetchall():
                row_id, source_file, chunk_index, section, dimensions = row
                print(
                    f"ID: {row_id} | Source: {source_file} | "
                    f"Chunk index: {chunk_index} | Section: {section} | "
                    f"Dimensions: {dimensions}"
                )

            # Metadata can later support filtering, debugging, evaluation,
            # and source attribution, but does not change vector similarity.
            print("\nRequired metadata verification:")
            for chunk_index, section in EXPECTED_RECORDS:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM knowledge_chunks
                        WHERE chunk_index = %s
                          AND section = %s
                    );
                    """,
                    (chunk_index, section),
                )
                found = cursor.fetchone()[0]
                print(
                    f'Chunk index {chunk_index} | Section: {section}: '
                    f'{"FOUND" if found else "NOT FOUND"}'
                )


if __name__ == "__main__":
    main()