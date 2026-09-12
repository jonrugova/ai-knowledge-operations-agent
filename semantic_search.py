import os
import time

import psycopg
from openai import OpenAI
from pgvector import Vector
from pgvector.psycopg import register_vector

from observability import record_embedding_call


def search_knowledge(question: str, top_k: int = 3, trace=None):
    database_url = os.environ.get("DATABASE_URL")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    client = OpenAI(api_key=api_key)

    # The question must be embedded so it can be compared with stored vectors.
    embedding_start = time.perf_counter()
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=question,
        )
    except Exception:
        if trace is not None:
            record_embedding_call(
                trace,
                (time.perf_counter() - embedding_start) * 1000,
                input_tokens=0,
                total_tokens=0,
            )
        raise
    else:
        if trace is not None:
            usage = getattr(response, "usage", None)
            record_embedding_call(
                trace,
                (time.perf_counter() - embedding_start) * 1000,
                input_tokens=(
                    getattr(usage, "prompt_tokens", 0) or 0
                    if usage is not None
                    else 0
                ),
                total_tokens=(
                    getattr(usage, "total_tokens", 0) or 0
                    if usage is not None
                    else 0
                ),
            )
    question_embedding = response.data[0].embedding

    with psycopg.connect(database_url) as connection:
        # The adapter converts Python lists to pgvector values for PostgreSQL.
        register_vector(connection)

        with connection.cursor() as cursor:
            # Cosine distance measures the difference between two vectors.
            # Smaller distance means the vectors, and their texts, are similar.
            cursor.execute(
                """
                SELECT
                    id,
                    source_file,
                    chunk_index,
                    section,
                    content,
                    embedding <=> %s AS distance
                FROM knowledge_chunks
                ORDER BY distance
                LIMIT %s;
                """,
                (Vector(question_embedding), top_k),
            )
            rows = cursor.fetchall()

    # Similarity reverses distance: similarity = 1 - distance.
    return [
        {
            "id": row_id,
            "source_file": source_file,
            "chunk_index": chunk_index,
            "section": section,
            "content": content,
            "distance": distance,
            "similarity": 1 - distance,
        }
        for row_id, source_file, chunk_index, section, content, distance in rows
    ]


def main():
    questions = [
        "How long does it take to make a dress?",
        "Can I return a dress made to my measurements?",
        "Who pays customs fees?",
        "Can you rush my order in about two weeks?",
    ]

    for question in questions:
        print(f"Question: {question}")
        matches = search_knowledge(question)

        for rank, match in enumerate(matches, start=1):
            print(f"Rank: {rank}")
            print(f"ID: {match['id']}")
            print(f"Similarity: {match['similarity']:.6f}")
            print(f"Content: {match['content']}")

        print()


if __name__ == "__main__":
    main()