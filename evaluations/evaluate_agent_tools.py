import json
from pathlib import Path

from agent import answer_question


EVAL_PATH = Path("evaluations/agent_tool_eval.json")


def yes_no(value: bool):
    return "YES" if value else "NO"


def main():
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    correct_decisions = 0
    failures = []

    for case in cases:
        _, tool_calls = answer_question(
            case["question"],
            requester_id="evaluation",
        )
        actual_tool = bool(tool_calls)
        passed = actual_tool == case["expected_tool"]

        correct_decisions += int(passed)
        if not passed:
            failures.append(
                {
                    "id": case["id"],
                    "question": case["question"],
                    "expected_tool": case["expected_tool"],
                    "actual_tool": actual_tool,
                }
            )

        print(f"ID: {case['id']}")
        print(f"Question: {case['question']}")
        print(f"Expected tool: {yes_no(case['expected_tool'])}")
        print(f"Actual tool: {yes_no(actual_tool)}")
        print(f"Result: {'PASS' if passed else 'FAIL'}")
        print()

    total_cases = len(cases)
    accuracy = correct_decisions / total_cases * 100

    print("SUMMARY")
    print(f"Total cases: {total_cases}")
    print(f"Correct decisions: {correct_decisions}")
    print(f"Tool-selection accuracy: {accuracy:.2f}%")

    print("\nFAILED CASES")
    if not failures:
        print("None")
    for failure in failures:
        print(f"ID: {failure['id']}")
        print(f"Question: {failure['question']}")
        print(f"Expected tool: {yes_no(failure['expected_tool'])}")
        print(f"Actual tool: {yes_no(failure['actual_tool'])}")


if __name__ == "__main__":
    main()