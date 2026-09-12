from rag_answer import answer_question
from semantic_search import search_knowledge


QUESTIONS = [
    "How long does production usually take?",
    "How much is the return shipping fee for one dress from the USA?",
    "How much does it cost to change a midi skirt to floor length?",
    "Do sleeve modifications require approval?",
    "What measurements are needed for custom sizing?",
    "Who is responsible for import duties?",
    "Can I cancel a custom-size order?",
    "Does Northstar Atelier offer gift wrapping?",
]


def main():
    for question in QUESTIONS:
        print(f"QUESTION\n{question}\n")
        print("RETRIEVAL RESULTS")

        matches = search_knowledge(question, top_k=3)
        for rank, match in enumerate(matches, start=1):
            preview = match["content"][:300].replace("\n", " ")
            print(
                f"Rank: {rank} | "
                f"Similarity: {match['similarity']:.6f} | "
                f"Content: {preview}"
            )

        _, answer = answer_question(question)
        print(f"\nGENERATED ANSWER\n{answer}\n")


if __name__ == "__main__":
    main()