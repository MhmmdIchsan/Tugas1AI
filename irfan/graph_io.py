"""Safe parser for the graph/graf assignment format in the task PDF."""
from __future__ import annotations

import ast
import math
from pathlib import Path

Number = int | float
Graph = dict[str, dict[str, Number]]


def validate_graph(graph: Graph, start: str, goal: str) -> None:
    """Validate file input as well as direct algorithm API calls."""
    if not isinstance(graph, dict) or not graph:
        raise ValueError("Graf harus berupa dictionary yang tidak kosong.")
    if not all(isinstance(v, str) and v and not any(c.isspace() for c in v) for v in graph):
        raise ValueError("Nama verteks harus berupa teks tidak kosong tanpa spasi.")
    if start not in graph or goal not in graph:
        raise ValueError("Verteks awal dan tujuan harus terdaftar dalam graf.")
    for vertex, neighbors in graph.items():
        if not isinstance(neighbors, dict):
            raise ValueError(f"Tetangga {vertex} harus berupa dictionary.")
        for neighbor, weight in neighbors.items():
            if neighbor not in graph:
                raise ValueError(f"Tetangga {neighbor!r} dari {vertex} tidak terdaftar sebagai verteks.")
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise ValueError(f"Bobot {vertex} → {neighbor} harus berupa angka.")
            if weight < 0 or (isinstance(weight, float) and not math.isfinite(weight)):
                raise ValueError(f"Bobot {vertex} → {neighbor} harus finite dan tidak negatif.")


def load_graph(path: str | Path) -> tuple[Graph, str, str]:
    """Read literal data only; reject duplicate keys instead of losing edges.

    Supports UTF-8/BOM, blank lines, comments, and the compact BH example.
    File size is bounded to protect interactive use from accidental huge input.
    """
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        source = stream.read(2_000_001)
    if len(source) > 2_000_000:
        raise ValueError("Berkas terlalu besar; batas input 2 juta karakter.")
    lines = source.splitlines()
    while lines and not lines[-1].split("#", 1)[0].strip():
        lines.pop()
    if not lines:
        raise ValueError("Berkas graf kosong.")
    endpoint_source = lines.pop().split("#", 1)[0].strip()
    try:
        module = ast.parse("\n".join(lines).strip(), mode="exec")
        if (
            len(module.body) != 1
            or not isinstance(module.body[0], ast.Assign)
            or len(module.body[0].targets) != 1
            or not isinstance(module.body[0].targets[0], ast.Name)
            or module.body[0].targets[0].id not in {"graph", "graf"}
            or not isinstance(module.body[0].value, ast.Dict)
        ):
            raise ValueError("Gunakan graph = {...} atau graf = {...}, lalu baris awal tujuan.")
        for node in ast.walk(module.body[0].value):
            if isinstance(node, ast.Dict):
                keys = [ast.literal_eval(key) for key in node.keys]
                if len(set(keys)) != len(keys):
                    raise ValueError("Kunci verteks/tetangga duplikat tidak diperbolehkan.")
        graph = ast.literal_eval(module.body[0].value)
    except (SyntaxError, TypeError, ValueError, MemoryError, RecursionError) as exc:
        raise ValueError(f"Format dictionary graf tidak valid: {exc}") from exc
    endpoints = endpoint_source.split()
    if len(endpoints) == 1 and len(endpoints[0]) == 2:
        if all(isinstance(vertex, str) and len(vertex) == 1 for vertex in graph):
            endpoints = list(endpoints[0])
    if len(endpoints) != 2:
        raise ValueError("Baris terakhir harus memuat dua verteks, misalnya V1 V15.")
    validate_graph(graph, *endpoints)
    return graph, endpoints[0], endpoints[1]
