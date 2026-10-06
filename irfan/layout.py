"""Deterministic spring layout; geometry never supplies algorithm edge weights."""
from __future__ import annotations
import math
from graph_io import Graph


def graph_positions(graph: Graph) -> dict[str, tuple[float, float]]:
    """Return normalized positions. Bound relaxation work for larger graphs."""
    vertices = list(graph)
    count = len(vertices)
    if count == 1:
        return {vertices[0]: (0.5, 0.5)}
    positions = [[math.cos(2 * math.pi * i / count), math.sin(2 * math.pi * i / count)]
                 for i in range(count)]
    index = {v: i for i, v in enumerate(vertices)}
    edges = {tuple(sorted((index[v], index[n])))
             for v in graph for n in graph[v] if v != n}
    ideal = math.sqrt(4 / max(count, 1))
    for iteration in range(160 if count <= 60 else 40):
        forces = [[0.0, 0.0] for _ in vertices]
        for i in range(count):
            for j in range(i):
                dx, dy = positions[i][0] - positions[j][0], positions[i][1] - positions[j][1]
                distance = max(math.hypot(dx, dy), 0.001)
                force = ideal * ideal / distance
                for axis, delta in enumerate((dx, dy)):
                    amount = delta / distance * force
                    forces[i][axis] += amount
                    forces[j][axis] -= amount
        for i, j in edges:
            dx, dy = positions[i][0] - positions[j][0], positions[i][1] - positions[j][1]
            distance = max(math.hypot(dx, dy), 0.001)
            force = distance * distance / ideal
            for axis, delta in enumerate((dx, dy)):
                amount = delta / distance * force
                forces[i][axis] -= amount
                forces[j][axis] += amount
        temperature = 0.16 * (1 - iteration / (160 if count <= 60 else 40))
        for i, force in enumerate(forces):
            size = max(math.hypot(*force), 0.001)
            for axis in (0, 1):
                positions[i][axis] += force[axis] / size * min(size, temperature)
    if not count:
        return {}
    minima = [min(p[a] for p in positions) for a in (0, 1)]
    spans = [max(p[a] for p in positions) - minima[a] for a in (0, 1)]
    return {v: tuple(0.5 if spans[a] < 0.001 else (positions[i][a] - minima[a]) / spans[a]
                     for a in (0, 1)) for i, v in enumerate(vertices)}
