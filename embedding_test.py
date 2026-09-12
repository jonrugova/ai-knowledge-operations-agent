import os

from openai import OpenAI


TEXT = (
    "Standard production time is up to around 3 weeks from the order date "
    "before the order is ready to ship."
)


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    # The OpenAI client uses the API key to communicate with OpenAI.
    client = OpenAI(api_key=api_key)

    # This request converts the text into an embedding using the selected model.
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=TEXT,
    )

    # The returned embedding is a list of numbers representing the text.
    embedding = response.data[0].embedding

    print(f"Original text:\n{TEXT}\n")
    print(f"Embedding dimensions: {len(embedding)}")
    print(f"First 10 numbers: {embedding[:10]}")


if __name__ == "__main__":
    main()