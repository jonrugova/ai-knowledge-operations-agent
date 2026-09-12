import json
from pathlib import Path

from agent import answer_question


EVAL_PATH = Path("evaluations/agent_answer_eval.json")


def yes_no(value: bool):
    return "YES" if value else "NO"


def pass_fail(value: bool):
    return "PASS" if value else "FAIL"


def answer_matches(case, answer: str):
    if "expected_exact_answer" in case:
        return answer.strip() == case["expected_exact_answer"]

    answer_lower = answer.lower()
    return all(
        any(term.lower() in answer_lower for term in alternatives)
        for alternatives in case["expected_answer_terms"]
    )


def main():
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    overall_passes = 0
    tool_passes = 0
    retrieval_passes = 0
    retrieval_checks = 0
    answer_passes = 0
    failures = []

    for case in cases:
        answer, tool_calls = answer_question(
            case["question"],
            requester_id="evaluation",
        )
        actual_tool = bool(tool_calls)
        sections = [
            section
            for tool_call in tool_calls
            for section in tool_call["sections"]
        ]

        tool_pass = actual_tool == case["expected_tool"]
        tool_passes += int(tool_pass)

        retrieval_applicable = (
            case["expected_tool"] and bool(case["acceptable_sections"])
        )
        if retrieval_applicable:
            retrieval_checks += 1
            retrieval_pass = any(
                section in case["acceptable_sections"]
                for section in sections
            )
            retrieval_passes += int(retrieval_pass)
        else:
            retrieval_pass = None

        answer_pass = answer_matches(case, answer)
        answer_passes += int(answer_pass)

        overall_pass = (
            tool_pass
            and (retrieval_pass is None or retrieval_pass)
            and answer_pass
        )
        overall_passes += int(overall_pass)

        if not overall_pass:
            failures.append(
                {
                    "id": case["id"],
                    "question": case["question"],
                    "tool_pass": tool_pass,
                    "retrieval_pass": retrieval_pass,
                    "answer_pass": answer_pass,
                }
            )

        print(f"ID: {case['id']}")
        print(f"Question: {case['question']}")
        print(f"Expected tool: {yes_no(case['expected_tool'])}")
        print(f"Actual tool: {yes_no(actual_tool)}")
        print(
            f"Sections returned: "
            f"{', '.join(sections) if sections else 'None'}"
        )
        print(f"Final answer: {answer}")
        print(f"Tool: {pass_fail(tool_pass)}")
        print(
            f"Retrieval: "
            f"{pass_fail(retrieval_pass) if retrieval_pass is not None else 'N/A'}"
        )
        print(f"Answer: {pass_fail(answer_pass)}")
        print(f"Overall: {pass_fail(overall_pass)}")
        print()

    total_cases = len(cases)

    print("SUMMARY")
    print(f"Total cases: {total_cases}")
    print(f"Overall passes: {overall_passes}")
    print(
        f"Overall accuracy: "
        f"{overall_passes / total_cases * 100:.2f}%"
    )
    print(
        f"Tool check accuracy: "
        f"{tool_passes}/{total_cases} "
        f"= {tool_passes / total_cases * 100:.2f}%"
    )
    print(
        f"Retrieval check accuracy: "
        f"{retrieval_passes}/{retrieval_checks} "
        f"= {retrieval_passes / retrieval_checks * 100:.2f}%"
    )
    print(
        f"Answer check accuracy: "
        f"{answer_passes}/{total_cases} "
        f"= {answer_passes / total_cases * 100:.2f}%"
    )

    print("\nFAILED CASES")
    if not failures:
        print("None")
    for failure in failures:
        print(f"ID: {failure['id']}")
        print(f"Question: {failure['question']}")
        print(f"Tool: {pass_fail(failure['tool_pass'])}")
        retrieval_result = (
            pass_fail(failure["retrieval_pass"])
            if failure["retrieval_pass"] is not None
            else "N/A"
        )
        print(f"Retrieval: {retrieval_result}")
        print(f"Answer: {pass_fail(failure['answer_pass'])}")


if __name__ == "__main__":
    main()