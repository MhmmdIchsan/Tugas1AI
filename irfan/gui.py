"""Tkinter visualization. Worker threads compute; only the main thread uses Tk.

Canvas layers, bottom to top: grid, edges, fx (animated), weight labels, nodes, tip.
Static layers redraw on state changes; the fx layer redraws every frame (~30 fps),
so pulses, travelling particles and the path reveal stay smooth on large graphs.
"""
from __future__ import annotations

import math
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from time import perf_counter
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont

from algorithms import Result, Step
from comparison import Comparison, compare, comparison_data, export_json, format_number
from graph_io import Graph, load_graph
from layout import graph_positions

BG = "#0b1120"
SURFACE = "#0f172a"
CARD = "#131c31"
CARD2 = "#1b2640"
BORDER = "#26324d"
INK = "#e2e8f0"
MUTED = "#8394b0"
EDGE = "#34425f"
TREE = "#5b7bb8"
CYAN = "#22d3ee"
GREEN = "#34d399"
RED = "#fb7185"
AMBER = "#fbbf24"
VIOLET = "#a78bfa"
BLUE = "#60a5fa"
ALGO_COLORS = {"Dijkstra": "#38bdf8", "Bellman–Ford": "#c084fc"}
STORY_COLORS = {"idle": MUTED, "pass": BLUE, "visit": VIOLET, "inspect": CYAN,
                "skip": MUTED, "relax": AMBER, "done": GREEN}
FRAME_MS = 33
INF = math.inf


def mix(color: str, other: str, amount: float) -> str:
    """Blend two #rrggbb colors; Tk canvas has no alpha, so glows are blends."""
    a = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def bezier(curve, t: float) -> tuple[float, float]:
    """Point on a quadratic Bézier (start, control, end); edges and particles share it."""
    (x0, y0), (mx, my), (x2, y2) = curve
    a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
    return a * x0 + b * mx + c * x2, a * y0 + b * my + c * y2


def sample(curve, end: float = 1.0, count: int = 14) -> list[float]:
    return [coord for k in range(count + 1) for coord in bezier(curve, end * k / count)]


def ease(t: float) -> float:
    return 1 - (1 - min(max(t, 0.0), 1.0)) ** 3


def num(value) -> str:
    return "∞" if value == INF else format_number(value)


class FlatButton(tk.Label):
    """Flat clickable label: native ttk buttons look dated under Linux Tk."""
    STYLES = {"primary": (CYAN, "#04222b", "#67e8f9"),
              "ghost": (CARD2, INK, "#26365a"),
              "seg": (CARD2, MUTED, "#26365a")}

    def __init__(self, parent, text, command, kind="ghost", font=None) -> None:
        self.base, self.fg, self.hover = self.STYLES[kind]
        super().__init__(parent, text=text, bg=self.base, fg=self.fg, font=font,
                         padx=12, pady=6, cursor="hand2")
        self.command, self.enabled = command, True
        self.bind("<Enter>", lambda _e: self.enabled and self.configure(bg=self.hover))
        self.bind("<Leave>", lambda _e: self.configure(bg=self.base if self.enabled else CARD))
        self.bind("<ButtonRelease-1>", self._click)

    def _click(self, event) -> None:
        if self.enabled and 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self.command()

    def paint(self, base: str, fg: str) -> None:
        self.base, self.fg = base, fg
        self.set_enabled(self.enabled)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.configure(bg=self.base if enabled else CARD, fg=self.fg if enabled else mix(MUTED, CARD, 0.5),
                       cursor="hand2" if enabled else "arrow")


