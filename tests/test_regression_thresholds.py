import unittest

from regression_thresholds import (
    RETRIEVAL_ACCEPTABLE_TOP_3,
    check_regression_metrics,
    check_threshold,
)


CURRENT_BASELINES = {
    "retrieval_acceptable_top_3": 94.44,
    "agent_tool_selection": 100.0,
    "agent_answer_overall": 100.0,
    "multi_tool_routing": 100.0,
    "multi_tool_combinations": 100.0,
}


class RegressionThresholdTests(unittest.TestCase):
    def test_all_current_baselines_pass(self):
        result = check_regression_metrics(CURRENT_BASELINES)

        self.assertTrue(result["overall_pass"])
        self.assertTrue(
            all(check["passed"] for check in result["checks"].values())
        )

    def test_retrieval_at_threshold_passes(self):
        result = check_threshold(
            "retrieval_acceptable_top_3",
            94.0,
            RETRIEVAL_ACCEPTABLE_TOP_3,
        )

        self.assertTrue(result["passed"])

    def test_retrieval_below_threshold_fails(self):
        result = check_threshold(
            "retrieval_acceptable_top_3",
            93.99,
            RETRIEVAL_ACCEPTABLE_TOP_3,
        )

        self.assertFalse(result["passed"])

    def test_tool_selection_below_threshold_fails(self):
        result = check_threshold("agent_tool_selection", 99.0, 100.0)

        self.assertFalse(result["passed"])

    def test_one_failed_metric_fails_overall(self):
        metrics = dict(CURRENT_BASELINES)
        metrics["multi_tool_routing"] = 99.0

        result = check_regression_metrics(metrics)

        self.assertFalse(result["overall_pass"])
        self.assertFalse(result["checks"]["multi_tool_routing"]["passed"])

    def test_value_above_threshold_passes(self):
        result = check_threshold("example_metric", 101.0, 100.0)

        self.assertEqual(
            result,
            {
                "metric": "example_metric",
                "actual": 101.0,
                "required": 100.0,
                "passed": True,
            },
        )


if __name__ == "__main__":
    unittest.main()