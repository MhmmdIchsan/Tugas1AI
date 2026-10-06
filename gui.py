"""Tkinter interface for comparing and animating shortest path searches."""

from __future__ import annotations

from collections import deque
import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from algorithms import Result, Step, bellman_ford, dijkstra
from graph_io import Graph, load_graph


BG = "#f3f6fb"
INK = "#17243a"
MUTED = "#617188"
EDGE = "#aebbd0"
BLUE = "#2875d0"
GREEN = "#17845b"
ORANGE = "#e48a24"
RED = "#c94b52"


def format_number(value: float) -> str:
    """Format a result cost for display."""
    return "Tidak ada jalur" if math.isinf(value) else f"{value:g}"


def distance_text(value: float) -> str:
    """Format a tentative distance shown inside a vertex."""
    return "∞" if math.isinf(value) else f"{value:g}"


def layered_positions(graph: Graph, start: str, width: int, height: int) -> dict[str, tuple[float, float]]:
    """Place vertices in deterministic BFS columns, including disconnected parts.

    Edge direction is ignored only for layout. The drawing still uses the actual
    directed edges. Sorting by parent positions reduces crossings within a layer.
    """
    if not graph:
        return {}
    order = {vertex: index for index, vertex in enumerate(graph)}
    adjacency = {vertex: set(neighbors) for vertex, neighbors in graph.items()}
    for vertex, neighbors in graph.items():
        for neighbor in neighbors:
            adjacency[neighbor].add(vertex)

    columns: list[list[str]] = []
    seen: set[str] = set()
    roots = [start] + [vertex for vertex in graph if vertex != start]
    for root in roots:
        if root in seen or root not in graph:
            continue
        queue = deque([(root, 0)])
        seen.add(root)
        levels: list[list[str]] = []
        while queue:
            vertex, depth = queue.popleft()
            if len(levels) == depth:
                levels.append([])
            levels[depth].append(vertex)
            for neighbor in sorted(adjacency[vertex], key=order.__getitem__):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append((neighbor, depth + 1))

        for depth in range(1, len(levels)):
            previous = {vertex: index for index, vertex in enumerate(levels[depth - 1])}
            levels[depth].sort(key=lambda vertex: (
                sum(previous[neighbor] for neighbor in adjacency[vertex] if neighbor in previous)
                / max(1, sum(neighbor in previous for neighbor in adjacency[vertex])),
                order[vertex],
            ))
        if columns:
            columns.append([])  # Space between disconnected components.
        columns.extend(levels)

    x_margin, y_margin = 48, 43
    x_span = max(0, width - 2 * x_margin)
    y_span = max(0, height - 2 * y_margin)
    positions: dict[str, tuple[float, float]] = {}
    for column_index, vertices in enumerate(columns):
        if not vertices:
            continue
        x = width / 2 if len(columns) == 1 else x_margin + x_span * column_index / (len(columns) - 1)
        for row_index, vertex in enumerate(vertices):
            y = height / 2 if len(vertices) == 1 else y_margin + y_span * row_index / (len(vertices) - 1)
            # A slight stagger keeps long intra-column edges from passing
            # straight through vertices between their endpoints.
            stagger = 0
            if len(vertices) >= 3 and row_index % 2:
                stagger = 34 if column_index < (len(columns) - 1) / 2 else -34
            positions[vertex] = (x + stagger, y)
    return positions


def _segment_near_point(
    first: tuple[float, float], second: tuple[float], point: tuple[float, float], clearance: float,
) -> bool:
    """Whether a line segment runs close enough to obscure a vertex."""
    x1, y1 = first
    x2, y2 = second
    px, py = point
    length_squared = (x2 - x1) ** 2 + (y2 - y1) ** 2
    if length_squared == 0:
        return math.hypot(px - x1, py - y1) < clearance
    fraction = max(0.0, min(1.0, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / length_squared))
    return math.hypot(px - (x1 + fraction * (x2 - x1)),
                      py - (y1 + fraction * (y2 - y1))) < clearance


