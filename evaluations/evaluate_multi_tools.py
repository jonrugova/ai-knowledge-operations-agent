import json
from pathlib import Path

from agent import answer_question


EVAL_PATH = Path("evaluations/multi_tool_eval.json")


def display_tools(tools):
    return ", ".join(tools) if tools else "NONE"


def main():
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    correct_cases = 0
    failures = []

    for case in cases:
        _, tool_calls = answer_question(
            case["question"],
            requester_id="evaluation",
        )
        actual_tools = [tool_call["name"] for tool_call in tool_calls]
        passed = actual_tools == case["expected_tools"]

        correct_cases += int(passed)
        if not passed:
            failures.append(
                {
                    "id": case["id"],
                    "question": case["question"],
                    "expected_tools": case["expected_tools"],
                    "actual_tools": actual_tools,
                }
            )

        print(f"ID: {case['id']}")
        print(f"Question: {case['question']}")
        print(f"Expected tools: {display_tools(case['expected_tools'])}")
        print(f"Actual tools: {display_tools(actual_tools)}")
        print(f"Result: {'PASS' if passed else 'FAIL'}")
        print()

    total_cases = len(cases)
    accuracy = correct_cases / total_cases * 100

    print("SUMMARY")
    print(f"Total cases: {total_cases}")
    print(f"Correct cases: {correct_cases}")
    print(f"Tool-routing accuracy: {accuracy:.2f}%")

    print("\nFAILED CASES")
    if not failures:
        print("None")
    for failure in failures:
        print(f"ID: {failure['id']}")
        print(f"Question: {failure['question']}")
        print(
            f"Expected tools: "
            f"{display_tools(failure['expected_tools'])}"
        )
        print(
            f"Actual tools: {display_tools(failure['actual_tools'])}"
        )


if __name__ == "__main__":
    main()