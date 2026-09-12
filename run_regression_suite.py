import subprocess
import sys
import time


SUITES = [
    "evaluations.evaluate_retrieval",
    "evaluations.evaluate_agent_tools",
    "evaluations.evaluate_agent_answers",
    "evaluations.evaluate_multi_tools",
    "evaluations.evaluate_multi_tool_combinations",
]


def main():
    # Regression tests detect when later changes break established behavior.
    print("REGRESSION SUITE")
    print()

    suite_results = []
    regression_start = time.perf_counter()

    for suite in SUITES:
        suite_start = time.perf_counter()

        # Each evaluation module continues to own its own test logic.
        completed = subprocess.run(
            [sys.executable, "-m", suite],
            capture_output=True,
            text=True,
            check=False,
        )

        duration = time.perf_counter() - suite_start
        passed = completed.returncode == 0
        suite_results.append(
            {
                "name": suite,
                "passed": passed,
                "duration": duration,
            }
        )

        print(f"SUITE: {suite}")
        print(f"RESULT: {'PASS' if passed else 'FAIL'}")
        print(f"DURATION: {duration:.2f} seconds")
        print("OUTPUT:")
        if completed.stdout:
            print(completed.stdout, end="")
        else:
            print("(no stdout)")

        if completed.stderr:
            print("STDERR:")
            print(completed.stderr, end="")
        print()

    # This runner only orchestrates the existing evaluation suites.
    total_runtime = time.perf_counter() - regression_start
    passed_suites = sum(result["passed"] for result in suite_results)
    total_suites = len(suite_results)
    failed_suites = total_suites - passed_suites
    overall_passed = failed_suites == 0

    print("SUMMARY")
    print(f"Total suites: {total_suites}")
    print(f"Passed suites: {passed_suites}")
    print(f"Failed suites: {failed_suites}")
    print(f"Total runtime: {total_runtime:.2f} seconds")
    print(f"Overall: {'PASS' if overall_passed else 'FAIL'}")

    if not overall_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()