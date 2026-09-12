import json
import tempfile
import unittest
from pathlib import Path

import observability


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_traces_path = observability.TRACES_PATH
        observability.TRACES_PATH = (
            Path(self.temporary_directory.name) / "traces.jsonl"
        )

    def tearDown(self):
        observability.TRACES_PATH = self.original_traces_path
        self.temporary_directory.cleanup()

    def read_traces(self):
        return [
            json.loads(line)
            for line in observability.TRACES_PATH.read_text(
                encoding="utf-8"
            ).splitlines()
        ]

    def test_trace_id_exists(self):
        trace = observability.start_trace("Test question")

        self.assertTrue(trace["trace_id"])

    def test_timing_values_are_non_negative(self):
        trace = observability.start_trace("Test question")
        observability.record_model_call(trace, 2.5)
        observability.record_tool_call(trace, "example_tool", 1.5)
        completed = observability.complete_trace(trace, "success")

        self.assertGreaterEqual(completed["total_duration_ms"], 0)
        self.assertGreaterEqual(
            completed["model_calls"][0]["duration_ms"],
            0,
        )
        self.assertGreaterEqual(
            completed["tool_calls"][0]["duration_ms"],
            0,
        )

    def test_success_trace_can_be_written(self):
        trace = observability.start_trace("Test question")

        completed = observability.persist_completed_trace(
            trace,
            "success",
        )

        self.assertEqual(self.read_traces(), [completed])
        self.assertEqual(completed["status"], "success")

    def test_error_trace_can_be_written(self):
        trace = observability.start_trace("Test question")

        completed = observability.persist_completed_trace(
            trace,
            "error",
            "ValueError",
        )

        self.assertEqual(self.read_traces(), [completed])
        self.assertEqual(completed["status"], "error")
        self.assertEqual(completed["error_type"], "ValueError")

    def test_multiple_traces_append(self):
        first = observability.start_trace("First question")
        second = observability.start_trace("Second question")

        observability.persist_completed_trace(first, "success")
        observability.persist_completed_trace(second, "success")

        traces = self.read_traces()
        self.assertEqual(len(traces), 2)
        self.assertEqual(
            [trace["question"] for trace in traces],
            ["First question", "Second question"],
        )

    def test_trace_contains_no_secret_fields(self):
        trace = observability.start_trace("Test question")
        completed = observability.persist_completed_trace(
            trace,
            "success",
        )

        forbidden_fields = {
            "OPENAI_API_KEY",
            "DATABASE_URL",
            "embedding",
            "embeddings",
            "vector",
            "vectors",
            "tool_output",
            "tool_outputs",
        }
        self.assertTrue(forbidden_fields.isdisjoint(completed))

    def test_cost_calculation_with_uncached_input(self):
        cost = observability.calculate_luna_cost(
            input_tokens=1_000_000,
            cached_input_tokens=0,
            output_tokens=1_000_000,
        )

        self.assertAlmostEqual(cost, 1.40)

    def test_cost_calculation_with_cached_input(self):
        cost = observability.calculate_luna_cost(
            input_tokens=1_000_000,
            cached_input_tokens=250_000,
            output_tokens=0,
        )

        self.assertAlmostEqual(cost, 0.155)

    def test_multiple_model_calls_aggregate_correctly(self):
        trace = observability.start_trace("Test question")
        observability.record_model_call(
            trace,
            1.0,
            input_tokens=100,
            cached_input_tokens=20,
            output_tokens=30,
            total_tokens=130,
        )
        observability.record_model_call(
            trace,
            2.0,
            input_tokens=200,
            cached_input_tokens=40,
            output_tokens=50,
            total_tokens=250,
        )

        completed = observability.complete_trace(trace, "success")

        self.assertEqual(len(completed["model_calls"]), 2)
        self.assertEqual(
            completed["estimated_model_cost_usd"],
            sum(
                call["estimated_cost_usd"]
                for call in completed["model_calls"]
            ),
        )

    def test_request_level_token_totals_are_correct(self):
        trace = observability.start_trace("Test question")
        observability.record_model_call(
            trace,
            1.0,
            input_tokens=100,
            cached_input_tokens=20,
            output_tokens=30,
            total_tokens=130,
        )
        observability.record_model_call(
            trace,
            2.0,
            input_tokens=200,
            cached_input_tokens=40,
            output_tokens=50,
            total_tokens=250,
        )

        completed = observability.complete_trace(trace, "success")

        self.assertEqual(
            completed["usage"],
            {
                "input_tokens": 300,
                "cached_input_tokens": 60,
                "output_tokens": 80,
                "total_tokens": 380,
            },
        )

    def test_request_cost_equals_sum_of_model_call_costs(self):
        trace = observability.start_trace("Test question")
        observability.record_model_call(
            trace,
            1.0,
            input_tokens=1_000,
            cached_input_tokens=100,
            output_tokens=200,
            total_tokens=1_200,
        )
        observability.record_model_call(
            trace,
            2.0,
            input_tokens=2_000,
            cached_input_tokens=500,
            output_tokens=300,
            total_tokens=2_300,
        )

        completed = observability.complete_trace(trace, "success")
        expected = sum(
            call["estimated_cost_usd"]
            for call in completed["model_calls"]
        )

        self.assertAlmostEqual(
            completed["estimated_model_cost_usd"],
            expected,
        )

    def test_zero_token_usage_has_zero_cost(self):
        trace = observability.start_trace("Test question")
        observability.record_model_call(trace, 1.0)

        completed = observability.complete_trace(trace, "success")

        self.assertEqual(
            completed["model_calls"][0]["estimated_cost_usd"],
            0,
        )
        self.assertEqual(completed["estimated_model_cost_usd"], 0)

    def test_embedding_cost_calculation(self):
        trace = observability.start_trace("Test question")

        observability.record_embedding_call(
            trace,
            duration_ms=1.0,
            input_tokens=1_000_000,
            total_tokens=1_000_000,
        )

        self.assertAlmostEqual(
            trace["embedding_calls"][0]["estimated_cost_usd"],
            0.02,
        )

    def test_embedding_call_recording(self):
        trace = observability.start_trace("Test question")

        observability.record_embedding_call(
            trace,
            duration_ms=2.5,
            input_tokens=15,
            total_tokens=15,
        )

        embedding_call = trace["embedding_calls"][0]
        self.assertEqual(embedding_call["duration_ms"], 2.5)
        self.assertEqual(embedding_call["input_tokens"], 15)
        self.assertEqual(embedding_call["total_tokens"], 15)
        self.assertAlmostEqual(
            embedding_call["estimated_cost_usd"],
            0.0000003,
        )

    def test_multiple_embedding_calls_aggregate_correctly(self):
        trace = observability.start_trace("Test question")
        observability.record_embedding_call(trace, 1.0, 10, 10)
        observability.record_embedding_call(trace, 2.0, 20, 20)

        completed = observability.complete_trace(trace, "success")

        self.assertEqual(
            completed["embedding_usage"],
            {
                "input_tokens": 30,
                "total_tokens": 30,
            },
        )
        self.assertAlmostEqual(
            completed["estimated_embedding_cost_usd"],
            30 / 1_000_000 * 0.02,
        )

    def test_model_and_embedding_costs_combine(self):
        trace = observability.start_trace("Test question")
        observability.record_model_call(
            trace,
            1.0,
            input_tokens=1_000,
            output_tokens=100,
            total_tokens=1_100,
        )
        observability.record_embedding_call(
            trace,
            1.0,
            input_tokens=500,
            total_tokens=500,
        )

        completed = observability.complete_trace(trace, "success")

        self.assertAlmostEqual(
            completed["estimated_total_api_cost_usd"],
            completed["estimated_model_cost_usd"]
            + completed["estimated_embedding_cost_usd"],
        )

    def test_zero_embedding_tokens_have_zero_cost(self):
        trace = observability.start_trace("Test question")
        observability.record_embedding_call(trace, 1.0, 0, 0)

        completed = observability.complete_trace(trace, "success")

        self.assertEqual(
            completed["embedding_calls"][0]["estimated_cost_usd"],
            0,
        )
        self.assertEqual(completed["estimated_embedding_cost_usd"], 0)

    def test_request_without_embeddings_has_zero_embedding_cost(self):
        trace = observability.start_trace("Test question")

        completed = observability.complete_trace(trace, "success")

        self.assertEqual(
            completed["embedding_usage"],
            {
                "input_tokens": 0,
                "total_tokens": 0,
            },
        )
        self.assertEqual(completed["estimated_embedding_cost_usd"], 0)
        self.assertEqual(
            completed["estimated_total_api_cost_usd"],
            completed["estimated_model_cost_usd"],
        )


if __name__ == "__main__":
    unittest.main()