"""Repeatable comparisons and portable JSON exports shared by CLI and GUI."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import statistics

from algorithms import Result, bellman_ford, dijkstra
from graph_io import Graph, Number

ALGORITHMS = (dijkstra, bellman_ford)


@dataclass(frozen=True)
class Timing:
    samples_ns: list[int]
    median_us: float
    min_us: float
    max_us: float
    q1_us: float
    q3_us: float


@dataclass(frozen=True)
class Comparison:
    results: list[Result]
    timings: dict[str, Timing]
    repetitions: int
    warmups: int
    consistent: bool


def format_number(value: Number) -> str:
    if value == math.inf:
        return "Tidak ada jalur"
    return str(value) if isinstance(value, int) else f"{value:.12g}"


def costs_equal(left: Number, right: Number) -> bool:
    if left == right:
        return True
    if left == math.inf or right == math.inf:
        return False
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)


def compare(graph: Graph, start: str, goal: str, *, repetitions: int = 31,
            warmups: int = 3, record_steps: bool = True) -> Comparison:
    """Alternate algorithm order to reduce order bias; keep every timing sample.

    Validation and I/O are outside each algorithm's timer. Counters and disabled
    trace dispatch remain included. GUI tracing is a separate untabulated run.
    """
    if not 1 <= repetitions <= 10_000 or not 0 <= warmups <= 1_000:
        raise ValueError("Pengulangan harus 1–10000; pemanasan harus 0–1000.")
    results = [algorithm(graph, start, goal, record_steps=record_steps)
               for algorithm in ALGORITHMS]
    samples: dict[str, list[int]] = {result.name: [] for result in results}
    for index in range(warmups + repetitions):
        order = ALGORITHMS if index % 2 == 0 else ALGORITHMS[::-1]
        for algorithm in order:
            measured = algorithm(graph, start, goal, record_steps=False)
            if index >= warmups:
                samples[measured.name].append(measured.runtime_ns)
    timings = {}
    for name, values in samples.items():
        quartiles = statistics.quantiles(values, n=4, method="inclusive") if len(values) > 1 else values * 3
        timings[name] = Timing(values, statistics.median(values) / 1000,
                               min(values) / 1000, max(values) / 1000,
                               quartiles[0] / 1000, quartiles[2] / 1000)
    return Comparison(results, timings, repetitions, warmups,
                      costs_equal(results[0].cost, results[1].cost))


def comparison_data(comparison: Comparison, graph: Graph, start: str,
                    goal: str, source: str = "") -> dict:
    """JSON uses null for unreachable cost, never the nonstandard Infinity."""
    algorithms = []
    for result in comparison.results:
        algorithms.append({
            "algorithm": result.name, "path": result.path,
            "reachable": bool(result.path),
            "cost": None if result.cost == math.inf else result.cost,
            "metrics": asdict(result.metrics),
            "trace_truncated": result.trace_truncated,
            "timing": asdict(comparison.timings[result.name]),
        })
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": platform.python_version(),
                        "implementation": platform.python_implementation(),
                        "platform": platform.platform(), "processor": platform.processor()},
        "source": source, "start": start, "goal": goal,
        "vertices": len(graph), "directed_edges": sum(map(len, graph.values())),
        "graph": graph, "consistent": comparison.consistent,
        "benchmark": {"repetitions": comparison.repetitions, "warmups": comparison.warmups,
                      "clock": "perf_counter_ns", "trace_recorded_in_timing": False,
                      "includes": "initialization, search, counters, reconstruction",
                      "excludes": "validation, file I/O, trace allocation, layout, animation"},
        "results": algorithms,
    }


def export_json(path: str | Path, data: dict) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                          encoding="utf-8")
