"""Interactive, dependency-free Tk canvas for shortest-path demonstrations.

Positions live in graph coordinates; panning and zooming only change the view.
Algorithm events repaint existing items instead of rebuilding the drawing.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import time
import tkinter as tk
from typing import Callable

from ichsan.graph_io import Graph


BACKGROUND = "#fcfefe"
INK = "#172b3a"
MUTED = "#71828e"
TEAL = "#087f8c"
EDGE = "#c5d4db"
AMBER = "#ca821d"
GREEN = "#218665"
CORAL = "#cf6670"

Point = tuple[float, float]


def _number(value: float) -> str:
    return "∞" if math.isinf(value) else f"{value:g}"


def graph_positions(graph: Graph, start: str) -> dict[str, Point]:
    """BFS layers with deterministic barycenter sweeps to reduce crossings.

    Direction is ignored for placement only. Disconnected components occupy
    successive groups of columns and never share a node position.
    """
    if not graph:
        return {}
    order = {vertex: index for index, vertex in enumerate(graph)}
    adjacency = {vertex: set(neighbors) - {vertex} for vertex, neighbors in graph.items()}
    for vertex, neighbors in graph.items():
        for neighbor in neighbors:
            if neighbor != vertex:
                adjacency[neighbor].add(vertex)
    seen: set[str] = set()
    columns: list[list[str]] = []
    for root in [start, *(vertex for vertex in graph if vertex != start)]:
        if root in seen or root not in graph:
            continue
        queue = deque([(root, 0)])
        seen.add(root)
        levels: list[list[str]] = []
        while queue:
            vertex, depth = queue.popleft()
            if depth == len(levels):
                levels.append([])
            levels[depth].append(vertex)
            for neighbor in sorted(adjacency[vertex], key=order.__getitem__):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append((neighbor, depth + 1))

        # Stable sweeps take both upstream and downstream neighbors into account.
        for _ in range(4):
            for indices in (range(1, len(levels)), range(len(levels) - 2, -1, -1)):
                for index in indices:
                    ranks = {
                        vertex: (row + 0.5) / len(level)
                        for level in levels for row, vertex in enumerate(level)
                    }
                    levels[index].sort(key=lambda vertex: (
                        sum(ranks[n] for n in adjacency[vertex]) / max(1, len(adjacency[vertex])),
                        order[vertex],
                    ))
        if columns:
            columns.append([])
        columns.extend(levels)

    max_rows = max(map(len, columns))
    positions: dict[str, Point] = {}
    for column, vertices in enumerate(columns):
        for row, vertex in enumerate(vertices):
            # Center short columns; stagger crowded layers so same-layer edges
            # can pass intermediate nodes without obscuring their labels.
            y = (row - (len(vertices) - 1) / 2) * 138
            if len(vertices) >= 3:
                y *= max_rows / len(vertices)
            stagger = 18 if len(vertices) >= 3 and row % 2 else 0
            positions[vertex] = (column * 170 + stagger, y)
    return positions


def _distance_to_segment(point: Point, first: Point, second: Point) -> float:
    dx, dy = second[0] - first[0], second[1] - first[1]
    denominator = dx * dx + dy * dy
    if denominator == 0:
        return math.hypot(point[0] - first[0], point[1] - first[1])
    t = max(0, min(1, ((point[0] - first[0]) * dx + (point[1] - first[1]) * dy) / denominator))
    return math.hypot(point[0] - first[0] - t * dx, point[1] - first[1] - t * dy)


@dataclass
class _EdgeItems:
    source: str
    target: str
    reciprocal: bool
    opposite: bool
    line: int
    badge: int
    label: int
    text: str


class GraphCanvas(tk.Canvas):
    """Pan, zoom, drag, and animate a graph using persistent Canvas items.

    ``on_hover`` receives a vertex name or None. ``set_state`` accepts a final
    path only when it should be highlighted; pass [] during normal playback.
    Call ``dispose`` before destroying a parent that owns pending callbacks.
    """

    def __init__(self, parent: tk.Widget, on_hover: Callable[[str | None], None] | None = None,
                 **kwargs) -> None:
        kwargs.setdefault("bg", BACKGROUND)
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("height", 450)
        kwargs.setdefault("cursor", "hand2")
        super().__init__(parent, **kwargs)
        self.on_hover = on_hover
        self.graph: Graph = {}
        self.start = ""
        self.goal = ""
        self.positions: dict[str, Point] = {}
        self._default_positions: dict[str, Point] = {}
        self.distances: dict[str, float] = {}
        self.visited: set[str] = set()
        self.current: str | None = None
        self.active_edge: tuple[str, str] | None = None
        self.path: list[str] = []
        self._nodes: dict[str, dict[str, int]] = {}
        self._edges: list[_EdgeItems] = []
        self._scale = 1.0
        self._offset: Point = (0, 0)
        self._interacted = False
        self._hover: str | None = None
        self._drag_node: str | None = None
        self._drag_origin: Point | None = None
        self._drag_position: Point | None = None
        self._transition_id: str | None = None
        self._resize_id: str | None = None
        self._disposed = False
        self._empty = self.create_text(0, 0, text="Pilih contoh graf untuk mulai menjelajah",
                                       fill=MUTED, font=("Segoe UI", 11), tags="empty")
        self.bind("<Configure>", self._on_resize)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", lambda _event: self._set_hover(None))
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Button-4>", lambda event: self._zoom_at(1.12, event.x, event.y))
        self.bind("<Button-5>", lambda event: self._zoom_at(1 / 1.12, event.x, event.y))
        self.bind("<Double-Button-1>", lambda _event: self.reset_view())
        self.bind("<Destroy>", self._on_destroy, add=True)

    def set_graph(self, graph: Graph, start: str, goal: str) -> None:
        """Load a graph and restore automatic fitting and the initial distances."""
        self._cancel_transition()
        self._set_hover(None)
        self.graph, self.start, self.goal = graph, start, goal
        self.positions = graph_positions(graph, start)
        self._default_positions = self.positions.copy()
        self._interacted = False
        self._drag_origin = self._drag_node = self._drag_position = None
        self.delete("graph")
        self._nodes.clear()
        self._edges.clear()
        self.itemconfigure(self._empty, state="hidden" if graph else "normal")
        drawn: set[tuple[str, str]] = set()
        for source, neighbors in graph.items():
            for target, weight in neighbors.items():
                reciprocal = source != target and graph[target].get(source) == weight
                key = tuple(sorted((source, target))) if reciprocal else (source, target)
                if key in drawn:
                    continue
                drawn.add(key)
                opposite = source != target and source in graph[target] and not reciprocal
                line = self.create_line(0, 0, 1, 1, fill=EDGE, width=1.6,
                                        arrow=tk.NONE if reciprocal else tk.LAST,
                                        arrowshape=(9, 10, 4), smooth=True, splinesteps=24,
                                        capstyle=tk.ROUND, joinstyle=tk.ROUND,
                                        tags=("graph", "edge"))
                badge = self.create_rectangle(0, 0, 1, 1, fill=BACKGROUND, outline="",
                                              tags=("graph", "edge-label"))
                label = self.create_text(0, 0, text=_number(weight), fill=MUTED,
                                         font=("Segoe UI", 9), tags=("graph", "edge-label"))
                self._edges.append(_EdgeItems(source, target, reciprocal, opposite,
                                              line, badge, label, _number(weight)))
        for vertex in graph:
            tags = ("graph", "node")
            role = "AWAL · TUJUAN" if start == goal == vertex else (
                "AWAL" if vertex == start else "TUJUAN" if vertex == goal else "")
            self._nodes[vertex] = {
                "halo": self.create_oval(0, 0, 1, 1, fill=BACKGROUND, outline="", tags=tags),
                "shadow": self.create_oval(0, 0, 1, 1, fill="#e7eef0", outline="", tags=tags),
                "body": self.create_oval(0, 0, 1, 1, fill="#ffffff", outline=EDGE, width=1.6, tags=tags),
                "name": self.create_text(0, 0, text=vertex, fill=INK,
                                          font=("Segoe UI", 10, "bold"), tags=tags),
                "distance": self.create_text(0, 0, text="∞", fill=MUTED,
                                              font=("Segoe UI", 9), tags=tags),
                "role": self.create_text(0, 0, text=role, fill=GREEN if vertex == start else CORAL,
                                          font=("Segoe UI", 8, "bold"), tags=tags),
            }
        self.tag_lower("edge")
        self.tag_lower("grid")
        self.tag_raise("node")
        self._fit()
        self.set_state({v: 0 if v == start else math.inf for v in graph}, set(), None, None, [], False)

    def set_state(self, distances: dict[str, float], visited: set[str], current: str | None,
                  active_edge: tuple[str, str] | None, path: list[str], animate: bool = True) -> None:
        """Apply an animation snapshot, independently of node layout and view."""
        if self._disposed:
            return
        self.distances = dict(distances)
        self.visited = set(visited)
        self.current, self.active_edge, self.path = current, active_edge, list(path)
        for vertex, items in self._nodes.items():
            self.itemconfigure(items["distance"], text=_number(self.distances.get(vertex, math.inf)))
        self._paint(animate)

    def reset_view(self) -> None:
        """Restore the deterministic layout and fit the whole graph."""
        self.positions = self._default_positions.copy()
        self._interacted = False
        self._fit()

    def zoom_in(self) -> None:
        self._zoom_at(1.18, self.winfo_width() / 2, self.winfo_height() / 2)

    def zoom_out(self) -> None:
        self._zoom_at(1 / 1.18, self.winfo_width() / 2, self.winfo_height() / 2)

    def dispose(self) -> None:
        self._disposed = True
        self._cancel_transition()
        if self._resize_id is not None:
            self.after_cancel(self._resize_id)
            self._resize_id = None

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            self.dispose()

    def _screen(self, position: Point) -> Point:
        return (position[0] * self._scale + self._offset[0],
                position[1] * self._scale + self._offset[1])

    def _radius(self) -> float:
        return max(17, min(43, 28 * self._scale))

    def _on_resize(self, _event) -> None:
        if self._resize_id is not None:
            self.after_cancel(self._resize_id)
        self._resize_id = self.after(24, self._resize)

    def _resize(self) -> None:
        self._resize_id = None
        if self._disposed:
            return
        width, height = self.winfo_width(), self.winfo_height()
        self.coords(self._empty, width / 2, height / 2)
        self.delete("grid")
        for x in range(22, width, 28):
            for y in range(22, height, 28):
                self.create_oval(x, y, x + 1, y + 1, fill="#e6edef", outline="", tags="grid")
        self.tag_lower("grid")
        if not self._interacted:
            self._fit()
        else:
            self._layout_items()

    def _fit(self) -> None:
        if not self.positions:
            return
        width, height = max(100, self.winfo_width()), max(100, self.winfo_height())
        xs, ys = zip(*self.positions.values())
        graph_width, graph_height = max(xs) - min(xs), max(ys) - min(ys)
        self._scale = min(1.18, max(0.20, min((width - 132) / max(1, graph_width),
                                             (height - 150) / max(1, graph_height))))
        self._offset = (width / 2 - (min(xs) + max(xs)) / 2 * self._scale,
                        height / 2 - (min(ys) + max(ys)) / 2 * self._scale + 5)
        self._layout_items()

    def _zoom_at(self, factor: float, x: float, y: float) -> str:
        if not self.graph:
            return "break"
        previous = self._scale
        self._scale = max(0.18, min(2.5, previous * factor))
        factor = self._scale / previous
        self._offset = (x - (x - self._offset[0]) * factor,
                        y - (y - self._offset[1]) * factor)
        self._interacted = True
        self._layout_items()
        return "break"

    def _wheel(self, event) -> str:
        return self._zoom_at(1.12 if event.delta > 0 else 1 / 1.12, event.x, event.y)

    def _node_at(self, x: float, y: float) -> str | None:
        radius = self._radius() + 4
        for vertex, position in reversed(list(self.positions.items())):
            px, py = self._screen(position)
            if math.hypot(x - px, y - py) <= radius:
                return vertex
        return None

    def _press(self, event) -> None:
        self.focus_set()
        self._drag_node = self._node_at(event.x, event.y)
        self._drag_origin = (event.x, event.y)
        self._drag_position = (self.positions[self._drag_node]
                               if self._drag_node else self._offset)
        self.configure(cursor="fleur")

    def _drag(self, event) -> None:
        if self._drag_origin is None or self._drag_position is None:
            return
        dx, dy = event.x - self._drag_origin[0], event.y - self._drag_origin[1]
        if abs(dx) + abs(dy) < 2:
            return
        self._interacted = True
        if self._drag_node:
            self.positions[self._drag_node] = (self._drag_position[0] + dx / self._scale,
                                               self._drag_position[1] + dy / self._scale)
        else:
            self._offset = (self._drag_position[0] + dx, self._drag_position[1] + dy)
        self._layout_items()

    def _release(self, event) -> None:
        self._drag_node = None
        self._drag_origin = self._drag_position = None
        self._motion(event)

    def _motion(self, event) -> None:
        vertex = self._node_at(event.x, event.y)
        self.configure(cursor="hand2" if vertex else "arrow")
        self._set_hover(vertex)

    def _set_hover(self, vertex: str | None) -> None:
        if vertex == self._hover:
            return
        self._hover = vertex
        self._paint(False)
        if self.on_hover:
            self.on_hover(vertex)

    def _route(self, edge: _EdgeItems, positions: dict[str, Point], radius: float) -> list[Point]:
        first, second = positions[edge.source], positions[edge.target]
        if edge.source == edge.target:
            x, y = first
            return [(x - radius * .6, y - radius * .8), (x - radius * 1.7, y - radius * 2.1),
                    (x + radius * 1.7, y - radius * 2.1), (x + radius * .6, y - radius * .8)]
        dx, dy = second[0] - first[0], second[1] - first[1]
        length = max(.001, math.hypot(dx, dy))
        ux, uy, nx, ny = dx / length, dy / length, -dy / length, dx / length
        others = [point for vertex, point in positions.items() if vertex not in {edge.source, edge.target}]
        offset = 23 if edge.opposite else 0
        if not edge.opposite and any(_distance_to_segment(point, first, second) < radius + 12 for point in others):
            # Curve long edges around intervening vertices, choosing the side
            # with most clearance; the endpoints remain attached to the circles.
            candidates = (-48, 48, -80, 80, -115, 115)
            scores: list[tuple[float, float]] = []
            for candidate in candidates:
                bend = ((first[0] + second[0]) / 2 + nx * candidate,
                        (first[1] + second[1]) / 2 + ny * candidate)
                clearance = min((_distance_to_segment(point, a, b)
                                 for point in others for a, b in ((first, bend), (bend, second))), default=1000)
                scores.append((min(clearance, radius + 24) - abs(candidate) * .025, candidate))
            offset = max(scores, key=lambda item: item[0])[1]
        if offset:
            bends = [(first[0] + dx * t + nx * offset, first[1] + dy * t + ny * offset)
                     for t in (.3, .7)]
            def clip(center: Point, toward: Point) -> Point:
                distance = max(.001, math.hypot(toward[0] - center[0], toward[1] - center[1]))
                return (center[0] + (toward[0] - center[0]) * (radius + 2) / distance,
                        center[1] + (toward[1] - center[1]) * (radius + 2) / distance)
            return [clip(first, bends[0]), *bends, clip(second, bends[-1])]
        return [(first[0] + ux * (radius + 2), first[1] + uy * (radius + 2)),
                (second[0] - ux * (radius + 2), second[1] - uy * (radius + 2))]

    @staticmethod
    def _label_position(route: list[Point], positions: dict[str, Point], used: list[tuple[float, float, float]],
                        label_width: float, radius: float) -> Point:
        first, second = (route[1], route[2]) if len(route) > 2 else (route[0], route[-1])
        dx, dy = second[0] - first[0], second[1] - first[1]
        length = max(.001, math.hypot(dx, dy))
        nx, ny = -dy / length, dx / length
        best: tuple[float, Point] | None = None
        for fraction in (.5, .38, .62, .26, .74):
            for offset in (0, 14, -14, 26, -26):
                x, y = first[0] + dx * fraction + nx * offset, first[1] + dy * fraction + ny * offset
                node_clearance = min((math.hypot(x - px, y - py) - radius - label_width / 3
                                      for px, py in positions.values()), default=1000)
                overlap = sum(abs(x - px) < (label_width + width) / 2 + 3 and abs(y - py) < 21
                              for px, py, width in used)
                score = min(node_clearance, 20) - overlap * 100 - abs(fraction - .5) * 5 - abs(offset) * .06
                if best is None or score > best[0]:
                    best = score, (x, y)
        assert best is not None
        used.append((*best[1], label_width))
        return best[1]

    def _layout_items(self) -> None:
        if not self.graph or self._disposed:
            return
        positions = {vertex: self._screen(point) for vertex, point in self.positions.items()}
        radius = self._radius()
        font_size = max(8, min(12, round(10 * self._scale)))
        small_size = max(8, min(11, font_size - 1))
        used: list[tuple[float, float, float]] = []
        for edge in self._edges:
            route = self._route(edge, positions, radius)
            self.coords(edge.line, *(coordinate for point in route for coordinate in point))
            self.itemconfigure(edge.label, font=("Segoe UI", small_size))
            label_width = max(22, len(edge.text) * small_size * .7 + 11)
            if edge.source == edge.target:
                x, y = positions[edge.source]
                lx, ly = x + radius * 1.6, y - radius * 1.6
            else:
                lx, ly = self._label_position(route, positions, used, label_width, radius)
            self.coords(edge.badge, lx - label_width / 2, ly - 10, lx + label_width / 2, ly + 10)
            self.coords(edge.label, lx, ly)
        for vertex, items in self._nodes.items():
            x, y = positions[vertex]
            halo = radius + 7
            self.coords(items["halo"], x - halo, y - halo, x + halo, y + halo)
            self.coords(items["shadow"], x - radius, y - radius + 3, x + radius, y + radius + 3)
            self.coords(items["body"], x - radius, y - radius, x + radius, y + radius)
            self.coords(items["name"], x, y - 7)
            self.coords(items["distance"], x, y + 10)
            self.coords(items["role"], x, y - radius - 16)
            self.itemconfigure(items["name"], font=("Segoe UI", font_size, "bold"))
            self.itemconfigure(items["distance"], font=("Segoe UI", small_size))
        self.tag_raise("edge-label")
        self.tag_raise("node")

    def _paint(self, animate: bool) -> None:
        if self._disposed:
            return
        self._cancel_transition()
        targets: dict[tuple[int, str], str | float] = {}
        route_edges = set(zip(self.path, self.path[1:]))
        route_nodes = set(self.path)
        for edge in self._edges:
            pair, reverse = (edge.source, edge.target), (edge.target, edge.source)
            highlighted = pair in route_edges or (edge.reciprocal and reverse in route_edges)
            active = self.active_edge == pair or (edge.reciprocal and self.active_edge == reverse)
            hover = self._hover in pair
            color = TEAL if highlighted else AMBER if active else "#91aeb9" if hover else EDGE
            targets[edge.line, "fill"] = color
            targets[edge.line, "width"] = 3.8 if highlighted else 3 if active else 1.8 if hover else 1.5
            targets[edge.label, "fill"] = TEAL if highlighted else AMBER if active else MUTED
            targets[edge.badge, "fill"] = "#e4f4f3" if highlighted else "#fff3df" if active else BACKGROUND
        for vertex, items in self._nodes.items():
            fill, outline = "#ffffff", "#bdcdd5"
            if vertex in self.visited:
                fill, outline = "#edf7f7", "#70aeb2"
            if vertex in route_nodes:
                fill, outline = "#e0f3f0", TEAL
            if vertex == self.start:
                fill, outline = "#e5f4ed", GREEN
            if vertex == self.goal:
                fill, outline = "#fcecef", CORAL
            if vertex == self.current:
                fill, outline = "#fff1d8", AMBER
            targets[items["body"], "fill"] = fill
            targets[items["body"], "outline"] = outline
            targets[items["body"], "width"] = 2.5 if vertex == self.current or vertex in route_nodes else 1.8
            targets[items["halo"], "fill"] = ("#fbe9cb" if vertex == self.current else
                                                "#dcefed" if vertex == self._hover else BACKGROUND)
            targets[items["distance"], "fill"] = AMBER if vertex == self.current else TEAL if vertex in route_nodes else MUTED
        if not animate:
            for (item, option), value in targets.items():
                self.itemconfigure(item, **{option: value})
            return
        origins = {(item, option): self.itemcget(item, option) for item, option in targets}
        started = time.perf_counter()

        def tick() -> None:
            self._transition_id = None
            if self._disposed:
                return
            fraction = min(1.0, (time.perf_counter() - started) / .13)
            eased = 1 - (1 - fraction) ** 3
            for key, value in targets.items():
                item, option = key
                origin = origins[key]
                if isinstance(value, str):
                    a = tuple(int(origin[index:index + 2], 16) for index in (1, 3, 5))
                    b = tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))
                    interpolated = "#" + "".join(f"{round(x + (y - x) * eased):02x}" for x, y in zip(a, b))
                else:
                    interpolated = float(origin) + (value - float(origin)) * eased
                self.itemconfigure(item, **{option: interpolated})
            if fraction < 1:
                self._transition_id = self.after(16, tick)
        tick()

    def _cancel_transition(self) -> None:
        if self._transition_id is not None:
            self.after_cancel(self._transition_id)
            self._transition_id = None
