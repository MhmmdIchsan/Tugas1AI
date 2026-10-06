"""Read and validate the graph format used in Tugas 1."""

from __future__ import annotations

import ast
import math
from pathlib import Path


Graph = dict[str, dict[str, float]]


def load_graph(path: str | Path) -> tuple[Graph, str, str]:
    """Return (adjacency map, start, goal) from a graf.txt file.

    The file contains a Python dictionary assignment followed by the endpoints.
    Only literal data is evaluated; arbitrary Python code is never executed.
    """
    source = Path(path).read_text(encoding="utf-8-sig")
    closing = source.rfind("}")
    if closing < 0:
        raise ValueError("Graf harus berupa dictionary yang diakhiri '}'.")

    graph_source = source[: closing + 1].strip()
    endpoint_source = source[closing + 1 :].strip()
    try:
        module = ast.parse(graph_source, mode="exec")
        if (
            len(module.body) != 1
            or not isinstance(module.body[0], ast.Assign)
            or len(module.body[0].targets) != 1
            or not isinstance(module.body[0].targets[0], ast.Name)
            or module.body[0].targets[0].id not in {"graph", "graf"}
        ):
            raise ValueError("Gunakan format graph = {...} atau graf = {...}.")
        raw_graph = ast.literal_eval(module.body[0].value)
    except (SyntaxError, TypeError, ValueError, MemoryError, RecursionError) as exc:
        raise ValueError(f"Format dictionary graf tidak valid: {exc}") from exc

    if not isinstance(raw_graph, dict) or not raw_graph:
        raise ValueError("Graf harus berupa dictionary yang tidak kosong.")
    if not all(isinstance(vertex, str) and vertex.strip() for vertex in raw_graph):
        raise ValueError("Setiap nama verteks harus berupa teks yang tidak kosong.")

    graph: Graph = {}
    for vertex, neighbors in raw_graph.items():
        if not isinstance(neighbors, dict):
            raise ValueError(f"Tetangga {vertex} harus berupa dictionary.")
        graph[vertex] = {}
        for neighbor, weight in neighbors.items():
            if neighbor not in raw_graph:
                raise ValueError(f"Tetangga {neighbor!r} dari {vertex} tidak terdaftar sebagai verteks.")
            if not isinstance(weight, (int, float)) or isinstance(weight, bool):
                raise ValueError(f"Bobot {vertex} → {neighbor} harus berupa angka.")
            if not math.isfinite(weight) or weight < 0:
                raise ValueError(f"Bobot {vertex} → {neighbor} harus finite dan tidak negatif.")
            graph[vertex][neighbor] = weight

    endpoints = endpoint_source.split()
    if len(endpoints) == 1 and len(endpoints[0]) == 2:
        # Example c in the assignment writes BH instead of B H.
        if all(len(vertex) == 1 for vertex in graph):
            endpoints = list(endpoints[0])
    if len(endpoints) != 2 or any(vertex not in graph for vertex in endpoints):
        raise ValueError("Baris terakhir harus memuat dua verteks yang ada, misalnya V1 V15.")
    return graph, endpoints[0], endpoints[1]
