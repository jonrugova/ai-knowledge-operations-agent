import json
from pathlib import Path

from agent import answer_question


EVAL_PATH = Path("evaluations/multi_tool_combination_eval.json")


def display_tools(tools):
    return ", ".join(tools) if tools else "NONE"


def answer_matches(answer, expected_answer_terms):
    answer_lower = answer.lower()
    return all(
        any(term.lower() in answer_lower for term in alternatives)
        for alternatives in expected_answer_terms
    )


def main():
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    tool_passes = 0
    answer_passes = 0
    overall_passes = 0
    failures = []

    for case in cases:
        answer, tool_calls = answer_question(
            case["question"],
            requester_id="evaluation",
        )
        actual_tools = [tool_call["name"] for tool_call in tool_calls]

        tool_pass = set(actual_tools) == set(case["expected_tools"])
        answer_pass = answer_matches(
            answer,
            case["expected_answer_terms"],
        )
        overall_pass = tool_pass and answer_pass

        tool_passes += int(tool_pass)
        answer_passes += int(answer_pass)
        overall_passes += int(overall_pass)

        if not overall_pass:
            failures.append(
                {
                    "id": case["id"],
                    "question": case["question"],
                    "expected_tools": case["expected_tools"],
                    "actual_tools": actual_tools,
                    "tool_pass": tool_pass,
                    "answer": answer,
                    "answer_pass": answer_pass,
                }
            )

        print(f"ID: {case['id']}")
        print(f"Question: {case['question']}")
        print(f"Expected tools: {display_tools(case['expected_tools'])}")
        print(f"Actual tools: {display_tools(actual_tools)}")
        print(f"Tool: {'PASS' if tool_pass else 'FAIL'}")
        print(f"Final answer: {answer}")
        print(f"Answer: {'PASS' if answer_pass else 'FAIL'}")
        print(f"Overall: {'PASS' if overall_pass else 'FAIL'}")
        print()

    total_cases = len(cases)

    print("SUMMARY")
    print(f"Total cases: {total_cases}")
    print(
        f"Tool-combination accuracy: {tool_passes}/{total_cases} "
        f"= {tool_passes / total_cases * 100:.2f}%"
    )
    print(
        f"Answer accuracy: {answer_passes}/{total_cases} "
        f"= {answer_passes / total_cases * 100:.2f}%"
    )
    print(
        f"Overall accuracy: {overall_passes}/{total_cases} "
        f"= {overall_passes / total_cases * 100:.2f}%"
    )

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
        print(f"Tool: {'PASS' if failure['tool_pass'] else 'FAIL'}")
        print(f"Final answer: {failure['answer']}")
        print(f"Answer: {'PASS' if failure['answer_pass'] else 'FAIL'}")


if __name__ == "__main__":
    main()