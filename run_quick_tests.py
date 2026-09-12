import subprocess
import sys
import time


TEST_MODULES = [
    "tests.test_offline_safety",
    "tests.test_agent_contracts",
    "tests.test_regression_thresholds",
    "tests.test_observability",
    "tests.test_trace_report",
    "tests.test_api",
    "tests.test_production_config",
    "tests.test_public_repo_safety",
]


def main():
    # Quick tests are deterministic and free, so they should run frequently
    # during development. run_regression_suite.py is the expensive live-AI
    # regression and should run only when relevant AI behavior changes.
    print("QUICK OFFLINE TESTS")
    print()

    results = []
    overall_start = time.perf_counter()

    for module in TEST_MODULES:
        module_start = time.perf_counter()
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", module, "-v"],
            capture_output=True,
            text=True,
            check=False,
        )
        duration = time.perf_counter() - module_start
        passed = completed.returncode == 0
        results.append(
            {
                "module": module,
                "passed": passed,
                "duration": duration,
            }
        )

        print(f"MODULE: {module}")
        print(f"RESULT: {'PASS' if passed else 'FAIL'}")
        print(f"DURATION: {duration:.3f} seconds")
        print("OUTPUT:")
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="")
        if not completed.stdout and not completed.stderr:
            print("(no output)")
        print()

    total_runtime = time.perf_counter() - overall_start
    total_modules = len(results)
    passed_modules = sum(result["passed"] for result in results)
    failed_modules = total_modules - passed_modules
    overall_passed = failed_modules == 0

    print("SUMMARY")
    print(f"Total test modules: {total_modules}")
    print(f"Passed modules: {passed_modules}")
    print(f"Failed modules: {failed_modules}")
    print(f"Total runtime: {total_runtime:.3f} seconds")
    print(f"Overall: {'PASS' if overall_passed else 'FAIL'}")

    if not overall_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()