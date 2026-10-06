"""Shortest path algorithms and visualisation events."""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import itertools
import math
from time import perf_counter_ns

from ardi.graph_io import Graph


@dataclass(frozen=True)
class Step:
    kind: str  # visit, inspect, relax, pass, done
    node: str | None = None
    neighbor: str | None = None
    distance: float | None = None
    iteration: int | None = None


@dataclass(frozen=True)
class Result:
    name: str
    path: list[str]
    cost: float
    runtime_ns: int
    steps: list[Step]


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


def dijkstra(graph: Graph, start: str, goal: str) -> Result:
    """Find one minimum-cost path using a binary-heap priority queue."""
    began = perf_counter_ns()
    steps: list[Step] = []
    distances = {vertex: math.inf for vertex in graph}
    distances[start] = 0
    previous: dict[str, str] = {}
    settled: set[str] = set()
    counter = itertools.count()
    queue = [(0, next(counter), start)]

    while queue:
        cost, _, vertex = heapq.heappop(queue)
        if vertex in settled:
            continue
        settled.add(vertex)
        steps.append(Step("visit", vertex, distance=cost))
        if vertex == goal:
            break
        for neighbor, weight in graph[vertex].items():
            steps.append(Step("inspect", vertex, neighbor))
            candidate = cost + weight
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = vertex
                heapq.heappush(queue, (candidate, next(counter), neighbor))
                steps.append(Step("relax", vertex, neighbor, candidate))

    path = _path(previous, start, goal) if math.isfinite(distances[goal]) else []
    steps.append(Step("done"))
    return Result("Dijkstra", path, distances[goal], perf_counter_ns() - began, steps)


def bellman_ford(graph: Graph, start: str, goal: str) -> Result:
    """Relax every directed edge until distances stop changing."""
    began = perf_counter_ns()
    steps: list[Step] = []
    distances = {vertex: math.inf for vertex in graph}
    distances[start] = 0
    previous: dict[str, str] = {}
    edges = [(vertex, neighbor, weight)
             for vertex, neighbors in graph.items()
             for neighbor, weight in neighbors.items()]

    for iteration in range(1, len(graph)):
        changed = False
        steps.append(Step("pass", iteration=iteration))
        for vertex, neighbor, weight in edges:
            if math.isinf(distances[vertex]):
                continue
            steps.append(Step("inspect", vertex, neighbor, iteration=iteration))
            candidate = distances[vertex] + weight
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = vertex
                changed = True
                steps.append(Step("relax", vertex, neighbor, candidate, iteration))
        if not changed:
            break

    path = _path(previous, start, goal) if math.isfinite(distances[goal]) else []
    steps.append(Step("done"))
    return Result("Bellman–Ford", path, distances[goal], perf_counter_ns() - began, steps)
