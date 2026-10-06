"""Replay algorithm events without re-running or re-timing the search."""

from __future__ import annotations

import math

from ichsan.algorithms import Result
from ichsan.graph_io import Graph


def number(value: float) -> str:
    return "∞" if math.isinf(value) else f"{value:g}"


class Playback:
    """One cursor into a search trace, with reversible, deterministic state."""

    def __init__(self, graph: Graph, start: str, goal: str, result: Result) -> None:
        self.graph, self.start, self.goal, self.result = graph, start, goal, result
        self.reset()

    def reset(self) -> None:
        self.index = 0
        self.distances = {vertex: math.inf for vertex in self.graph}
        self.distances[self.start] = 0
        self.previous: dict[str, str] = {}
        self.visited: set[str] = set()
        self.current: str | None = None
        self.active_edge: tuple[str, str] | None = None
        self.finished = False
        self.iteration = 0
        self.title = "Siap menjelajahi graf"
        self.detail = f"Jarak {self.start} dimulai dari 0. Simpul lainnya belum terjangkau (∞). Tekan Putar untuk mulai."

    def advance(self) -> bool:
        if self.index >= len(self.result.steps):
            return False
        step = self.result.steps[self.index]
        self.index += 1
        self.active_edge = None
        if step.kind == "pass":
            self.iteration = step.iteration or 0
            self.current = None
            self.title = f"Bellman–Ford · putaran {self.iteration}"
            self.detail = "Periksa sisi yang dapat dicapai. Jarak diperbarui jika ditemukan rute yang lebih pendek."
        elif step.kind == "visit" and step.node is not None:
            self.current = step.node
            self.visited.add(step.node)
            self.title = f"Tetapkan simpul {step.node}"
            self.detail = f"Dijkstra memilih jarak terkecil dari antrean. Jarak ke {step.node} sudah pasti: {number(self.distances[step.node])}."
        elif step.kind in {"inspect", "relax"} and step.node is not None and step.neighbor is not None:
            self.current = step.node
            self.active_edge = (step.node, step.neighbor)
            weight = self.graph[step.node][step.neighbor]
            old = self.distances[step.neighbor]
            if step.kind == "inspect":
                candidate = self.distances[step.node] + weight
                self.title = f"Periksa {step.node} → {step.neighbor}"
                self.detail = (f"Jarak lewat {step.node}: {number(self.distances[step.node])} + {number(weight)} = "
                               f"{number(candidate)}. Jarak {step.neighbor} saat ini: {number(old)}.")
            elif step.distance is not None:
                self.distances[step.neighbor] = step.distance
                self.previous[step.neighbor] = step.node
                self.title = f"Rute lebih pendek ke {step.neighbor}"
                self.detail = f"Jarak {step.neighbor} diperbarui: {number(old)} → {number(step.distance)}, melalui {step.node}."
        elif step.kind == "done":
            self.finished = True
            self.current = None
            self.title = "Jalur terpendek ditemukan" if self.result.path else "Tujuan tidak terjangkau"
            self.detail = (f"{' → '.join(self.result.path)} · total bobot {number(self.result.cost)}."
                           if self.result.path else f"Tidak ada jalur dari {self.start} menuju {self.goal} pada graf ini.")
        return True

    def seek(self, index: int) -> None:
        """Rebuild state from the same recorded trace; runtime stays unchanged."""
        target = max(0, min(int(index), len(self.result.steps)))
        if target < self.index:
            self.reset()
        while self.index < target:
            self.advance()
