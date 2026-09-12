import json
from pathlib import Path

from hybrid_search import hybrid_search_knowledge


EVAL_PATH = Path("evaluations/retrieval_eval.json")
BASELINE_TOP_1 = 77.78
BASELINE_TOP_3 = 88.89
FOCUS_CASES = {"eval_001", "eval_004", "eval_015", "eval_017"}


def main():
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    top_1_correct = 0
    top_3_correct = 0
    failures = []
    focus_results = []

    for case in cases:
        results = hybrid_search_knowledge(case["question"], top_k=3)
        sections = [result["section"] for result in results]
        expected = case["expected_sections"]

        top_1_pass = bool(sections) and sections[0] in expected
        top_3_pass = any(section in expected for section in sections)
        top_1_correct += int(top_1_pass)
        top_3_correct += int(top_3_pass)

        print(f"Evaluation ID: {case['id']}")
        print(f"Question: {case['question']}")
        print(f"Expected section(s): {', '.join(expected)}")
        for rank, result in enumerate(results, start=1):
            print(
                f"Rank {rank}: {result['section']} | "
                f"RRF: {result['rrf_score']:.6f} | "
                f"Vector rank: {result['vector_rank']} | "
                f"Text rank: {result['text_rank']}"
            )
        print(f"Top-1: {'PASS' if top_1_pass else 'FAIL'}")
        print(f"Top-3: {'PASS' if top_3_pass else 'FAIL'}")
        print()

        case_result = {
            "id": case["id"],
            "question": case["question"],
            "expected": expected,
            "sections": sections,
            "top_1_pass": top_1_pass,
            "top_3_pass": top_3_pass,
        }
        if not top_1_pass:
            failures.append(case_result)
        if case["id"] in FOCUS_CASES:
            focus_results.append(case_result)

    total = len(cases)
    top_1_accuracy = top_1_correct / total * 100
    top_3_accuracy = top_3_correct / total * 100

    print("FAILURES")
    if not failures:
        print("None")
    for failure in failures:
        print(f"Evaluation ID: {failure['id']}")
        print(f"Question: {failure['question']}")
        print(f"Expected section(s): {', '.join(failure['expected'])}")
        print(f"Retrieved section(s): {', '.join(failure['sections'])}")
        print(f"Top-1: {'PASS' if failure['top_1_pass'] else 'FAIL'}")
        print(f"Top-3: {'PASS' if failure['top_3_pass'] else 'FAIL'}")

    print("\nFOCUS CASES")
    for result in focus_results:
        print(
            f"{result['id']} | "
            f"Top-1: {'PASS' if result['top_1_pass'] else 'FAIL'} | "
            f"Top-3: {'PASS' if result['top_3_pass'] else 'FAIL'} | "
            f"Rank 1: {result['sections'][0]}"
        )

    print("\nCOMPARISON")
    print("BASELINE")
    print(f"Top-1: {BASELINE_TOP_1:.2f}%")
    print(f"Top-3: {BASELINE_TOP_3:.2f}%")
    print("HYBRID")
    print(f"Top-1: {top_1_correct}/{total} = {top_1_accuracy:.2f}%")
    print(f"Top-3: {top_3_correct}/{total} = {top_3_accuracy:.2f}%")


if __name__ == "__main__":
    main()