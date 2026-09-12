import os

import psycopg


def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")

    # Python uses the DATABASE_URL to open a PostgreSQL connection.
    with psycopg.connect(database_url) as connection:
        # A cursor sends SQL commands and reads their results.
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            postgres_version = cursor.fetchone()[0]
            print(f"PostgreSQL version:\n{postgres_version}\n")

            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    content TEXT NOT NULL
                );
                """
            )

            cursor.execute(
                "INSERT INTO knowledge_chunks (content) VALUES (%s);",
                ("Temporary test knowledge chunk.",),
            )

            # Commit saves the extension, table, and inserted row permanently.
            connection.commit()

            cursor.execute(
                "SELECT id, content FROM knowledge_chunks ORDER BY id;"
            )
            rows = cursor.fetchall()

            print("Rows in knowledge_chunks:")
            for row_id, content in rows:
                print(f"- id={row_id}, content={content!r}")


if __name__ == "__main__":
    main()