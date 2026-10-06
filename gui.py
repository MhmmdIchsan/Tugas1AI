"""Tkinter interface for comparing and animating shortest path searches."""

from __future__ import annotations

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
    if math.isinf(value):
        return "Tidak ada jalur"
    return f"{value:g}"


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
        self.visited: set[str] = set()
        self.current: str | None = None
        self.active_edge: tuple[str, str] | None = None
        self.finished = False
        self.playing = False
        self.timer: str | None = None
        self.file_path = tk.StringVar(value="Belum ada file")
        self.algorithm = tk.StringVar(value="Dijkstra")
        self.speed = tk.IntVar(value=260)
        self.status = tk.StringVar(value="Pilih file graf untuk memulai.")
        self.progress = tk.StringVar(value="Langkah 0 / 0")

        self._make_widgets()
        self.after(100, lambda: self.open_file(default_file) if default_file.exists() else None)

    def _make_widgets(self) -> None:
        heading = tk.Frame(self, bg=BG, padx=20, pady=15)
        heading.pack(fill="x")
        tk.Label(heading, text="Pencarian Jalur Terpendek", bg=BG, fg=INK,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(heading, text="Bandingkan Dijkstra dan Bellman–Ford, lalu amati prosesnya.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")

        controls = tk.Frame(self, bg=BG, padx=20)
        controls.pack(fill="x", pady=(0, 10))
        ttk.Button(controls, text="Buka graf.txt", command=self.choose_file).pack(side="left")
        tk.Label(controls, textvariable=self.file_path, bg=BG, fg=MUTED,
                 font=("Segoe UI", 9), anchor="w").pack(side="left", padx=12, fill="x", expand=True)
        ttk.Button(controls, text="Hitung keduanya", command=self.calculate).pack(side="right")

        body = tk.PanedWindow(self, orient="horizontal", bg=BG, sashwidth=6, borderwidth=0)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        graph_panel = tk.Frame(body, bg="white", highlightbackground="#d9e1ec", highlightthickness=1)
        side_panel = tk.Frame(body, bg="white", highlightbackground="#d9e1ec", highlightthickness=1)
        body.add(graph_panel, minsize=510, stretch="always")
        body.add(side_panel, minsize=310, stretch="never")

        tk.Label(graph_panel, text="Visualisasi graf", bg="white", fg=INK,
                 font=("Segoe UI", 13, "bold"), padx=16, pady=12).pack(anchor="w")
        self.canvas = tk.Canvas(graph_panel, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.canvas.bind("<Configure>", lambda _event: self.draw_graph())

        tk.Label(side_panel, text="Hasil perbandingan", bg="white", fg=INK,
                 font=("Segoe UI", 13, "bold"), padx=16, pady=12).pack(anchor="w")
        self.results_text = tk.Text(side_panel, height=15, wrap="word", bg="white", fg=INK,
                                    relief="flat", padx=15, pady=5, font=("Consolas", 10))
        self.results_text.pack(fill="both", expand=True)
        self.results_text.configure(state="disabled")

        player = tk.Frame(side_panel, bg="white", padx=16, pady=12)
        player.pack(fill="x")
        tk.Label(player, text="Animasi algoritma", bg="white", fg=INK,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        selector = ttk.Combobox(player, state="readonly", textvariable=self.algorithm,
                                values=("Dijkstra", "Bellman–Ford"))
        selector.pack(fill="x", pady=(5, 10))
        selector.bind("<<ComboboxSelected>>", lambda _event: self.reset_animation())
        buttons = tk.Frame(player, bg="white")
        buttons.pack(fill="x")
        self.play_button = ttk.Button(buttons, text="Putar", command=self.toggle_play)
        self.play_button.pack(side="left")
        ttk.Button(buttons, text="Satu langkah", command=self.next_step).pack(side="left", padx=7)
        ttk.Button(buttons, text="Ulangi", command=self.reset_animation).pack(side="left")
        tk.Label(player, textvariable=self.progress, bg="white", fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(12, 2))
        tk.Label(player, text="Jeda per langkah (ms)", bg="white", fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w")
        ttk.Scale(player, from_=60, to=900, variable=self.speed).pack(fill="x")

        footer = tk.Frame(self, bg=BG, padx=20, pady=5)
        footer.pack(fill="x", side="bottom")
        tk.Label(footer, text="● awal", fg=GREEN, bg=BG).pack(side="left")
        tk.Label(footer, text="● tujuan", fg=RED, bg=BG).pack(side="left", padx=12)
        tk.Label(footer, text="● sedang diproses", fg=ORANGE, bg=BG).pack(side="left")
        tk.Label(footer, text="● jalur terpendek", fg=BLUE, bg=BG).pack(side="left", padx=12)
        tk.Label(footer, textvariable=self.status, fg=MUTED, bg=BG,
                 anchor="e").pack(side="right", fill="x", expand=True)

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
            self.status.set("Gagal membaca graf.")
            return
        self._pause()
        self.graph, self.start, self.goal = graph, start, goal
        self.file_path.set(str(path))
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
        self.status.set("Hasil siap. Animasi dapat diputar atau dilangkahkan.")

    def _show_results(self) -> None:
        lines = [f"Awal: {self.start}    Tujuan: {self.goal}", ""]
        for name, result in self.results.items():
            route = " → ".join(result.path) if result.path else "Tidak ada jalur"
            lines += [name, f"  Jalur : {route}",
                      f"  Bobot : {format_number(result.cost)}",
                      f"  Waktu : {result.runtime_ns / 1000:.2f} µs", ""]
        lines.append("Waktu hanya mencakup perhitungan;\nanimasi tidak ikut diukur.")
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.insert("1.0", "\n".join(lines))
        self.results_text.configure(state="disabled")

    def reset_animation(self) -> None:
        self._pause()
        result = self.results.get(self.algorithm.get())
        self.events = result.steps if result else []
        self.step_index = 0
        self.visited.clear()
        self.current = None
        self.active_edge = None
        self.finished = False
        self.progress.set(f"Langkah 0 / {len(self.events)}")
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
            self.status.set(f"Bellman–Ford: iterasi {step.iteration}.")
        elif step.kind == "visit":
            self.current = step.node
            self.visited.add(step.node or "")
            self.status.set(f"Dijkstra: tetapkan {step.node}, jarak {format_number(step.distance or 0)}.")
        elif step.kind in {"inspect", "relax"}:
            self.current = step.node
            self.active_edge = (step.node or "", step.neighbor or "")
            verb = "Perbarui" if step.kind == "relax" else "Periksa"
            detail = f"; jarak baru {format_number(step.distance)}" if step.kind == "relax" else ""
            self.status.set(f"{verb} {step.node} → {step.neighbor}{detail}.")
        elif step.kind == "done":
            self.finished = True
            result = self.results[self.algorithm.get()]
            self.status.set("Selesai: " + (" → ".join(result.path) if result.path else "tujuan tak terjangkau"))
        self.progress.set(f"Langkah {self.step_index} / {len(self.events)}")
        self.draw_graph()

    def draw_graph(self) -> None:
        if not hasattr(self, "canvas"):
            return
        canvas = self.canvas
        canvas.delete("all")
        if not self.graph:
            canvas.create_text(max(canvas.winfo_width() // 2, 250),
                               max(canvas.winfo_height() // 2, 250),
                               text="Buka graf.txt untuk menampilkan graf", fill=MUTED,
                               font=("Segoe UI", 12))
            return

        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 420)
        vertices = list(self.graph)
        radius = min(width * 0.39, height * 0.39)
        positions = {
            vertex: (width / 2 + radius * math.cos(-math.pi / 2 + 2 * math.pi * index / len(vertices)),
                     height / 2 + radius * math.sin(-math.pi / 2 + 2 * math.pi * index / len(vertices)))
            for index, vertex in enumerate(vertices)
        }
        result = self.results.get(self.algorithm.get())
        route_edges = set(zip(result.path, result.path[1:])) if self.finished and result else set()
        drawn: set[tuple[str, str]] = set()

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
                    canvas.create_arc(x1 - 27, y1 - 42, x1 + 27, y1 + 5,
                                      start=25, extent=290, style="arc", outline=color, width=thickness)
                    continue
                distance = math.hypot(x2 - x1, y2 - y1)
                ux, uy = (x2 - x1) / distance, (y2 - y1) / distance
                start_x, start_y = x1 + ux * 23, y1 + uy * 23
                end_x, end_y = x2 - ux * 23, y2 - uy * 23
                canvas.create_line(start_x, start_y, end_x, end_y, fill=color,
                                   width=thickness, arrow="none" if reciprocal else "last")
                mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
                canvas.create_rectangle(mid_x - 14, mid_y - 10, mid_x + 14, mid_y + 10,
                                        fill="white", outline="")
                canvas.create_text(mid_x, mid_y, text=format_number(weight),
                                   fill=BLUE if highlighted else MUTED, font=("Segoe UI", 8))

        route_nodes = set(result.path) if self.finished and result else set()
        for vertex, (x, y) in positions.items():
            fill = "white"
            outline = EDGE
            if vertex in self.visited:
                fill, outline = "#dceafc", BLUE
            if vertex in route_nodes:
                fill, outline = "#dceafc", BLUE
            if vertex == self.start:
                fill, outline = "#d8f4e8", GREEN
            if vertex == self.goal:
                fill, outline = "#fde4e5", RED
            if vertex == self.current and not self.finished:
                fill, outline = "#fff0d9", ORANGE
            canvas.create_oval(x - 22, y - 22, x + 22, y + 22,
                               fill=fill, outline=outline, width=3)
            canvas.create_text(x, y, text=vertex, fill=INK, font=("Segoe UI", 9, "bold"))
