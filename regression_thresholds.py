RETRIEVAL_ACCEPTABLE_TOP_3 = 94.0
AGENT_TOOL_SELECTION = 100.0
AGENT_ANSWER_OVERALL = 100.0
MULTI_TOOL_ROUTING = 100.0
MULTI_TOOL_COMBINATIONS = 100.0


THRESHOLDS = {
    "retrieval_acceptable_top_3": RETRIEVAL_ACCEPTABLE_TOP_3,
    "agent_tool_selection": AGENT_TOOL_SELECTION,
    "agent_answer_overall": AGENT_ANSWER_OVERALL,
    "multi_tool_routing": MULTI_TOOL_ROUTING,
    "multi_tool_combinations": MULTI_TOOL_COMBINATIONS,
}


def check_threshold(metric_name: str, actual: float, required: float):
    return {
        "metric": metric_name,
        "actual": actual,
        "required": required,
        "passed": actual >= required,
    }


def check_regression_metrics(metrics: dict):
    checks = {
        metric_name: check_threshold(
            metric_name,
            metrics[metric_name],
            required,
        )
        for metric_name, required in THRESHOLDS.items()
    }

    return {
        "checks": checks,
        "overall_pass": all(
            check["passed"] for check in checks.values()
        ),
    }