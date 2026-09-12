import json
import math
from collections import Counter
from pathlib import Path
from statistics import median


TRACES_PATH = Path("data/traces.jsonl")


def parse_trace_file(path: Path):
    traces = []
    malformed_lines = 0

    if not path.exists():
        return traces, malformed_lines

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            trace = json.loads(line)
        except json.JSONDecodeError:
            malformed_lines += 1
            continue
        if not isinstance(trace, dict):
            malformed_lines += 1
            continue
        traces.append(trace)

    return traces, malformed_lines


def nearest_rank_percentile(values, percentile):
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = math.ceil(percentile / 100 * len(ordered))
    return ordered[max(0, rank - 1)]


def calculate_trace_report(traces, malformed_lines=0):
    total_traces = len(traces)
    successful_traces = sum(
        trace.get("status") == "success" for trace in traces
    )
    error_traces = sum(
        trace.get("status") == "error" for trace in traces
    )
    success_rate = (
        successful_traces / total_traces * 100
        if total_traces
        else 0.0
    )

    durations = [
        float(trace.get("total_duration_ms", 0) or 0)
        for trace in traces
    ]
    average_latency = (
        sum(durations) / len(durations) if durations else 0.0
    )

    costs = []
    traces_without_cost_data = 0
    for trace in traces:
        if "estimated_total_api_cost_usd" not in trace:
            traces_without_cost_data += 1
            costs.append(0.0)
        else:
            costs.append(
                float(
                    trace.get("estimated_total_api_cost_usd", 0) or 0
                )
            )

    total_cost = sum(costs)
    average_cost = total_cost / total_traces if total_traces else 0.0

    tool_usage = Counter()
    total_tool_calls = 0
    for trace in traces:
        tool_calls = trace.get("tool_calls", [])
        total_tool_calls += len(tool_calls)
        for tool_call in tool_calls:
            name = tool_call.get("name")
            if name:
                tool_usage[name] += 1

    error_types = Counter(
        trace.get("error_type", "unknown")
        for trace in traces
        if trace.get("status") == "error"
    )

    return {
        "total_valid_traces": total_traces,
        "successful_traces": successful_traces,
        "error_traces": error_traces,
        "success_rate_percentage": success_rate,
        "malformed_trace_lines": malformed_lines,
        "latency": {
            "average_ms": average_latency,
            "minimum_ms": min(durations) if durations else 0.0,
            "maximum_ms": max(durations) if durations else 0.0,
            "median_ms": median(durations) if durations else 0.0,
            "p95_ms": nearest_rank_percentile(durations, 95),
        },
        "cost": {
            "total_usd": total_cost,
            "average_usd": average_cost,
            "minimum_usd": min(costs) if costs else 0.0,
            "maximum_usd": max(costs) if costs else 0.0,
            "traces_without_cost_data": traces_without_cost_data,
        },
        "calls": {
            "model": sum(
                len(trace.get("model_calls", [])) for trace in traces
            ),
            "embedding": sum(
                len(trace.get("embedding_calls", []))
                for trace in traces
            ),
            "tool": total_tool_calls,
        },
        "tool_usage": tool_usage,
        "error_types": error_types,
    }


def print_trace_report(report):
    print("AI KNOWLEDGE AGENT — TRACE REPORT")
    print()
    print("REQUESTS")
    print(f"Total valid traces: {report['total_valid_traces']}")
    print(f"Successful traces: {report['successful_traces']}")
    print(f"Error traces: {report['error_traces']}")
    print(
        f"Success rate: "
        f"{report['success_rate_percentage']:.2f}%"
    )
    print(
        f"Malformed trace lines: {report['malformed_trace_lines']}"
    )
    print()

    latency = report["latency"]
    print("LATENCY")
    print(f"Average: {latency['average_ms']:.2f} ms")
    print(f"Minimum: {latency['minimum_ms']:.2f} ms")
    print(f"Maximum: {latency['maximum_ms']:.2f} ms")
    print(f"Median: {latency['median_ms']:.2f} ms")
    print(f"P95: {latency['p95_ms']:.2f} ms")
    print()

    cost = report["cost"]
    print("ESTIMATED API COST")
    print(f"Total: ${cost['total_usd']:.8f}")
    print(f"Average per valid trace: ${cost['average_usd']:.8f}")
    print(f"Minimum request cost: ${cost['minimum_usd']:.8f}")
    print(f"Maximum request cost: ${cost['maximum_usd']:.8f}")
    print(
        f"Traces without cost data: "
        f"{cost['traces_without_cost_data']}"
    )
    print()

    calls = report["calls"]
    print("CALLS")
    print(f"Model calls: {calls['model']}")
    print(f"Embedding calls: {calls['embedding']}")
    print(f"Tool calls: {calls['tool']}")
    print()

    print("TOOL USAGE")
    if report["tool_usage"]:
        for name, count in report["tool_usage"].most_common():
            print(f"{name}: {count}")
    else:
        print("None")
    print()

    print("ERRORS")
    if report["error_types"]:
        for error_type, count in report["error_types"].most_common():
            print(f"{error_type}: {count}")
    else:
        print("None")


def main():
    traces, malformed_lines = parse_trace_file(TRACES_PATH)
    report = calculate_trace_report(traces, malformed_lines)
    print_trace_report(report)


if __name__ == "__main__":
    main()