class ShortestPathApp(tk.Tk):
    """Compare two algorithms, replay a trace, inspect distances and export data."""
    def __init__(self, default_file: Path) -> None:
        super().__init__()
        self.title("MMAI1001 · Laboratorium Jalur Terpendek")
        self.geometry("1380x880")
        self.minsize(1120, 740)
        self.configure(bg=BG)
        families = set(tkfont.families(self))
        self.family = next((f for f in ("Inter", "Segoe UI", "SF Pro Text", "Cantarell", "Noto Sans",
                                        "DejaVu Sans") if f in families), "TkDefaultFont")
        self.mono = next((f for f in ("JetBrains Mono", "Cascadia Mono", "Consolas", "Menlo",
                                      "DejaVu Sans Mono") if f in families), "TkFixedFont")
        self.graph: Graph = {}
        self.start = self.goal = ""
        self.results: dict[str, Result] = {}
        self.comparison: Comparison | None = None
        self.events: list[Step] = []
        self.positions: dict[str, tuple[float, float]] = {}
        self.pixel_positions: dict[str, tuple[float, float]] = {}
        self.edge_paths: dict[tuple[str, str], tuple] = {}
        self.bounds = (60.0, 70.0, 1.0, 1.0)
        self.radius = 22
        self.edge_count = 0
        self.dragged: str | None = None
        self.hovered: str | None = None
        self.row_ids: dict[str, str] = {}
        # Replay state, rebuilt from the recorded trace (never re-runs the search).
        self.step_index = 0
        self.dist: dict[str, float] = {}
        self.prev: dict[str, str] = {}
        self.visited: set[str] = set()
        self.current: str | None = None
        self.active_edge: tuple[str, str] | None = None
        self.updated: str | None = None
        self.finished = self.playing = self.busy = False
        self.edge_started = self.reveal_started = self.bars_started = 0.0
        self.timer: str | None = None
        self.poll_timer: str | None = None
        self.jobs: Queue = Queue()
        self.file_path = ""
        self.file_label = tk.StringVar(value="Belum ada file")
        self.algorithm = tk.StringVar(value="Dijkstra")
        self.start_var, self.goal_var = tk.StringVar(), tk.StringVar()
        self.speed = tk.DoubleVar(value=350)
        self.speed_text = tk.StringVar(value="350 ms/langkah")
        self.status = tk.StringVar(value="Pilih file graf untuk memulai.")
        self.progress_text = tk.StringVar(value="0 / 0")
        self.buttons: list[FlatButton] = []
        self._style()
        self._make_widgets()
        self.protocol("WM_DELETE_WINDOW", self.close)
        for key, action in (("<Control-o>", self.choose_file), ("<Escape>", self._pause),
                            ("<space>", self.toggle_play), ("<Right>", self.next_step),
                            ("<Left>", self.previous_step), ("<Home>", self.reset_animation),
                            ("<End>", self.show_final)):
            self.bind(key, lambda _e, run=action: run())
        self.after(100, lambda: self.open_file(default_file))
        self.frame_timer = self.after(FRAME_MS, self._frame)

    # ── construction ──────────────────────────────────────────────────────
    def _font(self, size: int, weight: str = "normal", mono: bool = False):
        return (self.mono if mono else self.family, size, weight)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=CARD, foreground=INK, fieldbackground=CARD2, bordercolor=BORDER,
                        lightcolor=CARD2, darkcolor=CARD2, troughcolor=CARD2, arrowcolor=MUTED,
                        focuscolor=CARD2)
        style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=INK,
                        rowheight=24, borderwidth=0, font=self._font(9, mono=True))
        style.configure("Treeview.Heading", background=CARD2, foreground=MUTED, relief="flat",
                        font=self._font(8, "bold"))
        style.map("Treeview.Heading", background=[("active", CARD2)])
        style.map("Treeview", background=[("selected", mix(CYAN, CARD, 0.78))], foreground=[("selected", INK)])
        style.configure("TCombobox", padding=4, arrowsize=14)
        style.map("TCombobox", fieldbackground=[("readonly", CARD2), ("disabled", CARD)],
                  foreground=[("readonly", INK), ("disabled", MUTED)],
                  selectbackground=[("readonly", CARD2)], selectforeground=[("readonly", INK)],
                  background=[("readonly", CARD2)])
        self.option_add("*TCombobox*Listbox.background", CARD2)
        self.option_add("*TCombobox*Listbox.foreground", INK)
        self.option_add("*TCombobox*Listbox.selectBackground", mix(CYAN, CARD2, 0.6))
        style.configure("Horizontal.TScale", background=CYAN, troughcolor=CARD2, bordercolor=CARD)
        style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=0)
        style.configure("TNotebook.Tab", background=CARD2, foreground=MUTED, padding=(14, 6),
                        borderwidth=0, font=self._font(9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", CARD)], foreground=[("selected", INK)])
        style.configure("Vertical.TScrollbar", background=CARD2, troughcolor=CARD, bordercolor=CARD,
                        arrowcolor=MUTED)

    def _add_button(self, parent, text, command, kind="ghost") -> FlatButton:
        button = FlatButton(parent, text, command, kind, font=self._font(10, "bold"))
        self.buttons.append(button)
        return button

    def _card(self, parent, title: str, right_var: tk.StringVar | None = None, **pack) -> tk.Frame:
        card = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1, padx=14, pady=12)
        card.pack(fill="x", pady=(0, 12), **pack)
        head = tk.Frame(card, bg=CARD)
        head.pack(fill="x", pady=(0, 8))
        tk.Label(head, text=title.upper(), bg=CARD, fg=MUTED, font=self._font(8, "bold")).pack(side="left")
        if right_var is not None:
            tk.Label(head, textvariable=right_var, bg=CARD, fg=INK,
                     font=self._font(9, mono=True)).pack(side="right")
        return card

    def _make_widgets(self) -> None:
        f = self._font
        header = tk.Frame(self, bg=SURFACE, padx=20, pady=12)
        header.pack(fill="x")
        logo = tk.Canvas(header, width=42, height=42, bg=SURFACE, highlightthickness=0)
        logo.pack(side="left")
        logo.create_line(9, 31, 21, 11, 33, 29, fill=TREE, width=2)
        logo.create_line(21, 11, 33, 29, fill=CYAN, width=3)
        for x, y, color in ((9, 31, GREEN), (21, 11, CYAN), (33, 29, RED)):
            logo.create_oval(x - 6, y - 6, x + 6, y + 6, fill=mix(color, SURFACE, 0.6), outline=color, width=2)
        titles = tk.Frame(header, bg=SURFACE)
        titles.pack(side="left", padx=12)
        tk.Label(titles, text="Laboratorium Jalur Terpendek", bg=SURFACE, fg=INK,
                 font=f(17, "bold")).pack(anchor="w")
        tk.Label(titles, text="MMAI1001 · Tugas 1 · Dijkstra vs Bellman–Ford", bg=SURFACE, fg=MUTED,
                 font=f(10)).pack(anchor="w")
        actions = tk.Frame(header, bg=SURFACE)
        actions.pack(side="right")
        self._add_button(actions, "▶  Hitung ulang", self.calculate, "primary").pack(side="right", padx=(8, 0))
        self._add_button(actions, "⤓  Ekspor JSON", self.export_results).pack(side="right", padx=(8, 0))
        self._add_button(actions, "Buka graf…", self.choose_file).pack(side="right", padx=(8, 0))
        tk.Label(actions, textvariable=self.file_label, bg=CARD2, fg=MUTED, font=f(9, mono=True),
                 padx=10, pady=6).pack(side="right")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        bar = tk.Frame(self, bg=BG, padx=20, pady=12)
        bar.pack(fill="x")
        self.endpoint_boxes = []
        for label, variable, color in (("AWAL", self.start_var, GREEN), ("TUJUAN", self.goal_var, RED)):
            tk.Label(bar, text="●", fg=color, bg=BG, font=f(12)).pack(side="left")
            tk.Label(bar, text=label, fg=MUTED, bg=BG, font=f(9, "bold")).pack(side="left", padx=(4, 6))
            box = ttk.Combobox(bar, state="readonly", textvariable=variable, width=8, font=f(10))
            box.pack(side="left")
            box.bind("<<ComboboxSelected>>", lambda _e: self.calculate())
            self.endpoint_boxes.append(box)
            if label == "AWAL":
                self._add_button(bar, "⇄", self.swap_endpoints).pack(side="left", padx=10)
        tk.Frame(bar, bg=BORDER, width=1, height=26).pack(side="left", padx=16)
        tk.Label(bar, text="ALGORITMA", fg=MUTED, bg=BG, font=f(9, "bold")).pack(side="left")
        segments = tk.Frame(bar, bg=CARD2, padx=3, pady=3)
        segments.pack(side="left", padx=8)
        self.segments = {}
        for name in ALGO_COLORS:
            button = self._add_button(segments, name, lambda n=name: self.select_algorithm(n), "seg")
            button.pack(side="left")
            self.segments[name] = button
        self._paint_segments()
        self.info_chips = tk.Frame(bar, bg=BG)
        self.info_chips.pack(side="right")

        footer = tk.Frame(self, bg=SURFACE, padx=20, pady=7)
        footer.pack(side="bottom", fill="x")
        tk.Label(footer, text="Spasi putar/jeda · ←/→ langkah · Home ulang · End akhir · Ctrl+O buka",
                 bg=SURFACE, fg=mix(MUTED, SURFACE, 0.35), font=f(9)).pack(side="right")
        tk.Label(footer, textvariable=self.status, bg=SURFACE, fg=MUTED, font=f(9),
                 anchor="w").pack(side="left", fill="x", expand=True)

        body = tk.Frame(self, bg=BG, padx=20)
        body.pack(fill="both", expand=True, pady=(0, 14))
        side = tk.Frame(body, bg=BG, width=410)
        side.pack(side="right", fill="y", padx=(14, 0))
        side.pack_propagate(False)
        stage = tk.Frame(body, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        stage.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(stage, bg=CARD, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<ButtonPress-1>", lambda e: setattr(self, "dragged", self._node_at(e.x, e.y)))
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", lambda _e: setattr(self, "dragged", None))
        self.canvas.bind("<Motion>", self._hover)
        self.canvas.bind("<Leave>", lambda _e: setattr(self, "hovered", None))
        for button in ("<Button-3>", "<Button-2>"):
            self.canvas.bind(button, self._context_menu)

        player = self._card(side, "Pemutar langkah", self.progress_text)
        self.progress_canvas = tk.Canvas(player, height=16, bg=CARD, highlightthickness=0, cursor="hand2")
        self.progress_canvas.pack(fill="x", pady=(0, 10))
        self.progress_canvas.bind("<Configure>", lambda _e: self._draw_progress())
        self.progress_canvas.bind("<Button-1>", self._seek_click)
        self.progress_canvas.bind("<B1-Motion>", self._seek_click)
        controls = tk.Frame(player, bg=CARD)
        controls.pack(fill="x")
        self._add_button(controls, "↺", self.reset_animation).pack(side="left")
        self._add_button(controls, "‹", self.previous_step).pack(side="left", padx=(6, 0))
        self.play_button = self._add_button(controls, "▶  Putar", self.toggle_play, "primary")
        self.play_button.pack(side="left", fill="x", expand=True, padx=6)
        self._add_button(controls, "›", self.next_step).pack(side="left")
        self._add_button(controls, "Akhir »", self.show_final).pack(side="left", padx=(6, 0))
        speed = tk.Frame(player, bg=CARD)
        speed.pack(fill="x", pady=(10, 0))
        tk.Label(speed, text="lambat", bg=CARD, fg=MUTED, font=f(8)).pack(side="left")
        ttk.Scale(speed, from_=900, to=20, variable=self.speed,
                  command=lambda _v: self.speed_text.set(f"{int(self.speed.get())} ms/langkah")
                  ).pack(side="left", fill="x", expand=True, padx=6)
        tk.Label(speed, text="cepat", bg=CARD, fg=MUTED, font=f(8)).pack(side="left")
        tk.Label(speed, textvariable=self.speed_text, bg=CARD, fg=INK, width=14, anchor="e",
                 font=f(8, mono=True)).pack(side="left")

        story = self._card(side, "Apa yang sedang terjadi?")
        top = tk.Frame(story, bg=CARD)
        top.pack(fill="x")
        self.story_chip = tk.Label(top, bg=CARD2, fg=MUTED, font=f(8, "bold"), padx=8, pady=2)
        self.story_chip.pack(side="left")
        self.story_title = tk.Label(top, bg=CARD, fg=INK, font=f(12, "bold"), anchor="w")
        self.story_title.pack(side="left", padx=8, fill="x", expand=True)
        self.story_body = tk.Label(story, bg=CARD, fg=MUTED, font=f(10), justify="left", anchor="w",
                                   wraplength=370, height=3)
        self.story_body.pack(fill="x", pady=(6, 0))

        comparison = self._card(side, "Perbandingan algoritma")
        self.verdict = tk.Label(comparison, text="Menunggu hasil…", bg=CARD, fg=MUTED, font=f(10, "bold"),
                                anchor="w", justify="left", wraplength=370)
        self.verdict.pack(fill="x")
        self.result_rows = tk.Frame(comparison, bg=CARD)
        self.result_rows.pack(fill="x", pady=4)
        self.chart = tk.Canvas(comparison, height=142, bg=CARD, highlightthickness=0)
        self.chart.pack(fill="x", pady=(4, 0))
        self.chart.bind("<Configure>", lambda _e: self.draw_chart())

        tabs = ttk.Notebook(side)
        tabs.pack(fill="both", expand=True)
        table_frame, log_frame = tk.Frame(tabs, bg=CARD), tk.Frame(tabs, bg=CARD)
        tabs.add(table_frame, text="Tabel jarak")
        tabs.add(log_frame, text="Log langkah")
        self.distance_table = ttk.Treeview(table_frame, columns=("vertex", "distance", "previous", "status"),
                                  show="headings", selectmode="browse")
        for column, label, width in (("vertex", "VERTEKS", 70), ("distance", "JARAK", 80),
                                     ("previous", "VIA", 70), ("status", "STATUS", 100)):
            self.distance_table.heading(column, text=label)
            self.distance_table.column(column, width=width, minwidth=50, anchor="center")
        for tag, color in (("upd", AMBER), ("awal", GREEN), ("tujuan", RED), ("tetap", VIOLET),
                           ("known", INK), ("none", MUTED)):
            self.distance_table.tag_configure(tag, foreground=color)
        scroll = ttk.Scrollbar(table_frame, command=self.distance_table.yview)
        self.distance_table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.distance_table.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, bg=CARD, fg=INK, relief="flat", font=f(9, mono=True), padx=10,
                           pady=8, wrap="none", state="disabled", highlightthickness=0)
        log_scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("num", foreground=mix(MUTED, CARD, 0.4))
        for tag, color in STORY_COLORS.items():
            self.log.tag_configure(tag, foreground=color)
        self._set_story("idle", "SIAP", "Belum ada graf", "Buka berkas graf untuk memulai.")

    # ── file, calculation and results ─────────────────────────────────────
    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        for button in self.buttons:
            button.set_enabled(not busy)
        for box in self.endpoint_boxes:
            box.configure(state="disabled" if busy else "readonly")

    def choose_file(self) -> None:
        if self.busy:
            return
        path = filedialog.askopenfilename(title="Pilih graf.txt", filetypes=[("Berkas teks", "*.txt"),
                                                                            ("Semua berkas", "*.*")])
        if path:
            self.open_file(Path(path))

    def open_file(self, path: Path) -> None:
        if self.busy:
            return
        self._pause()
        try:
            graph, start, goal = load_graph(path)
            if len(graph) > 120 or sum(map(len, graph.values())) > 1200:
                raise ValueError("Visualisasi dibatasi 120 verteks / 1200 sisi berarah. "
                                 "Gunakan --cli untuk graf lebih besar.")
        except (OSError, UnicodeError, ValueError) as exc:
            messagebox.showerror("Gagal membuka graf", str(exc), parent=self)
            self.status.set("Gagal membaca graf. Periksa format berkas lalu buka kembali.")
            return
        self.graph, self.start, self.goal = graph, start, goal
        self.positions = graph_positions(graph)
        self.radius = 22 if len(graph) <= 20 else max(11, 22 - (len(graph) - 20) // 6)
        self.hovered = None
        self.file_path = str(path.resolve())
        self.file_label.set(path.name)
        self.start_var.set(start)
        self.goal_var.set(goal)
        for box in self.endpoint_boxes:
            box.configure(values=list(graph))
        directed = any(graph[n].get(v) != w for v in graph for n, w in graph[v].items())
        self.edge_count = sum(map(len, graph.values()))
        for chip in self.info_chips.winfo_children():
            chip.destroy()
        for text in (f"{len(graph)} verteks", f"{self.edge_count} sisi berarah",
                     "berarah / campuran" if directed else "dua arah"):
            tk.Label(self.info_chips, text=text, bg=CARD2, fg=MUTED, font=self._font(9),
                     padx=10, pady=4).pack(side="left", padx=(6, 0))
        self.calculate()

    def swap_endpoints(self) -> None:
        if self.busy or not self.graph:
            return
        start = self.start_var.get()
        self.start_var.set(self.goal_var.get())
        self.goal_var.set(start)
        self.calculate()

    def calculate(self) -> None:
        if self.busy or not self.graph:
            return
        self._pause()
        self.start, self.goal = self.start_var.get(), self.goal_var.get()
        self.results.clear()
        self.comparison = None
        self.reset_animation()
        self.verdict.configure(text="Menghitung kedua algoritma dan mengukur runtime…", fg=MUTED)
        for row in self.result_rows.winfo_children():
            row.destroy()
        self.draw_chart()
        self._set_busy(True)
        self.status.set("Menghitung… jendela tetap dapat dipindah atau diubah ukurannya.")
        graph, start, goal = self.graph, self.start, self.goal

        def worker() -> None:
            try:
                self.jobs.put(compare(graph, start, goal))
            except Exception as exc:
                self.jobs.put(exc)
        Thread(target=worker, daemon=True).start()
        self.poll_timer = self.after(40, self._poll_result)

    def _poll_result(self) -> None:
        self.poll_timer = None
        try:
            value = self.jobs.get_nowait()
        except Empty:
            self.poll_timer = self.after(40, self._poll_result)
            return
        self._set_busy(False)
        self._paint_segments()
        if isinstance(value, Exception):
            self.verdict.configure(text=f"Perhitungan gagal: {value}", fg=RED)
            self.status.set("Perhitungan gagal. Periksa bobot atau buka graf lain.")
            messagebox.showerror("Perhitungan gagal", str(value), parent=self)
            return
        self.comparison = value
        self.results = {r.name: r for r in value.results}
        self.bars_started = perf_counter()
        self._show_results()
        self.reset_animation()
        self.status.set("Hasil siap. Putar animasi, telusuri langkah, atau lompat ke hasil akhir.")

    def _show_results(self) -> None:
        for row in self.result_rows.winfo_children():
            row.destroy()
        for name, result in self.results.items():
            color = ALGO_COLORS[name]
            row = tk.Frame(self.result_rows, bg=CARD2, padx=10, pady=6)
            row.pack(fill="x", pady=3)
            head = tk.Frame(row, bg=CARD2)
            head.pack(fill="x")
            tk.Label(head, text="●", fg=color, bg=CARD2).pack(side="left")
            tk.Label(head, text=name, fg=INK, bg=CARD2, font=self._font(10, "bold")).pack(side="left", padx=4)
            tk.Label(head, text=f"bobot {num(result.cost)}", fg=color, bg=CARD2,
                     font=self._font(10, "bold", mono=True)).pack(side="right")
            tk.Label(row, text=" → ".join(result.path) or "Tidak ada jalur", fg=MUTED, bg=CARD2,
                     font=self._font(9, mono=True), wraplength=350, justify="left",
                     anchor="w").pack(fill="x")
        timings = self.comparison.timings
        fast, slow = sorted(self.results, key=lambda n: timings[n].median_us)
        ratio = timings[slow].median_us / max(timings[fast].median_us, 1e-9)
        text = ("✓ Bobot minimum sama" if self.comparison.consistent else "⚠ Bobot minimum BERBEDA")
        text += f" · {fast} ≈{ratio:.1f}× lebih cepat (median {self.comparison.repetitions}×)"
        if any(r.trace_truncated for r in self.results.values()):
            text += "\nJejak animasi dibatasi 20.000 langkah; hasil tetap lengkap."
        self.verdict.configure(text=text, fg=GREEN if self.comparison.consistent else RED)
        self.draw_chart()

    def draw_chart(self) -> None:
        chart = self.chart
        chart.delete("all")
        width = max(chart.winfo_width(), 200)
        if self.comparison is None:
            chart.create_text(width / 2, 70, text="Grafik muncul setelah perhitungan selesai",
                              fill=MUTED, font=self._font(9))
            return
        grow = ease((perf_counter() - self.bars_started) / 0.9)
        metrics = (("RUNTIME MEDIAN (µs)", lambda n: self.comparison.timings[n].median_us, "{:.1f}"),
                   ("SISI DIPERIKSA", lambda n: self.results[n].metrics.inspected_edges, "{}"),
                   ("RELAKSASI", lambda n: self.results[n].metrics.relaxations, "{}"))
        track = width - 64
        y = 2
        for title, value_of, pattern in metrics:
            chart.create_text(0, y, text=title, anchor="nw", fill=MUTED, font=self._font(7, "bold"))
            y += 15
            values = {name: value_of(name) for name in self.results}
            top = max(values.values()) or 1
            for name, value in values.items():
                chart.create_rectangle(0, y, track, y + 9, fill=CARD2, outline="")
                chart.create_rectangle(0, y, max(track * value / top * grow, 2), y + 9,
                                       fill=ALGO_COLORS[name], outline="")
                chart.create_text(width, y + 4, text=pattern.format(value), anchor="e", fill=INK,
                                  font=self._font(8, mono=True))
                y += 13
            y += 6

    def export_results(self) -> None:
        if self.busy or self.comparison is None:
            return
        path = filedialog.asksaveasfilename(title="Simpan hasil perbandingan", defaultextension=".json",
                                            initialfile="hasil_perbandingan.json", filetypes=[("JSON", "*.json")])
        if path:
            try:
                export_json(path, comparison_data(self.comparison, self.graph, self.start, self.goal,
                                                  self.file_path))
            except (OSError, ValueError) as exc:
                messagebox.showerror("Ekspor gagal", str(exc), parent=self)
                return
            self.status.set(f"Hasil dan sampel benchmark tersimpan: {path}")

    # ── replay ────────────────────────────────────────────────────────────
    def select_algorithm(self, name: str) -> None:
        if self.busy:
            return
        self.algorithm.set(name)
        self._paint_segments()
        self.reset_animation()

    def _paint_segments(self) -> None:
        for name, button in self.segments.items():
            color = ALGO_COLORS[name]
            selected = name == self.algorithm.get()
            button.paint(mix(color, CARD2, 0.72) if selected else CARD2, color if selected else MUTED)

    def _reset_state(self) -> None:
        self.step_index = 0
        self.dist = {v: INF for v in self.graph}
        if self.start in self.dist:
            self.dist[self.start] = 0
        self.prev.clear()
        self.visited.clear()
        self.current = self.active_edge = self.updated = None
        self.finished = False

    def reset_animation(self) -> None:
        if self.busy:
            return
        self._pause()
        name = self.algorithm.get()
        result = self.results.get(name)
        self.events = result.steps if result else []
        self._reset_state()
        self._clear_log()
        self._rebuild_table()
        if result:
            self._set_story("idle", "SIAP", f"Mulai dari {self.start}",
                            f"Jarak {self.start} = 0, verteks lain ∞. Tekan ▶ Putar (Spasi) atau › "
                            f"untuk melihat {name} bekerja langkah demi langkah.")
        else:
            self._set_story("idle", "SIAP", "Menunggu hasil", "Hasil perhitungan belum tersedia.")
        self._draw_progress()
        self.draw_graph()

    def _apply(self, step: Step) -> tuple[str, str, str, str]:
        """Update replay state from one trace step; return (tag, chip, title, explanation)."""
        self.active_edge = self.updated = None
        if step.kind == "pass":
            self.current = None
            return ("pass", f"PUTARAN {step.iteration}", "Periksa semua sisi",
                    f"Bellman–Ford menelusuri ulang seluruh {self.edge_count} sisi. Jika satu putaran "
                    "penuh tidak mengubah jarak apa pun, pencarian berhenti lebih awal.")
        if step.kind == "visit":
            self.current = step.node
            self.visited.add(step.node)
            ending = " Tujuan tercapai, pencarian berhenti." if step.node == self.goal else ""
            return ("visit", "TETAPKAN", f"{step.node} final = {num(step.distance)}",
                    f"{step.node} punya jarak terkecil di antrean prioritas. Karena bobot tidak negatif, "
                    f"jarak ini pasti terpendek dan tidak akan berubah lagi.{ending}")
        if step.kind in ("inspect", "relax"):
            u, v = step.node, step.neighbor
            self.current, self.active_edge = u, (u, v)
            weight, du, dv = self.graph[u][v], self.dist[u], self.dist[v]
            if step.kind == "relax":
                self.dist[v], self.prev[v], self.updated = step.distance, u, v
                return ("relax", "PERBARUI", f"Jarak {v}: {num(dv)} → {num(step.distance)}",
                        f"Jalan melalui {u} lebih pendek, jadi {v} dicatat dengan pendahulu {u}.")
            if du == INF:
                return ("skip", "LEWATI", f"{u} → {v}",
                        f"Jarak {u} masih ∞ (belum terjangkau), sisi ini belum bisa dipakai.")
            candidate = du + weight
            better = candidate < dv
            return ("inspect", "PERIKSA", f"{u} → {v}  (bobot {num(weight)})",
                    f"{num(du)} + {num(weight)} = {num(candidate)} {'<' if better else '≥'} {num(dv)} "
                    f"(jarak {v} sekarang). "
                    + ("Lebih pendek, akan diperbarui!" if better else "Tidak lebih baik, abaikan."))
        self.finished, self.current = True, None
        result = self.results[self.algorithm.get()]
        body = (f"Jalur terpendek {' → '.join(result.path)} dengan bobot {num(result.cost)}."
                if result.path else f"{self.goal} tidak dapat dicapai dari {self.start}.")
        if result.trace_truncated:
            body += " Jejak animasi terpotong; hasil akhir tetap lengkap."
        return ("done", "SELESAI", "Pencarian selesai", body)

    def _advance(self) -> None:
        if self.step_index >= len(self.events):
            return
        step = self.events[self.step_index]
        before = self.updated
        story = self._apply(step)
        self.step_index += 1
        now = perf_counter()
        self.edge_started = now
        if step.kind == "done":
            self.reveal_started = now
            self._rebuild_table()
        else:
            for vertex in {before, step.node, step.neighbor} - {None}:
                self.distance_table.item(self.row_ids[vertex], values=self._row(vertex), tags=(self._row_tag(vertex),))
            if self.updated:
                self.distance_table.see(self.row_ids[self.updated])
        self._set_story(*story)
        self._log(story[0], story[1], story[2])
        self._draw_progress()
        self.draw_graph()

    def _seek(self, target: int) -> None:
        """Jump anywhere by replaying the trace silently from the beginning."""
        self._reset_state()
        story = None
        while self.step_index < min(target, len(self.events)):
            story = self._apply(self.events[self.step_index])
            self.step_index += 1
        self.edge_started = self.reveal_started = perf_counter()
        self._clear_log()
        self._log("idle", "LOMPAT", f"ke langkah {self.step_index}")
        self._rebuild_table()
        if story:
            self._set_story(*story)
        else:
            self._set_story("idle", "SIAP", f"Mulai dari {self.start}", "Kembali ke keadaan awal.")
        self._draw_progress()
        self.draw_graph()

    def _seek_click(self, event) -> None:
        if self.busy or not self.events:
            return
        self._pause()
        width = max(self.progress_canvas.winfo_width(), 1)
        target = round(min(max(event.x / width, 0), 1) * len(self.events))
        if target != self.step_index:
            self._seek(target)

    def toggle_play(self) -> None:
        if self.busy:
            return
        if self.playing:
            self._pause()
            return
        if not self.events:
            return
        if self.step_index >= len(self.events):
            self.reset_animation()
        self.playing = True
        self.play_button.configure(text="❚❚  Jeda")
        self._play_tick()

    def _pause(self) -> None:
        self.playing = False
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        if hasattr(self, "play_button"):
            self.play_button.configure(text="▶  Putar")

    def _play_tick(self) -> None:
        self.timer = None
        if not self.playing:
            return
        self._advance()
        if self.playing and self.step_index < len(self.events):
            self.timer = self.after(max(20, int(self.speed.get())), self._play_tick)
        else:
            self._pause()

    def next_step(self) -> None:
        if self.busy:
            return
        self._pause()
        self._advance()

    def previous_step(self) -> None:
        if self.busy or self.step_index == 0:
            return
        self._pause()
        self._seek(self.step_index - 1)

    def show_final(self) -> None:
        if self.busy or not self.events:
            return
        self._pause()
        self._seek(len(self.events))

    # ── side panel helpers ────────────────────────────────────────────────
    def _set_story(self, tag: str, chip: str, title: str, body: str) -> None:
        color = STORY_COLORS[tag]
        self.story_chip.configure(text=chip, fg=color, bg=mix(color, CARD, 0.8))
        self.story_title.configure(text=title)
        self.story_body.configure(text=body)
        if tag != "idle":
            self.status.set(f"{chip.capitalize()}: {title}")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _log(self, tag: str, chip: str, title: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"{self.step_index:>5}  ", "num")
        self.log.insert("end", f"{chip:<11}", tag)
        self.log.insert("end", title + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _status_of(self, vertex: str) -> str:
        if vertex in self.visited or (self.finished and self.dist.get(vertex, INF) != INF):
            return "final"
        return "sementara" if self.dist.get(vertex, INF) != INF else "belum"

    def _row(self, vertex: str) -> tuple:
        return vertex, num(self.dist.get(vertex, INF)), self.prev.get(vertex, "—"), self._status_of(vertex)

    def _row_tag(self, vertex: str) -> str:
        if vertex == self.updated:
            return "upd"
        if vertex in (self.start, self.goal):
            return "awal" if vertex == self.start else "tujuan"
        status = self._status_of(vertex)
        return "tetap" if status == "final" else "known" if status == "sementara" else "none"

    def _rebuild_table(self) -> None:
        self.distance_table.delete(*self.distance_table.get_children())
        self.row_ids = {v: self.distance_table.insert("", "end", values=self._row(v), tags=(self._row_tag(v),))
                        for v in self.graph}

    def _draw_progress(self) -> None:
        canvas = self.progress_canvas
        canvas.delete("all")
        width, total = max(canvas.winfo_width(), 50), len(self.events)
        self.progress_text.set(f"Langkah {self.step_index} / {total}")
        color = ALGO_COLORS.get(self.algorithm.get(), CYAN)
        x = min(max(width * (self.step_index / total if total else 0), 7), width - 7)
        canvas.create_rectangle(0, 6, width, 10, fill=CARD2, outline="")
        canvas.create_rectangle(0, 6, x, 10, fill=color, outline="")
        canvas.create_oval(x - 7, 1, x + 7, 15, fill=INK, outline=color, width=2)

    # ── canvas interaction ────────────────────────────────────────────────
    def _canvas_size(self) -> tuple[int, int]:
        return max(self.canvas.winfo_width(), 120), max(self.canvas.winfo_height(), 120)

    def _node_at(self, x: float, y: float) -> str | None:
        return next((v for v, (vx, vy) in self.pixel_positions.items()
                     if math.hypot(x - vx, y - vy) <= self.radius + 4), None)

    def _hover(self, event) -> None:
        node = self._node_at(event.x, event.y)
        if node != self.hovered:
            self.hovered = node
            self.canvas.configure(cursor="fleur" if node else "")

    def _drag(self, event) -> None:
        if self.dragged is None:
            return
        left, top, span_x, span_y = self.bounds
        self.positions[self.dragged] = (min(max((event.x - left) / span_x, 0), 1),
                                        min(max((event.y - top) / span_y, 0), 1))
        self.draw_graph()

    def _context_menu(self, event) -> None:
        node = self._node_at(event.x, event.y)
        if node is None or self.busy:
            return
        menu = tk.Menu(self, tearoff=0, bg=CARD2, fg=INK, activebackground=mix(CYAN, CARD2, 0.55),
                       activeforeground=INK, bd=0, font=self._font(10))
        menu.add_command(label=f"●  Jadikan {node} titik AWAL",
                         command=lambda: self._set_endpoint(self.start_var, node))
        menu.add_command(label=f"●  Jadikan {node} TUJUAN",
                         command=lambda: self._set_endpoint(self.goal_var, node))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _set_endpoint(self, variable: tk.StringVar, node: str) -> None:
        variable.set(node)
        self.calculate()

    def _on_resize(self, _event=None) -> None:
        canvas = self.canvas
        canvas.delete("grid")
        width, height = self._canvas_size()
        dot = mix(BORDER, CARD, 0.35)
        for x in range(16, width, 28):
            for y in range(16, height, 28):
                canvas.create_rectangle(x, y, x + 1, y + 1, fill=dot, outline="", tags="grid")
        canvas.tag_lower("grid")
        self.draw_graph()

    # ── drawing ───────────────────────────────────────────────────────────
    def draw_graph(self) -> None:
        if not hasattr(self, "canvas"):
            return
        canvas = self.canvas
        canvas.delete("graph")
        width, height = self._canvas_size()
        if not self.graph:
            canvas.create_text(width / 2, height / 2, text="Buka graf.txt untuk memulai", fill=MUTED,
                               font=self._font(13), tags="graph")
            return
        r = self.radius
        self.bounds = (60.0, 78.0, max(width - 120.0, 1.0), max(height - 156.0, 1.0))
        left, top, span_x, span_y = self.bounds
        positions = {v: (left + x * span_x, top + y * span_y) for v, (x, y) in self.positions.items()}
        self.pixel_positions = positions
        result = self.results.get(self.algorithm.get())
        tree = {(p, v) for v, p in self.prev.items()}
        self.edge_paths = {}
        drawn, labels = set(), []
        for vertex, neighbors in self.graph.items():
            for neighbor, weight in neighbors.items():
                reciprocal = self.graph[neighbor].get(vertex) == weight
                key = tuple(sorted((vertex, neighbor))) if reciprocal else (vertex, neighbor)
                x1, y1 = positions[vertex]
                if vertex == neighbor:
                    if key not in drawn:
                        drawn.add(key)
                        canvas.create_line(x1 - r * .6, y1 - r * .8, x1 - r * 1.7, y1 - r * 2.6,
                                           x1 + r * 1.7, y1 - r * 2.6, x1 + r * .6, y1 - r * .8,
                                           smooth=True, fill=EDGE, width=1.6, arrow="last", tags="graph")
                        labels.append((x1, y1 - r * 2.3, weight, EDGE))
                    continue
                x2, y2 = positions[neighbor]
                distance = max(math.hypot(x2 - x1, y2 - y1), 0.001)
                ux, uy = (x2 - x1) / distance, (y2 - y1) / distance
                # Opposite arcs with different weights bend to opposite sides.
                bend = 0 if reciprocal or vertex not in self.graph[neighbor] else 36
                tail = r + (2 if reciprocal else 5)
                curve = ((x1 + ux * (r + 2), y1 + uy * (r + 2)),
                         ((x1 + x2) / 2 - uy * bend, (y1 + y2) / 2 + ux * bend),
                         (x2 - ux * tail, y2 - uy * tail))
                self.edge_paths[(vertex, neighbor)] = curve
                if key in drawn:
                    continue
                drawn.add(key)
                in_tree = (vertex, neighbor) in tree or (reciprocal and (neighbor, vertex) in tree)
                color = TREE if in_tree else EDGE
                canvas.create_line(*(sample(curve) if bend else (*curve[0], *curve[2])), fill=color,
                                   width=2.6 if in_tree else 1.6, capstyle="round",
                                   arrow="none" if reciprocal else "last", arrowshape=(10, 12, 4), tags="graph")
                labels.append((*bezier(curve, 0.5), weight, color))
        for x, y, weight, color in labels:
            text = canvas.create_text(x, y, text=format_number(weight), fill=INK if color == TREE else MUTED,
                                      font=self._font(8, mono=True), tags=("graph", "label"))
            x0, y0, x1, y1 = canvas.bbox(text)
            box = canvas.create_rectangle(x0 - 4, y0 - 1, x1 + 4, y1 + 1, fill=CARD, outline=color,
                                          tags=("graph", "label"))
            canvas.tag_lower(box, text)
        route = set(result.path) if self.finished and result else set()
        for vertex, (x, y) in positions.items():
            known = self.dist.get(vertex, INF) != INF
            accent = (GREEN if vertex == self.start else RED if vertex == self.goal
                      else AMBER if vertex == self.current else CYAN if vertex in route
                      else VIOLET if vertex in self.visited else TREE if known else EDGE)
            if accent in (GREEN, RED, CYAN):
                for blend, extra in ((0.9, 10), (0.82, 5)):
                    canvas.create_oval(x - r - extra, y - r - extra, x + r + extra, y + r + extra,
                                       fill=mix(accent, CARD, blend), outline="", tags=("graph", "node"))
            fill = CARD2 if accent == EDGE else mix(accent, CARD, 0.78)
            canvas.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline=accent, width=2.5,
                               tags=("graph", "node"))
            canvas.create_text(x, y, text=vertex, fill=INK, font=self._font(max(7, int(r * 0.42)), "bold"),
                               tags=("graph", "node"))
            if self.events:
                canvas.create_text(x + r * 0.75, y - r * 0.85, text=num(self.dist.get(vertex, INF)), anchor="sw",
                                   fill=AMBER if vertex == self.updated else INK if known else MUTED,
                                   font=self._font(8, "bold", mono=True), tags=("graph", "node"))
            marker = ("AWAL · TUJUAN" if vertex == self.start == self.goal else "AWAL" if vertex == self.start
                      else "TUJUAN" if vertex == self.goal else "")
            if marker:
                canvas.create_text(x, y + r + 12, text=marker, fill=accent, font=self._font(7, "bold"),
                                   tags=("graph", "node"))
        name = self.algorithm.get()
        if self.finished and result:
            banner = (f"Jalur terpendek   {' → '.join(result.path)}   ·   bobot {num(result.cost)}"
                      if result.path else f"{self.goal} tidak terjangkau dari {self.start}")
            color = CYAN if result.path else RED
        else:
            banner, color = f"{name}   ·   {self.start} → {self.goal}", ALGO_COLORS.get(name, CYAN)
        text = canvas.create_text(30, 26, anchor="nw", text=banner, fill=color, font=self._font(11, "bold"),
                                  tags="graph")
        x0, y0, x1, y1 = canvas.bbox(text)
        box = canvas.create_rectangle(x0 - 12, y0 - 7, x1 + 12, y1 + 7, fill=mix(color, CARD, 0.86),
                                      outline=mix(color, CARD, 0.4), tags="graph")
        canvas.tag_lower(box, text)
        hint = canvas.create_text(width - 20, 22, anchor="ne", text="seret simpul · klik kanan: jadikan awal/tujuan",
                                  fill=mix(MUTED, CARD, 0.3), font=self._font(9), tags="graph")
        if canvas.bbox(hint)[0] < x1 + 24:
            canvas.delete(hint)
        x = 22
        for label, color in (("Awal", GREEN), ("Tujuan", RED), ("Diproses", AMBER), ("Ditetapkan", VIOLET),
                             ("Jarak diketahui", TREE), ("Jalur terpendek", CYAN)):
            canvas.create_oval(x, height - 28, x + 10, height - 18, fill=color, outline="", tags="graph")
            item = canvas.create_text(x + 16, height - 23, text=label, anchor="w", fill=MUTED,
                                      font=self._font(9), tags="graph")
            x = canvas.bbox(item)[2] + 18

    def _frame(self) -> None:
        """Animation clock: redraw only the cheap fx/tip layers every frame."""
        self.frame_timer = self.after(FRAME_MS, self._frame)
        canvas, now = self.canvas, perf_counter()
        canvas.delete("fx", "tip")
        if self.comparison is not None and now - self.bars_started < 1.0:
            self.draw_chart()
        width, height = self._canvas_size()
        if self.busy:
            angle = now * 360 % 360
            canvas.create_oval(width / 2 - 40, height / 2 - 40, width / 2 + 40, height / 2 + 64,
                               fill=CARD, outline="", tags="tip")
            canvas.create_arc(width / 2 - 22, height / 2 - 22, width / 2 + 22, height / 2 + 22, start=-angle,
                              extent=270, style="arc", outline=CYAN, width=4, tags="tip")
            canvas.create_text(width / 2, height / 2 + 42, text="Menghitung…", fill=MUTED,
                               font=self._font(9), tags="tip")
        if not self.graph or not self.pixel_positions:
            return
        r, positions = self.radius, self.pixel_positions
        pulse = (math.sin(now * 6) + 1) / 2
        if self.current in positions and not self.finished:
            x, y = positions[self.current]
            for spread, blend in ((5 + pulse * 7, 0.35 + pulse * 0.5), (3, 0.2)):
                e = r + spread
                canvas.create_oval(x - e, y - e, x + e, y + e, outline=mix(AMBER, CARD, blend), width=2,
                                   tags="fx")
        curve = self.edge_paths.get(self.active_edge) if self.active_edge else None
        if curve:
            points = sample(curve)
            canvas.create_line(*points, fill=mix(AMBER, CARD, 0.65), width=8, capstyle="round", tags="fx")
            canvas.create_line(*points, fill=AMBER, width=2.5, capstyle="round", tags="fx")
            duration = min(max(self.speed.get(), 150), 700) / 1000
            px, py = bezier(curve, ease((now - self.edge_started) / duration))
            canvas.create_oval(px - 7, py - 7, px + 7, py + 7, fill=mix(AMBER, CARD, 0.45), outline="", tags="fx")
            canvas.create_oval(px - 3.5, py - 3.5, px + 3.5, py + 3.5, fill="#fff7d6", outline="", tags="fx")
        result = self.results.get(self.algorithm.get())
        if self.finished and result and len(result.path) > 1:
            segments = list(zip(result.path, result.path[1:]))
            progress = (now - self.reveal_started) / 0.22
            for index, edge in enumerate(segments):
                part = min(progress - index, 1)
                if part <= 0:
                    break
                if edge in self.edge_paths:
                    points = sample(self.edge_paths[edge], part)
                    canvas.create_line(*points, fill=mix(CYAN, CARD, 0.7), width=11, capstyle="round", tags="fx")
                    canvas.create_line(*points, fill=CYAN, width=4, capstyle="round", tags="fx")
            if progress >= len(segments):
                travel = (now - self.reveal_started) * 0.5 % 1 * len(segments)
                edge = segments[int(travel)]
                if edge in self.edge_paths:
                    px, py = bezier(self.edge_paths[edge], travel % 1)
                    canvas.create_oval(px - 5, py - 5, px + 5, py + 5, fill="#e0fbff", outline="", tags="fx")
        anchor = canvas.find_withtag("label") or canvas.find_withtag("node")
        if anchor:
            canvas.tag_lower("fx", anchor[0])
        if self.hovered in positions and self.dragged is None:
            vertex = self.hovered
            x, y = positions[vertex]
            lines = (f"{vertex}", f"jarak     {num(self.dist.get(vertex, INF))}",
                     f"via       {self.prev.get(vertex, '—')}", f"status    {self._status_of(vertex)}",
                     f"tetangga  {len(self.graph[vertex])}")
            text = canvas.create_text(x + r + 14, y - r, anchor="nw", text="\n".join(lines), fill=INK,
                                      font=self._font(9, mono=True), tags="tip")
            x0, y0, x1, y1 = canvas.bbox(text)
            dx = -(x1 - x0) - 2 * r - 28 if x1 > width - 8 else 0
            dy = min(height - 12 - y1, 0) + max(12 - y0, 0)
            if dx or dy:
                canvas.move(text, dx, dy)
                x0, y0, x1, y1 = canvas.bbox(text)
            box = canvas.create_rectangle(x0 - 10, y0 - 8, x1 + 10, y1 + 8, fill=SURFACE, outline=BORDER,
                                          tags="tip")
            canvas.tag_lower(box, text)

    def close(self) -> None:
        self._pause()
        for timer in (self.poll_timer, self.frame_timer):
            if timer is not None:
                self.after_cancel(timer)
        self.destroy()
