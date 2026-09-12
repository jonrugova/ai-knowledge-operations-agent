import json
from pathlib import Path

from title_aware_search import title_aware_search_knowledge


EVAL_PATH = Path("evaluations/retrieval_eval.json")
VECTOR_BASELINE = {
    "primary_top_1": (13, 72.22),
    "primary_top_3": (16, 88.89),
    "acceptable_top_1": (14, 77.78),
    "acceptable_top_3": (17, 94.44),
}


def metric_results(sections, primary, acceptable):
    return {
        "primary_top_1": bool(sections) and sections[0] == primary,
        "primary_top_3": primary in sections[:3],
        "acceptable_top_1": bool(sections) and sections[0] in acceptable,
        "acceptable_top_3": any(
            section in acceptable for section in sections[:3]
        ),
    }


def main():
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    correct = {metric: 0 for metric in VECTOR_BASELINE}
    failures = []
    regressions = []
    eval_015_results = None

    for case in cases:
        all_results = title_aware_search_knowledge(
            case["question"],
            top_k=18,
        )
        title_results = all_results[:3]
        vector_results = sorted(
            all_results,
            key=lambda result: result["vector_similarity"],
            reverse=True,
        )[:3]

        title_sections = [result["section"] for result in title_results]
        vector_sections = [result["section"] for result in vector_results]
        primary = case["primary_section"]
        acceptable = case["acceptable_sections"]

        title_metrics = metric_results(
            title_sections,
            primary,
            acceptable,
        )
        vector_metrics = metric_results(
            vector_sections,
            primary,
            acceptable,
        )

        for metric, passed in title_metrics.items():
            correct[metric] += int(passed)

        regressed_metrics = [
            metric
            for metric in title_metrics
            if vector_metrics[metric] and not title_metrics[metric]
        ]
        if regressed_metrics:
            regressions.append(
                {
                    "id": case["id"],
                    "metrics": regressed_metrics,
                    "vector_sections": vector_sections,
                    "title_sections": title_sections,
                }
            )

        if not title_metrics["acceptable_top_3"]:
            failures.append(
                {
                    "id": case["id"],
                    "question": case["question"],
                    "primary": primary,
                    "acceptable": acceptable,
                    "sections": title_sections,
                }
            )

        if case["id"] == "eval_015":
            eval_015_results = {
                "case": case,
                "results": title_results,
                "metrics": title_metrics,
            }

        print(f"Evaluation ID: {case['id']}")
        for rank, result in enumerate(title_results, start=1):
            print(
                f"Rank {rank}: {result['section']} | "
                f"Vector similarity: "
                f"{result['vector_similarity']:.6f} | "
                f"Title overlap: {result['title_overlap']} | "
                f"Title bonus: {result['title_bonus']:.2f} | "
                f"Final score: {result['final_score']:.6f}"
            )
        for metric, passed in title_metrics.items():
            label = metric.replace("_", " ").title()
            print(f"{label}: {'PASS' if passed else 'FAIL'}")
        print()

    total = len(cases)
    print("SUMMARY")
    for metric, count in correct.items():
        label = metric.replace("_", " ").title()
        print(f"{label}: {count}/{total} = {count / total * 100:.2f}%")

    print("\nEVAL_015 FULL RESULT")
    case = eval_015_results["case"]
    print(f"Question: {case['question']}")
    print(f"Primary section: {case['primary_section']}")
    print(
        f"Acceptable section(s): "
        f"{', '.join(case['acceptable_sections'])}"
    )
    for rank, result in enumerate(eval_015_results["results"], start=1):
        print(f"Rank {rank}")
        print(f"ID: {result['id']}")
        print(f"Section: {result['section']}")
        print(f"Content: {result['content']}")
        print(
            f"Vector similarity: {result['vector_similarity']:.6f}"
        )
        print(f"Title overlap: {result['title_overlap']}")
        print(f"Title bonus: {result['title_bonus']:.2f}")
        print(f"Final score: {result['final_score']:.6f}")
    for metric, passed in eval_015_results["metrics"].items():
        label = metric.replace("_", " ").title()
        print(f"{label}: {'PASS' if passed else 'FAIL'}")

    print("\nACCEPTABLE TOP-3 FAILURES")
    if not failures:
        print("None")
    for failure in failures:
        print(f"Evaluation ID: {failure['id']}")
        print(f"Question: {failure['question']}")
        print(f"Primary section: {failure['primary']}")
        print(
            f"Acceptable section(s): "
            f"{', '.join(failure['acceptable'])}"
        )
        print(f"Retrieved section(s): {', '.join(failure['sections'])}")

    print("\nWORSE THAN VECTOR BASELINE")
    if not regressions:
        print("None")
    for regression in regressions:
        labels = [
            metric.replace("_", " ").title()
            for metric in regression["metrics"]
        ]
        print(f"Evaluation ID: {regression['id']}")
        print(f"Worse metric(s): {', '.join(labels)}")
        print(
            f"Vector section(s): "
            f"{', '.join(regression['vector_sections'])}"
        )
        print(
            f"Title-aware section(s): "
            f"{', '.join(regression['title_sections'])}"
        )

    print("\nBASELINE VS TITLE-AWARE")
    for metric, (baseline_count, baseline_accuracy) in (
        VECTOR_BASELINE.items()
    ):
        label = metric.replace("_", " ").title()
        title_count = correct[metric]
        title_accuracy = title_count / total * 100
        print(
            f"{label}: Vector {baseline_count}/{total} "
            f"= {baseline_accuracy:.2f}% | "
            f"Title-aware {title_count}/{total} "
            f"= {title_accuracy:.2f}%"
        )


if __name__ == "__main__":
    main()