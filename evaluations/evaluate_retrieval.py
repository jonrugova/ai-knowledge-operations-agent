import json
from pathlib import Path

from semantic_search import search_knowledge


EVAL_PATH = Path("evaluations/retrieval_eval.json")


def main():
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    primary_top_1_correct = 0
    primary_top_3_correct = 0
    acceptable_top_1_correct = 0
    acceptable_top_3_correct = 0
    acceptable_top_3_failures = []

    for case in cases:
        results = search_knowledge(case["question"], top_k=3)
        primary = case["primary_section"]
        acceptable = case["acceptable_sections"]
        sections = [result["section"] for result in results]

        primary_top_1_pass = bool(sections) and sections[0] == primary
        primary_top_3_pass = primary in sections
        acceptable_top_1_pass = bool(sections) and sections[0] in acceptable
        acceptable_top_3_pass = any(
            section in acceptable for section in sections
        )

        primary_top_1_correct += int(primary_top_1_pass)
        primary_top_3_correct += int(primary_top_3_pass)
        acceptable_top_1_correct += int(acceptable_top_1_pass)
        acceptable_top_3_correct += int(acceptable_top_3_pass)

        if not acceptable_top_3_pass:
            acceptable_top_3_failures.append(
                {
                    "id": case["id"],
                    "question": case["question"],
                    "primary": primary,
                    "acceptable": acceptable,
                    "sections": sections,
                }
            )

        print(f"Evaluation ID: {case['id']}")
        print(f"Question: {case['question']}")
        print(f"Primary section: {primary}")
        print(f"Acceptable section(s): {', '.join(acceptable)}")
        for rank, section in enumerate(sections, start=1):
            print(f"Rank {rank} section: {section}")
        print(f"Primary Top-1: {'PASS' if primary_top_1_pass else 'FAIL'}")
        print(f"Primary Top-3: {'PASS' if primary_top_3_pass else 'FAIL'}")
        print(
            f"Acceptable Top-1: "
            f"{'PASS' if acceptable_top_1_pass else 'FAIL'}"
        )
        print(
            f"Acceptable Top-3: "
            f"{'PASS' if acceptable_top_3_pass else 'FAIL'}"
        )
        print()

    total_cases = len(cases)
    primary_top_1_accuracy = primary_top_1_correct / total_cases * 100
    primary_top_3_accuracy = primary_top_3_correct / total_cases * 100
    acceptable_top_1_accuracy = acceptable_top_1_correct / total_cases * 100
    acceptable_top_3_accuracy = acceptable_top_3_correct / total_cases * 100

    print("SUMMARY")
    print(f"Total cases: {total_cases}")
    print(
        f"Primary Top-1: {primary_top_1_correct}/{total_cases} "
        f"= {primary_top_1_accuracy:.2f}%"
    )
    print(
        f"Primary Top-3: {primary_top_3_correct}/{total_cases} "
        f"= {primary_top_3_accuracy:.2f}%"
    )
    print(
        f"Acceptable Top-1: {acceptable_top_1_correct}/{total_cases} "
        f"= {acceptable_top_1_accuracy:.2f}%"
    )
    print(
        f"Acceptable Top-3: {acceptable_top_3_correct}/{total_cases} "
        f"= {acceptable_top_3_accuracy:.2f}%"
    )

    print("\nACCEPTABLE TOP-3 FAILURES")
    if not acceptable_top_3_failures:
        print("None")

    for failure in acceptable_top_3_failures:
        print(f"Evaluation ID: {failure['id']}")
        print(f"Question: {failure['question']}")
        print(f"Primary section: {failure['primary']}")
        print(f"Acceptable section(s): {', '.join(failure['acceptable'])}")
        print(f"Retrieved section(s): {', '.join(failure['sections'])}")


if __name__ == "__main__":
    main()