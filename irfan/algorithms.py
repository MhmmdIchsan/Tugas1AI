"""Two shortest-path algorithms on a shared, nonnegative input domain.

Timing includes initialization, operation counters and reconstruction, but excludes
input validation. Use record_steps=False for timings without animation tracing.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import itertools
import math
from time import perf_counter_ns
from graph_io import Graph, Number, validate_graph


@dataclass(frozen=True)
class Step:
    kind: str  # visit, inspect, relax, pass, done
    node: str | None = None
    neighbor: str | None = None
    distance: Number | None = None
    iteration: int | None = None


@dataclass(frozen=True)
class Metrics:
    inspected_edges: int = 0
    relaxations: int = 0
    settled_vertices: int = 0
    passes: int = 0


@dataclass(frozen=True)
class Result:
    name: str
    path: list[str]
    cost: Number
    runtime_ns: int
    steps: list[Step]
    metrics: Metrics
    trace_truncated: bool = False


class _Trace:
    """Bound trace memory without interrupting the actual search."""
    def __init__(self, enabled: bool, limit: int) -> None:
        if limit < 1:
            raise ValueError("Batas langkah harus minimal 1.")
        self.enabled, self.limit = enabled, limit
        self.steps: list[Step] = []
        self.truncated = False

    def add(self, kind: str, node: str | None = None,
            neighbor: str | None = None, distance: Number | None = None,
            iteration: int | None = None) -> None:
        if not self.enabled:
            return
        if kind == "done" or len(self.steps) < self.limit:
            self.steps.append(Step(kind, node, neighbor, distance, iteration))
        else:
            self.truncated = True


def _path(previous: dict[str, str], start: str, goal: str) -> list[str]:
    if start == goal:
        return [start]
    if goal not in previous:
        return []
    route = [goal]
    while route[-1] != start:
        route.append(previous[route[-1]])
    route.reverse()
    return route


def _sum(cost: Number, weight: Number) -> Number:
    """Do not confuse float overflow with an unreachable vertex."""
    try:
        value = cost + weight
    except OverflowError as exc:
        raise ValueError("Total bobot melampaui kapasitas float; gunakan skala lebih kecil.") from exc
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Total bobot melampaui kapasitas float; gunakan skala lebih kecil.")
    return value


def dijkstra(graph: Graph, start: str, goal: str, *,
             record_steps: bool = True, max_steps: int = 20_000) -> Result:
    """Binary heap with lazy duplicates; stop when goal is settled.

    O(V + E log(E+1)) time and O(V+E) auxiliary space, excluding trace.
    For simple graphs this is commonly bounded by O((V+E) log V).
    """
    validate_graph(graph, start, goal)
    began = perf_counter_ns()
    trace = _Trace(record_steps, max_steps)
    distances: dict[str, Number] = {v: math.inf for v in graph}
    distances[start] = 0
    previous: dict[str, str] = {}
    settled: set[str] = set()
    counter = itertools.count()
    queue = [(0, next(counter), start)]
    inspected = relaxed = 0
    while queue:
        cost, _, vertex = heapq.heappop(queue)
        if vertex in settled:
            continue
        settled.add(vertex)
        trace.add("visit", vertex, distance=cost)
        if vertex == goal:
            break
        for neighbor, weight in graph[vertex].items():
            inspected += 1
            trace.add("inspect", vertex, neighbor)
            candidate = _sum(cost, weight)
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = vertex
                heapq.heappush(queue, (candidate, next(counter), neighbor))
                relaxed += 1
                trace.add("relax", vertex, neighbor, candidate)
    path = _path(previous, start, goal) if distances[goal] != math.inf else []
    trace.add("done")
    elapsed = perf_counter_ns() - began
    return Result("Dijkstra", path, distances[goal], elapsed, trace.steps,
                  Metrics(inspected, relaxed, len(settled)), trace.truncated)


def bellman_ford(graph: Graph, start: str, goal: str, *,
                 record_steps: bool = True, max_steps: int = 20_000) -> Result:
    """Scan edges in place for at most V-1 passes, with early stopping.

    O(VE+V) time, O(V+E) auxiliary space (an explicit edge list is stored).
    This application's shared input contract rejects negative weights; this is
    not a general negative-weight/negative-cycle Bellman-Ford API. In-place
    updates can propagate several edges in one pass.
    """
    validate_graph(graph, start, goal)
    began = perf_counter_ns()
    trace = _Trace(record_steps, max_steps)
    distances: dict[str, Number] = {v: math.inf for v in graph}
    distances[start] = 0
    previous: dict[str, str] = {}
    edges = [(v, n, w) for v, neighbors in graph.items() for n, w in neighbors.items()]
    inspected = relaxed = passes = 0
    for iteration in range(1, len(graph)):
        passes += 1
        changed = False
        trace.add("pass", iteration=iteration)
        for vertex, neighbor, weight in edges:
            inspected += 1
            trace.add("inspect", vertex, neighbor, iteration=iteration)
            if distances[vertex] == math.inf:
                continue
            candidate = _sum(distances[vertex], weight)
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = vertex
                changed = True
                relaxed += 1
                trace.add("relax", vertex, neighbor, candidate, iteration)
        if not changed:
            break
    path = _path(previous, start, goal) if distances[goal] != math.inf else []
    trace.add("done")
    elapsed = perf_counter_ns() - began
    return Result("Bellman–Ford", path, distances[goal], elapsed, trace.steps,
                  Metrics(inspected, relaxed, passes=passes), trace.truncated)
