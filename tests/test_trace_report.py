import tempfile
import unittest
from pathlib import Path

from trace_report import calculate_trace_report, parse_trace_file


def make_trace(
    status="success",
    duration=100.0,
    cost=0.001,
    tool_names=None,
    error_type=None,
):
    trace = {
        "status": status,
        "total_duration_ms": duration,
        "estimated_total_api_cost_usd": cost,
        "model_calls": [{}, {}],
        "embedding_calls": [{}],
        "tool_calls": [
            {"name": name} for name in (tool_names or [])
        ],
    }
    if error_type is not None:
        trace["error_type"] = error_type
    return trace


class TraceReportTests(unittest.TestCase):
    def test_success_and_error_counts(self):
        traces = [
            make_trace(status="success"),
            make_trace(status="success"),
            make_trace(status="error", error_type="ValueError"),
        ]

        report = calculate_trace_report(traces)

        self.assertEqual(report["total_valid_traces"], 3)
        self.assertEqual(report["successful_traces"], 2)
        self.assertEqual(report["error_traces"], 1)
        self.assertAlmostEqual(
            report["success_rate_percentage"],
            200 / 3,
        )

    def test_average_latency(self):
        traces = [
            make_trace(duration=100),
            make_trace(duration=200),
            make_trace(duration=300),
        ]

        report = calculate_trace_report(traces)

        self.assertEqual(report["latency"]["average_ms"], 200)

    def test_median_latency(self):
        traces = [
            make_trace(duration=300),
            make_trace(duration=100),
            make_trace(duration=200),
            make_trace(duration=400),
        ]

        report = calculate_trace_report(traces)

        self.assertEqual(report["latency"]["median_ms"], 250)

    def test_nearest_rank_p95_latency(self):
        traces = [
            make_trace(duration=duration)
            for duration in range(1, 21)
        ]

        report = calculate_trace_report(traces)

        self.assertEqual(report["latency"]["p95_ms"], 19)

    def test_total_and_average_cost(self):
        traces = [
            make_trace(cost=0.001),
            make_trace(cost=0.003),
        ]

        report = calculate_trace_report(traces)

        self.assertAlmostEqual(report["cost"]["total_usd"], 0.004)
        self.assertAlmostEqual(report["cost"]["average_usd"], 0.002)

    def test_missing_cost_data_counts_as_zero(self):
        trace_with_cost = make_trace(cost=0.002)
        trace_without_cost = make_trace()
        del trace_without_cost["estimated_total_api_cost_usd"]

        report = calculate_trace_report(
            [trace_with_cost, trace_without_cost]
        )

        self.assertEqual(
            report["cost"]["traces_without_cost_data"],
            1,
        )
        self.assertAlmostEqual(report["cost"]["total_usd"], 0.002)
        self.assertAlmostEqual(report["cost"]["average_usd"], 0.001)
        self.assertEqual(report["cost"]["minimum_usd"], 0)

    def test_tool_usage_counts(self):
        traces = [
            make_trace(
                tool_names=[
                    "search_company_knowledge",
                    "calculate_delivery_timeline",
                ]
            ),
            make_trace(tool_names=["search_company_knowledge"]),
        ]

        report = calculate_trace_report(traces)

        self.assertEqual(report["calls"]["tool"], 3)
        self.assertEqual(
            report["tool_usage"]["search_company_knowledge"],
            2,
        )
        self.assertEqual(
            report["tool_usage"]["calculate_delivery_timeline"],
            1,
        )

    def test_malformed_jsonl_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "traces.jsonl"
            path.write_text(
                '{"status": "success"}\n'
                "not valid json\n"
                "\n"
                "[]\n"
                '{"status": "error"}\n',
                encoding="utf-8",
            )

            traces, malformed_lines = parse_trace_file(path)

        self.assertEqual(len(traces), 2)
        self.assertEqual(malformed_lines, 2)

    def test_empty_trace_file_is_safe(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "traces.jsonl"
            path.write_text("", encoding="utf-8")

            traces, malformed_lines = parse_trace_file(path)
            report = calculate_trace_report(traces, malformed_lines)

        self.assertEqual(report["total_valid_traces"], 0)
        self.assertEqual(report["success_rate_percentage"], 0)
        self.assertEqual(report["latency"]["average_ms"], 0)
        self.assertEqual(report["latency"]["median_ms"], 0)
        self.assertEqual(report["latency"]["p95_ms"], 0)
        self.assertEqual(report["cost"]["total_usd"], 0)


if __name__ == "__main__":
    unittest.main()