def _edge_route(
    first: tuple[float, float], second: tuple[float],
    other_vertices: list[tuple[float, float]], width: int, height: int,
) -> list[tuple[float, float]]:
    """Detour around any vertex that lies on a long straight edge."""
    if not any(_segment_near_point(first, second, point, 30) for point in other_vertices):
        return [first, second]
    x1, y1 = first
    x2, y2 = second
    length = math.hypot(x2 - x1, y2 - y1)
    nx, ny = -(y2 - y1) / length, (x2 - x1) / length
    for offset in (-45, 45, -65, 65):
        bends = [(x1 + (x2 - x1) * fraction + nx * offset,
                  y1 + (y2 - y1) * fraction + ny * offset)
                 for fraction in (0.25, 0.75)]
        route = [first, *bends, second]
        if any(not (28 < x < width - 28 and 28 < y < height - 28) for x, y in bends):
            continue
        if any(_segment_near_point(a, b, point, 29)
               for a, b in zip(route, route[1:]) for point in other_vertices):
            continue
        return route
    return [first, second]


class ShortestPathApp(tk.Tk):
    def __init__(self, default_file: Path) -> None:
        super().__init__()
        self.title("Tugas 1 — Perbandingan Jalur Terpendek")
        self.geometry("1160x740")
        self.minsize(880, 600)
        self.configure(bg=BG)

        self.graph: Graph = {}
        self.start = ""
        self.goal = ""
        self.results: dict[str, Result] = {}
        self.events: list[Step] = []
        self.step_index = 0
        self.distances: dict[str, float] = {}
        self.visited: set[str] = set()
        self.current: str | None = None
        self.active_edge: tuple[str, str] | None = None
        self.finished = False
        self.playing = False
        self.timer: str | None = None
        self.file_path = tk.StringVar(value="Belum ada file")
        self.algorithm = tk.StringVar(value="Dijkstra")
        self.speed = tk.IntVar(value=260)
        self.progress = tk.StringVar(value="Langkah 0 / 0")
        self.step_title = tk.StringVar(value="Belum ada graf")
        self.step_detail = tk.StringVar(value="Buka file graf untuk memulai.")
        self.endpoint_text = tk.StringVar(value="Awal —  Tujuan —")
        self.card_values: dict[str, dict[str, tk.StringVar]] = {}

        self._make_widgets()
        self.after(100, lambda: self.open_file(default_file) if default_file.exists() else None)

    def _make_widgets(self) -> None:
        heading = tk.Frame(self, bg=BG, padx=20, pady=13)
        heading.pack(fill="x")
        tk.Label(heading, text="Pencarian Jalur Terpendek", bg=BG, fg=INK,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(heading, text="Bandingkan Dijkstra dan Bellman–Ford, lalu amati prosesnya.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")

        controls = tk.Frame(self, bg=BG, padx=20)
        controls.pack(fill="x", pady=(0, 9))
        ttk.Button(controls, text="Buka graf.txt", command=self.choose_file).pack(side="left")
        tk.Label(controls, textvariable=self.file_path, bg=BG, fg=MUTED,
                 font=("Segoe UI", 9), anchor="w").pack(side="left", padx=12, fill="x", expand=True)
        ttk.Button(controls, text="Hitung ulang", command=self.calculate).pack(side="right")

        footer = tk.Frame(self, bg=BG, padx=20, pady=7)
        footer.pack(fill="x", side="bottom")
        for label, color in (("● awal", GREEN), ("● tujuan", RED),
                             ("● sedang diproses", ORANGE), ("● jalur terpendek", BLUE)):
            tk.Label(footer, text=label, fg=color, bg=BG,
                     font=("Segoe UI", 9)).pack(side="left", padx=(0, 15))

        body = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=6, borderwidth=0)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        graph_panel = tk.Frame(body, bg="white", highlightbackground="#d9e1ec", highlightthickness=1)
        side_panel = tk.Frame(body, bg="white", highlightbackground="#d9e1ec", highlightthickness=1)
        body.add(graph_panel, minsize=510, stretch="always")
        body.add(side_panel, minsize=310, stretch="never")

        tk.Label(graph_panel, text="Visualisasi graf", bg="white", fg=INK,
                 font=("Segoe UI", 13, "bold"), padx=16, pady=10).pack(anchor="w")
        self.canvas = tk.Canvas(graph_panel, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        self.canvas.bind("<Configure>", lambda _event: self.draw_graph())

        side_canvas = tk.Canvas(side_panel, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(side_panel, orient="vertical", command=side_canvas.yview)
        side_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        side_canvas.pack(side="left", fill="both", expand=True)
        side_inner = tk.Frame(side_canvas, bg="white", padx=12, pady=7)
        side_window = side_canvas.create_window((0, 0), window=side_inner, anchor="nw")
        side_inner.bind("<Configure>", lambda _event: side_canvas.configure(scrollregion=side_canvas.bbox("all")))
        side_canvas.bind("<Configure>", lambda event: side_canvas.itemconfigure(side_window, width=event.width))
        side_canvas.bind("<MouseWheel>", lambda event: side_canvas.yview_scroll(-int(event.delta / 120), "units"))

        tk.Label(side_inner, text="Hasil perbandingan", bg="white", fg=INK,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(side_inner, textvariable=self.endpoint_text, bg="white", fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(1, 5))
        for name in ("Dijkstra", "Bellman–Ford"):
            self._make_result_card(side_inner, name)
        tk.Label(side_inner, text="Waktu dapat berubah; animasi tidak ikut diukur.",
                 bg="white", fg=MUTED, justify="left", wraplength=270,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 8))

        tk.Label(side_inner, text="Animasi algoritma", bg="white", fg=INK,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        selector = ttk.Combobox(side_inner, state="readonly", textvariable=self.algorithm,
                                values=("Dijkstra", "Bellman–Ford"))
        selector.pack(fill="x", pady=(4, 6))
        selector.bind("<<ComboboxSelected>>", lambda _event: self.reset_animation())
        buttons = tk.Frame(side_inner, bg="white")
        buttons.pack(fill="x")
        self.play_button = ttk.Button(buttons, text="Putar", command=self.toggle_play)
        self.play_button.pack(side="left")
        ttk.Button(buttons, text="Satu langkah", command=self.next_step).pack(side="left", padx=6)
        ttk.Button(buttons, text="Ulangi", command=self.reset_animation).pack(side="left")
        step_panel = tk.Frame(side_inner, bg="#eef4fc", padx=10, pady=9)
        step_panel.pack(fill="x", pady=(8, 5))
        tk.Label(step_panel, textvariable=self.step_title, bg="#eef4fc", fg=INK,
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        tk.Label(step_panel, textvariable=self.step_detail, bg="#eef4fc", fg=MUTED,
                 justify="left", anchor="w", wraplength=255,
                 font=("Segoe UI", 9)).pack(fill="x", pady=(3, 0))
        tk.Label(side_inner, textvariable=self.progress, bg="white", fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 1))
        tk.Label(side_inner, text="Jeda per langkah (ms)", bg="white", fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w")
        ttk.Scale(side_inner, from_=60, to=900, variable=self.speed).pack(fill="x", pady=(0, 6))

    def _make_result_card(self, parent: tk.Widget, name: str) -> None:
        card = tk.Frame(parent, bg="#f8faff", highlightbackground="#dbe5f2",
                        highlightthickness=1, padx=9, pady=5)
        card.pack(fill="x", pady=(0, 5))
        values = {key: tk.StringVar(value="—") for key in ("path", "cost", "metrics")}
        self.card_values[name] = values
        title = tk.Frame(card, bg="#f8faff")
        title.pack(fill="x")
        tk.Label(title, text=name, bg="#f8faff", fg=INK,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Label(title, textvariable=values["cost"], bg="#f8faff", fg=BLUE,
                 font=("Segoe UI", 13, "bold")).pack(side="right")
        tk.Label(card, textvariable=values["path"], bg="#f8faff", fg=INK,
                 justify="left", anchor="w", wraplength=260,
                 font=("Segoe UI", 9)).pack(fill="x", pady=(2, 2))
        tk.Label(card, textvariable=values["metrics"], bg="#f8faff", fg=MUTED,
                 justify="left", anchor="w", wraplength=260,
                 font=("Segoe UI", 8)).pack(fill="x")

    def choose_file(self) -> None:
        path = filedialog.askopenfilename(title="Pilih graf.txt", filetypes=[("Berkas teks", "*.txt"),
                                                                     ("Semua berkas", "*.*")])
        if path:
            self.open_file(Path(path))

    def open_file(self, path: Path) -> None:
        try:
            graph, start, goal = load_graph(path)
        except (OSError, UnicodeError, ValueError) as exc:
            messagebox.showerror("Gagal membuka graf", str(exc))
            self.step_title.set("Gagal membaca graf")
            self.step_detail.set(str(exc))
            return
        self._pause()
        self.graph, self.start, self.goal = graph, start, goal
        self.file_path.set(path.name)
        self.endpoint_text.set(f"Awal {start}  →  Tujuan {goal}")
        self.results.clear()
        self.reset_animation()
        self.calculate()

    def calculate(self) -> None:
        if not self.graph:
            messagebox.showinfo("Belum ada graf", "Buka file graf.txt terlebih dahulu.")
            return
        self._pause()
        self.results = {
            "Dijkstra": dijkstra(self.graph, self.start, self.goal),
            "Bellman–Ford": bellman_ford(self.graph, self.start, self.goal),
        }
        self._show_results()
        self.reset_animation()

    def _show_results(self) -> None:
        for name, result in self.results.items():
            values = self.card_values[name]
            values["path"].set(" → ".join(result.path) if result.path else "Tidak ada jalur")
            values["cost"].set(format_number(result.cost))
            inspected = sum(step.kind == "inspect" for step in result.steps)
            updated = sum(step.kind == "relax" for step in result.steps)
            values["metrics"].set(
                f"{result.runtime_ns / 1_000_000_000:.6f} s "
                f"({result.runtime_ns / 1000:.1f} µs)\n"
                f"{inspected} sisi diperiksa · {updated} pembaruan"
            )

    def reset_animation(self) -> None:
        self._pause()
        result = self.results.get(self.algorithm.get())
        self.events = result.steps if result else []
        self.step_index = 0
        self.distances = {vertex: math.inf for vertex in self.graph}
        if self.start in self.distances:
            self.distances[self.start] = 0
        self.visited.clear()
        self.current = None
        self.active_edge = None
        self.finished = False
        self.progress.set(f"Langkah 0 / {len(self.events)}")
        self.step_title.set("Siap memutar animasi" if self.events else "Belum ada graf")
        self.step_detail.set("Jarak awal = 0; verteks lain = ∞. Pilih Putar atau Satu langkah."
                             if self.events else "Buka file graf untuk memulai.")
        self.draw_graph()

    def toggle_play(self) -> None:
        if self.playing:
            self._pause()
            return
        if not self.events:
            return
        if self.step_index >= len(self.events):
            self.reset_animation()
        self.playing = True
        self.play_button.configure(text="Jeda")
        self._play_tick()

    def _pause(self) -> None:
        self.playing = False
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        if hasattr(self, "play_button"):
            self.play_button.configure(text="Putar")

    def _play_tick(self) -> None:
        if not self.playing:
            return
        self.next_step()
        if self.playing and self.step_index < len(self.events):
            self.timer = self.after(max(60, int(self.speed.get())), self._play_tick)
        else:
            self._pause()

    def next_step(self) -> None:
        if self.step_index >= len(self.events):
            self._pause()
            return
        step = self.events[self.step_index]
        self.step_index += 1
        self.active_edge = None
        if step.kind == "pass":
            self.current = None
            self.step_title.set(f"Bellman–Ford · putaran {step.iteration}")
            self.step_detail.set("Periksa sisi yang dapat dicapai dan perbarui jarak jika lebih kecil.")
        elif step.kind == "visit" and step.node is not None:
            self.current = step.node
            self.visited.add(step.node)
            self.step_title.set(f"Dijkstra · tetapkan {step.node}")
            self.step_detail.set(f"Jarak terpendek ke {step.node} sudah pasti: "
                                 f"{distance_text(self.distances[step.node])}.")
        elif step.kind in {"inspect", "relax"} and step.node is not None and step.neighbor is not None:
            self.current = step.node
            self.active_edge = (step.node, step.neighbor)
            weight = self.graph[step.node][step.neighbor]
            if step.kind == "inspect":
                candidate = self.distances[step.node] + weight
                self.step_title.set(f"Periksa sisi {step.node} → {step.neighbor}")
                self.step_detail.set(
                    f"{distance_text(self.distances[step.node])} + {format_number(weight)} = "
                    f"{distance_text(candidate)}; jarak {step.neighbor} saat ini "
                    f"{distance_text(self.distances[step.neighbor])}."
                )
            elif step.distance is not None:
                old = self.distances[step.neighbor]
                self.distances[step.neighbor] = step.distance
                self.step_title.set(f"Perbarui jarak {step.neighbor}")
                self.step_detail.set(f"Jarak sementara berubah dari {distance_text(old)} "
                                     f"menjadi {distance_text(step.distance)} lewat {step.node}.")
        elif step.kind == "done":
            self.finished = True
            self.current = None
            result = self.results[self.algorithm.get()]
            self.step_title.set("Pencarian selesai")
            self.step_detail.set("Jalur: " + (" → ".join(result.path) if result.path else "tujuan tidak terjangkau"))
        self.progress.set(f"Langkah {self.step_index} / {len(self.events)}")
        self.draw_graph()

    @staticmethod
    def _weight_label_position(
        first: tuple[float, float], second: tuple[float], text_width: int,
        positions: dict[str, tuple[float, float]], used: list[tuple[float, float]],
        width: int, height: int,
    ) -> tuple[float, float]:
        x1, y1 = first
        x2, y2 = second
        length = math.hypot(x2 - x1, y2 - y1)
        nx, ny = -(y2 - y1) / length, (x2 - x1) / length
        for fraction in (0.5, 0.38, 0.62):
            for offset in (12, -12, 22, -22, 32, -32, 0):
                x = x1 + (x2 - x1) * fraction + nx * offset
                y = y1 + (y2 - y1) * fraction + ny * offset
                if not (text_width / 2 + 3 < x < width - text_width / 2 - 3 and 10 < y < height - 10):
                    continue
                if any(math.hypot(x - px, y - py) < 31 for px, py in positions.values()):
                    continue
                if any(abs(x - px) < text_width / 2 + 17 and abs(y - py) < 18 for px, py in used):
                    continue
                used.append((x, y))
                return x, y
        x, y = (x1 + x2) / 2 + nx * 12, (y1 + y2) / 2 + ny * 12
        used.append((x, y))
        return x, y

    def draw_graph(self) -> None:
        if not hasattr(self, "canvas"):
            return
        canvas = self.canvas
        canvas.delete("all")
        width, height = max(canvas.winfo_width(), 1), max(canvas.winfo_height(), 1)
        if width < 150 or height < 150:
            return  # A Configure event will redraw when the window has a real size.
        if not self.graph:
            canvas.create_text(width / 2, height / 2,
                               text="Buka graf.txt untuk menampilkan graf", fill=MUTED,
                               font=("Segoe UI", 12))
            return

        positions = layered_positions(self.graph, self.start, width, height)
        result = self.results.get(self.algorithm.get())
        route_edges = set(zip(result.path, result.path[1:])) if self.finished and result else set()
        drawn: set[tuple[str, str]] = set()
        used_labels: list[tuple[float, float]] = []

        for vertex, neighbors in self.graph.items():
            for neighbor, weight in neighbors.items():
                reciprocal = self.graph[neighbor].get(vertex) == weight
                key = tuple(sorted((vertex, neighbor))) if reciprocal else (vertex, neighbor)
                if key in drawn:
                    continue
                drawn.add(key)
                x1, y1 = positions[vertex]
                x2, y2 = positions[neighbor]
                highlighted = (vertex, neighbor) in route_edges or (reciprocal and (neighbor, vertex) in route_edges)
                active = self.active_edge == (vertex, neighbor) or (reciprocal and self.active_edge == (neighbor, vertex))
                color = BLUE if highlighted else ORANGE if active else EDGE
                thickness = 4 if highlighted else 3 if active else 1.5
                if vertex == neighbor:
                    canvas.create_arc(x1 - 26, y1 - 42, x1 + 26, y1 + 4,
                                      start=25, extent=290, style="arc", outline=color, width=thickness)
                    canvas.create_text(x1 + 29, y1 - 34, text=format_number(weight), fill=MUTED,
                                       font=("Segoe UI", 8))
                    continue

                length = math.hypot(x2 - x1, y2 - y1)
                if length == 0:
                    continue
                ux, uy = (x2 - x1) / length, (y2 - y1) / length
                nx, ny = -uy, ux
                opposite = vertex in self.graph[neighbor] and not reciprocal
                separation = 5 if opposite else 0
                first = (x1 + ux * 25 + nx * separation, y1 + uy * 25 + ny * separation)
                second = (x2 - ux * 25 + nx * separation, y2 - uy * 25 + ny * separation)
                other_vertices = [point for name, point in positions.items() if name not in {vertex, neighbor}]
                route = _edge_route(first, second, other_vertices, width, height)
                canvas.create_line(*(coordinate for point in route for coordinate in point),
                                   fill=color, width=thickness,
                                   arrow=tk.NONE if reciprocal else tk.LAST)

                label = format_number(weight)
                text_width = max(25, len(label) * 7 + 9)
                label_first, label_second = (route[1], route[2]) if len(route) > 2 else (route[0], route[-1])
                lx, ly = self._weight_label_position(label_first, label_second, text_width,
                                                      positions, used_labels, width, height)
                canvas.create_rectangle(lx - text_width / 2, ly - 9, lx + text_width / 2, ly + 9,
                                        fill="white", outline="")
                canvas.create_text(lx, ly, text=label, fill=BLUE if highlighted else MUTED,
                                   font=("Segoe UI", 8))

        route_nodes = set(result.path) if self.finished and result else set()
        for vertex, (x, y) in positions.items():
            fill, outline = "white", EDGE
            if vertex in self.visited or vertex in route_nodes:
                fill, outline = "#dceafc", BLUE
            if vertex == self.start:
                fill, outline = "#d8f4e8", GREEN
            if vertex == self.goal:
                fill, outline = "#fde4e5", RED
            if vertex == self.current and not self.finished:
                fill, outline = "#fff0d9", ORANGE
            canvas.create_oval(x - 22, y - 22, x + 22, y + 22,
                               fill=fill, outline=outline, width=3)
            canvas.create_text(x, y - 7, text=vertex, fill=INK,
                               font=("Segoe UI", 9, "bold"))
            canvas.create_text(x, y + 9, text=distance_text(self.distances.get(vertex, math.inf)),
                               fill=MUTED, font=("Segoe UI", 8, "bold"))
