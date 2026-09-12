import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


TRACES_PATH = Path("data/traces.jsonl")

LUNA_INPUT_COST_PER_MILLION = 0.20
LUNA_CACHED_INPUT_COST_PER_MILLION = 0.02
LUNA_OUTPUT_COST_PER_MILLION = 1.20
EMBEDDING_INPUT_COST_PER_MILLION = 0.02


def start_trace(question: str):
    return {
        "trace_id": str(uuid4()),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "model_calls": [],
        "embedding_calls": [],
        "tool_calls": [],
        "tool_names": [],
        "_started_counter": time.perf_counter(),
    }


def calculate_luna_cost(
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
):
    uncached_input_tokens = max(
        0,
        input_tokens - cached_input_tokens,
    )
    return (
        uncached_input_tokens
        / 1_000_000
        * LUNA_INPUT_COST_PER_MILLION
        + cached_input_tokens
        / 1_000_000
        * LUNA_CACHED_INPUT_COST_PER_MILLION
        + output_tokens
        / 1_000_000
        * LUNA_OUTPUT_COST_PER_MILLION
    )


def record_model_call(
    trace: dict,
    duration_ms: float,
    input_tokens: int = 0,
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
):
    input_tokens = max(0, input_tokens)
    cached_input_tokens = max(0, cached_input_tokens)
    output_tokens = max(0, output_tokens)
    total_tokens = max(0, total_tokens)
    estimated_cost = calculate_luna_cost(
        input_tokens,
        cached_input_tokens,
        output_tokens,
    )

    trace["model_calls"].append(
        {
            "duration_ms": max(0.0, duration_ms),
            "input_tokens": input_tokens,
            "cached_input_tokens": cached_input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost,
        }
    )


def record_tool_call(trace: dict, name: str, duration_ms: float):
    trace["tool_calls"].append(
        {
            "name": name,
            "duration_ms": max(0.0, duration_ms),
        }
    )
    trace["tool_names"].append(name)


def record_embedding_call(
    trace: dict,
    duration_ms: float,
    input_tokens: int,
    total_tokens: int,
):
    input_tokens = max(0, input_tokens)
    total_tokens = max(0, total_tokens)
    estimated_cost = (
        input_tokens
        / 1_000_000
        * EMBEDDING_INPUT_COST_PER_MILLION
    )
    trace["embedding_calls"].append(
        {
            "duration_ms": max(0.0, duration_ms),
            "input_tokens": input_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost,
        }
    )


def complete_trace(
    trace: dict,
    status: str,
    error_type: str | None = None,
):
    completed = {
        key: value
        for key, value in trace.items()
        if not key.startswith("_")
    }
    started_counter = trace["_started_counter"]
    completed["total_duration_ms"] = max(
        0.0,
        (time.perf_counter() - started_counter) * 1000,
    )
    completed["usage"] = {
        "input_tokens": sum(
            call["input_tokens"] for call in completed["model_calls"]
        ),
        "cached_input_tokens": sum(
            call["cached_input_tokens"]
            for call in completed["model_calls"]
        ),
        "output_tokens": sum(
            call["output_tokens"] for call in completed["model_calls"]
        ),
        "total_tokens": sum(
            call["total_tokens"] for call in completed["model_calls"]
        ),
    }
    completed["estimated_model_cost_usd"] = sum(
        call["estimated_cost_usd"]
        for call in completed["model_calls"]
    )
    completed["embedding_usage"] = {
        "input_tokens": sum(
            call["input_tokens"]
            for call in completed["embedding_calls"]
        ),
        "total_tokens": sum(
            call["total_tokens"]
            for call in completed["embedding_calls"]
        ),
    }
    completed["estimated_embedding_cost_usd"] = sum(
        call["estimated_cost_usd"]
        for call in completed["embedding_calls"]
    )
    completed["estimated_total_api_cost_usd"] = (
        completed["estimated_model_cost_usd"]
        + completed["estimated_embedding_cost_usd"]
    )
    completed["status"] = status
    if error_type is not None:
        completed["error_type"] = error_type
    return completed


def write_trace(trace: dict, path: Path | None = None):
    destination = path if path is not None else TRACES_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as trace_file:
        trace_file.write(
            json.dumps(trace, ensure_ascii=False) + "\n"
        )


def persist_completed_trace(
    trace: dict,
    status: str,
    error_type: str | None = None,
):
    completed = complete_trace(trace, status, error_type)
    write_trace(completed)
    return completed