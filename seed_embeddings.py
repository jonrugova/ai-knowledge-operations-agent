import os

import psycopg
from openai import OpenAI
from pgvector.psycopg import register_vector


CHUNKS = [
    "Northstar Atelier prepares standard orders in 12 calendar production days after payment and final details are confirmed.",
    "After production, Northstar Atelier standard courier delivery usually takes 4–7 business days.",
    "Eligible standard-size items may be returned within 14 calendar days if unworn, undamaged, and in original packaging.",
    "Items made to a customer's measurements are final sale and are not eligible for routine returns or exchanges.",
    "Customization requests must be confirmed in writing before production starts.",
    "Address changes cannot be guaranteed after an order enters fulfillment.",
    "Rush production is not promised; an employee may submit a request for human review.",
    "Import duties, local taxes, and brokerage charges are the customer's responsibility unless the order confirmation says otherwise.",
    "Cancellation requests are reviewed based on production status.",
    "Northstar Atelier does not currently offer gift wrapping.",
]


def main():
    database_url = os.environ.get("DATABASE_URL")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=CHUNKS,
    )
    embeddings = [item.embedding for item in response.data]

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            # VECTOR(1536) matches the model's 1536-number embedding size.
            cursor.execute("DROP TABLE IF EXISTS knowledge_chunks;")
            cursor.execute(
                """
                CREATE TABLE knowledge_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding VECTOR(1536) NOT NULL
                );
                """
            )

            # The adapter converts Python lists to and from pgvector values.
            register_vector(connection)

            # Each chunk is stored beside the embedding that represents it.
            cursor.executemany(
                """
                INSERT INTO knowledge_chunks (content, embedding)
                VALUES (%s, %s);
                """,
                zip(CHUNKS, embeddings),
            )
            connection.commit()

            cursor.execute(
                """
                SELECT id, content, vector_dims(embedding)
                FROM knowledge_chunks
                ORDER BY id;
                """
            )

            for row_id, content, dimensions in cursor.fetchall():
                print(f"id: {row_id}")
                print(f"content: {content}")
                print(f"dimensions: {dimensions}")


if __name__ == "__main__":
    main()