import os
import re

import psycopg
from openai import OpenAI
from pgvector import Vector
from pgvector.psycopg import register_vector


STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "do",
    "does",
    "did",
    "what",
    "when",
    "who",
    "how",
    "can",
    "my",
    "i",
    "it",
    "if",
    "in",
    "of",
    "to",
    "for",
    "from",
    "and",
    "or",
}


def meaningful_tokens(text: str):
    return {
        token
        for token in re.findall(r"[a-z]+", text.lower())
        if token not in STOPWORDS
    }


def title_aware_search_knowledge(question: str, top_k: int = 3):
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
            cursor.execute(
                """
                SELECT
                    id,
                    section,
                    content,
                    embedding <=> %s AS distance
                FROM knowledge_chunks;
                """,
                (Vector(question_embedding),),
            )
            rows = cursor.fetchall()

    question_tokens = meaningful_tokens(question)
    results = []

    for row_id, section, content, distance in rows:
        vector_similarity = 1 - distance
        section_tokens = meaningful_tokens(section)
        title_overlap = len(question_tokens & section_tokens)
        title_bonus = min(title_overlap * 0.05, 0.10)
        final_score = vector_similarity + title_bonus

        results.append(
            {
                "id": row_id,
                "section": section,
                "content": content,
                "vector_similarity": vector_similarity,
                "title_overlap": title_overlap,
                "title_bonus": title_bonus,
                "final_score": final_score,
            }
        )

    results.sort(key=lambda result: result["final_score"], reverse=True)
    return results[:top_k]