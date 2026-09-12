import os

from openai import OpenAI

from semantic_search import search_knowledge


def answer_question(question: str):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    # Retrieval happens before generation.
    matches = search_knowledge(question, top_k=3)

    # The retrieved chunks become the model's context.
    context = "\n\n".join(match["content"] for match in matches)

    client = OpenAI(api_key=api_key)

    # Grounding instructions help prevent unsupported answers.
    response = client.responses.create(
        model="gpt-5.6-luna",
        instructions=(
            "Answer using ONLY the provided context. "
            "Do not invent policies or information. "
            "If the context does not contain enough information to answer, "
            "say exactly: \"I don't have enough information in the provided "
            "knowledge.\" Keep the answer concise and natural. "
            "Do not mention embeddings, vectors, retrieval, chunks, databases, "
            "or internal technical details."
        ),
        input=f"CONTEXT:\n{context}\n\nQUESTION:\n{question}",
    )

    return matches, response.output_text


def main():
    questions = [
        "How long does it take to make a dress?",
        "Can I return a dress made to my measurements?",
        "Who pays customs fees?",
        "Can you rush my order in about two weeks?",
        "Does Northstar Atelier offer gift wrapping?",
    ]

    for question in questions:
        matches, answer = answer_question(question)

        print(f"QUESTION\n{question}\n")
        print("RETRIEVED CONTEXT:")
        for match in matches:
            print(
                f"- Similarity: {match['similarity']:.6f} | "
                f"{match['content']}"
            )
        print(f"\nGENERATED ANSWER\n{answer}\n")


if __name__ == "__main__":
    main()