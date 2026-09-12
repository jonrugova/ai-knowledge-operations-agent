import os

import psycopg
from openai import OpenAI
from pgvector import Vector
from pgvector.psycopg import register_vector


def hybrid_search_knowledge(question: str, top_k: int = 3):
    database_url = os.environ.get("DATABASE_URL")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=question,
    )
    question_embedding = response.data[0].embedding

    with psycopg.connect(database_url) as connection:
        register_vector(connection)

        with connection.cursor() as cursor:
            # Vector search finds semantically similar content.
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
                LIMIT 10;
                """,
                (Vector(question_embedding),),
            )
            vector_results = cursor.fetchall()

            # Text search finds lexical or keyword similarity.
            cursor.execute(
                """
                SELECT
                    id,
                    source_file,
                    chunk_index,
                    section,
                    content
                FROM knowledge_chunks
                WHERE to_tsvector(
                    'english',
                    section || ' ' || content
                ) @@ websearch_to_tsquery('english', %s)
                ORDER BY ts_rank_cd(
                    to_tsvector('english', section || ' ' || content),
                    websearch_to_tsquery('english', %s)
                ) DESC
                LIMIT 10;
                """,
                (question, question),
            )
            text_results = cursor.fetchall()

    combined = {}

    for rank, row in enumerate(vector_results, start=1):
        row_id, source_file, chunk_index, section, content, distance = row
        combined[row_id] = {
            "id": row_id,
            "source_file": source_file,
            "chunk_index": chunk_index,
            "section": section,
            "content": content,
            "vector_similarity": 1 - distance,
            "vector_rank": rank,
            "text_rank": None,
            "rrf_score": 1 / (60 + rank),
        }

    for rank, row in enumerate(text_results, start=1):
        row_id, source_file, chunk_index, section, content = row
        if row_id not in combined:
            combined[row_id] = {
                "id": row_id,
                "source_file": source_file,
                "chunk_index": chunk_index,
                "section": section,
                "content": content,
                "vector_similarity": None,
                "vector_rank": None,
                "text_rank": rank,
                "rrf_score": 1 / (60 + rank),
            }
        else:
            combined[row_id]["text_rank"] = rank
            combined[row_id]["rrf_score"] += 1 / (60 + rank)

    # RRF combines rankings without requiring scores on the same scale.
    ranked_results = sorted(
        combined.values(),
        key=lambda result: result["rrf_score"],
        reverse=True,
    )
    return ranked_results[:top_k]