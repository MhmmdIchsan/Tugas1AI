"""Interactive Tkinter studio for the shortest-path assignment."""

from __future__ import annotations

import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ichsan.algorithms import Result, bellman_ford, dijkstra
from ichsan.examples import EXAMPLES, example_path
from ichsan.graph_io import Graph, load_graph
from ichsan.graph_view import GraphCanvas
from ichsan.playback import Playback, number

BG, WHITE, INK, MUTED = "#eef3f6", "#ffffff", "#172b3a", "#627789"
BORDER, TEAL, SOFT = "#dce5eb", "#087f8c", "#e8f5f5"
DIJKSTRA, BELLMAN = "Dijkstra", "Bellman–Ford"
DEFAULT_SOURCE = "graf.txt · file utama"
SPEEDS = {"0.5×": 840, "1×": 420, "2×": 210, "4×": 105}
CANVAS_HINT = "Seret simpul untuk mengatur posisi · roda mouse untuk zoom · seret latar untuk menggeser"


def result_report(results: dict[str, Result], source: str, start: str, goal: str) -> str:
    """Export already measured results; this does not run the search again."""
    lines = ["HASIL PENCARIAN JALUR TERPENDEK", f"Sumber: {source}", f"Awal: {start} | Tujuan: {goal}", ""]
    for name, result in results.items():
        lines.extend([name,
                      "Jalur: " + (" → ".join(result.path) if result.path else "Tidak ada jalur"),
                      "Bobot minimum: " + (number(result.cost) if result.path else "Tidak terjangkau"),
                      f"Waktu: {result.runtime_ns / 1_000_000_000:.6f} s ({result.runtime_ns / 1000:.1f} µs)",
                      f"Sisi diperiksa: {sum(step.kind == 'inspect' for step in result.steps)}",
                      f"Pembaruan jarak: {sum(step.kind == 'relax' for step in result.steps)}", ""])
    lines.append("Waktu mencakup perhitungan dan pencatatan langkah; animasi tidak ikut diukur.")
    return "\n".join(lines) + "\n"


class ShortestPathApp(tk.Tk):
    def __init__(self, default_file: Path) -> None:
        super().__init__()
        self.title("Jalur Terpendek · MMAI1001")
        self.geometry(f"{min(1280, self.winfo_screenwidth() - 70)}x{min(850, self.winfo_screenheight() - 100)}")
        self.minsize(1000, 680)
        self.configure(bg=BG)
        self.default_file = default_file.resolve()
        self.graph: Graph = {}
        self.start = self.goal = ""
        self.source_path: Path | None = None
        self.results: dict[str, Result] = {}
        self.playback: Playback | None = None
        self.playing = False
        self.timer: str | None = None
        self.startup_timer: str | None = None
        self._syncing = False
        self.source = tk.StringVar(value=DEFAULT_SOURCE)
        self.source_info = tk.StringVar(value="Pilih contoh dari soal atau buka file graf sendiri.")
        self.start_value, self.goal_value = tk.StringVar(), tk.StringVar()
        self.algorithm = tk.StringVar(value=DIJKSTRA)
        self.speed = tk.StringVar(value="1×")
        self.progress_value = tk.DoubleVar(value=0)
        self.progress_text = tk.StringVar(value="0 / 0 langkah")
        self.step_title = tk.StringVar(value="Siap menjelajahi graf")
        self.step_detail = tk.StringVar(value="Pilih graf untuk memulai.")
        self.canvas_hint = tk.StringVar(value=CANVAS_HINT)
        self.route_label = tk.StringVar(value="AWAL → TUJUAN")
        self.compare_text = tk.StringVar(value="Hasil kedua algoritma akan muncul di sini.")
        self.card_values: dict[str, dict[str, tk.StringVar]] = {}
        self.card_frames: dict[str, tk.Frame] = {}
        self.source_paths = {DEFAULT_SOURCE: self.default_file,
                             **{example.title: example_path(example) for example in EXAMPLES}}
        self._style()
        self._build()
        for key, action in (("<space>", self.toggle_play), ("<Left>", self.previous_step),
                            ("<Right>", self.next_step), ("<Home>", self.reset_animation), ("<End>", self.show_final)):
            self.bind(key, lambda event, callback=action: self._shortcut(event, callback))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.startup_timer = self.after_idle(self._load_initial)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", font=("Segoe UI", 9), padding=(10, 7), background=WHITE,
                        foreground=INK, bordercolor=BORDER, lightcolor=WHITE, darkcolor=WHITE, focuscolor=WHITE)
        style.map("TButton", background=[("active", "#e7eff4"), ("pressed", "#dae6ed")], foreground=[("disabled", "#9aabb5")])
        style.configure("Accent.TButton", background=TEAL, foreground=WHITE, bordercolor=TEAL,
                        lightcolor=TEAL, darkcolor=TEAL, focuscolor=TEAL, font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#096d78"), ("pressed", "#075964")])
        style.configure("Compact.TButton", padding=(8, 4))
        style.configure("Algorithm.TRadiobutton", background=WHITE, foreground=MUTED,
                        font=("Segoe UI", 10, "bold"), padding=(10, 6))
        style.map("Algorithm.TRadiobutton", foreground=[("selected", TEAL)],
                  background=[("selected", SOFT), ("active", "#f0f5f8")])
        style.configure("TCombobox", padding=(7, 5), fieldbackground=WHITE, foreground=INK,
                        bordercolor=BORDER, arrowcolor=MUTED, selectbackground=SOFT, selectforeground=INK)
        style.map("TCombobox", fieldbackground=[("readonly", WHITE)], foreground=[("readonly", INK)])
        style.configure("TScale", background=WHITE, troughcolor="#e3ecef", bordercolor=WHITE)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 10), background="#e6edf2", foreground=MUTED,
                        font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", WHITE)], foreground=[("selected", TEAL)])
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=32, background=WHITE,
                        fieldbackground=WHITE, foreground=INK, borderwidth=0)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#edf3f6",
                        foreground=MUTED, padding=(4, 8))
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

    @staticmethod
    def _label(parent, text="", variable=None, size=10, color=INK, bold=False, bg=WHITE, **kwargs):
        return tk.Label(parent, text=text, textvariable=variable, bg=bg, fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"), **kwargs)

    def _build(self) -> None:
        header = tk.Frame(self, bg=BG, padx=24, pady=16)
        header.pack(fill="x")
        mark = tk.Canvas(header, width=42, height=45, bg=BG, highlightthickness=0)
        mark.pack(side="left", padx=(0, 12))
        mark.create_line(10, 30, 28, 10, 34, 34, fill=TEAL, width=3, joinstyle="round")
        for x, y in ((10, 30), (28, 10), (34, 34)):
            mark.create_oval(x - 5, y - 5, x + 5, y + 5, fill=TEAL, outline=BG, width=2)
        titles = tk.Frame(header, bg=BG)
        titles.pack(side="left")
        self._label(titles, "Jalur terpendek", size=23, bold=True, bg=BG).pack(anchor="w")
        self._label(titles, "Eksplorasi graf dan bandingkan dua cara pencarian", color=MUTED, bg=BG).pack(anchor="w", pady=(2, 0))
        self._label(header, "MMAI1001  /  TUGAS 01", color=TEAL, size=9, bold=True, bg=BG).pack(side="right")

        setup = tk.Frame(self, bg=WHITE, padx=14, pady=10, highlightbackground=BORDER, highlightthickness=1)
        setup.pack(fill="x", padx=22, pady=(0, 12))
        setup.columnconfigure(0, weight=1)
        self._label(setup, "SUMBER GRAF", size=8, bold=True, color=MUTED).grid(row=0, column=0, sticky="w")
        self._label(setup, "AWAL", size=8, bold=True, color=MUTED).grid(row=0, column=2, sticky="w", padx=(16, 0))
        self._label(setup, "TUJUAN", size=8, bold=True, color=MUTED).grid(row=0, column=4, sticky="w")
        self.source_selector = ttk.Combobox(setup, textvariable=self.source, state="readonly", values=list(self.source_paths), width=29)
        self.source_selector.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        self.source_selector.bind("<<ComboboxSelected>>", self._select_source)
        ttk.Button(setup, text="Buka file…", command=self.choose_file).grid(row=1, column=1, padx=(8, 0))
        self.start_selector = ttk.Combobox(setup, textvariable=self.start_value, state="disabled", width=7)
        self.start_selector.grid(row=1, column=2, padx=(16, 0))
        ttk.Button(setup, text="⇄", width=2, command=self.swap_endpoints).grid(row=1, column=3, padx=5)
        self.goal_selector = ttk.Combobox(setup, textvariable=self.goal_value, state="disabled", width=7)
        self.goal_selector.grid(row=1, column=4)
        self.start_selector.bind("<<ComboboxSelected>>", self._change_endpoints)
        self.goal_selector.bind("<<ComboboxSelected>>", self._change_endpoints)
        ttk.Button(setup, text="Hitung ulang", command=self.calculate).grid(row=1, column=5, padx=(12, 0))
        self._label(setup, variable=self.source_info, size=9, color=MUTED).grid(row=2, column=0, columnspan=6, sticky="w", pady=(7, 0))

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 14))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, minsize=330)
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self._build_stage(left)
        self._build_transport(left)
        self._build_results(body)

    def _build_stage(self, parent) -> None:
        stage = tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        stage.grid(row=0, column=0, sticky="nsew")
        top = tk.Frame(stage, bg=WHITE, padx=14, pady=10)
        top.pack(fill="x")
        self._label(top, "Peta graf", size=12, bold=True).pack(side="left")
        self._label(top, variable=self.route_label, size=9, color=TEAL, bold=True).pack(side="left", padx=12)
        ttk.Button(top, text="Atur ulang", style="Compact.TButton", command=self.reset_view).pack(side="right")
        ttk.Button(top, text="+", width=2, style="Compact.TButton", command=lambda: self.canvas.zoom_in()).pack(side="right", padx=4)
        ttk.Button(top, text="−", width=2, style="Compact.TButton", command=lambda: self.canvas.zoom_out()).pack(side="right")
        self.canvas = GraphCanvas(stage, on_hover=self._hover_vertex, bg=WHITE, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=5)
        legend = tk.Frame(stage, bg=WHITE, padx=14, pady=5)
        legend.pack(fill="x")
        for text, color in (("● Awal", "#15966b"), ("● Tujuan", "#d26863"), ("● Diproses", "#d58b24"), ("● Jalur akhir", TEAL)):
            self._label(legend, text, color=color, size=8).pack(side="left", padx=(0, 13))
        hint = self._label(stage, variable=self.canvas_hint, color=MUTED, size=8, anchor="w", justify="left")
        hint.pack(fill="x", padx=14, pady=(0, 9))
        stage.bind("<Configure>", lambda e: hint.configure(wraplength=max(250, e.width - 30)))

    def _build_transport(self, parent) -> None:
        panel = tk.Frame(parent, bg=WHITE, padx=12, pady=10, highlightbackground=BORDER, highlightthickness=1)
        panel.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        algo = tk.Frame(panel, bg=WHITE)
        algo.pack(fill="x")
        for name in (DIJKSTRA, BELLMAN):
            ttk.Radiobutton(algo, text=name, variable=self.algorithm, value=name, style="Algorithm.TRadiobutton",
                            command=self._select_algorithm).pack(side="left", padx=(0, 5))
        speed = ttk.Combobox(algo, textvariable=self.speed, values=list(SPEEDS), state="readonly", width=5)
        speed.pack(side="right")
        speed.bind("<<ComboboxSelected>>", self._change_speed)
        self._label(algo, "Kecepatan", size=9, color=MUTED).pack(side="right", padx=6)
        controls = tk.Frame(panel, bg=WHITE)
        controls.pack(fill="x", pady=(8, 5))
        self.play_button = ttk.Button(controls, text="▶  Putar", style="Accent.TButton", command=self.toggle_play)
        self.play_button.pack(side="left", padx=(0, 7))
        ttk.Button(controls, text="‹ Mundur", command=self.previous_step).pack(side="left", padx=(0, 5))
        ttk.Button(controls, text="Maju ›", command=self.next_step).pack(side="left", padx=(0, 5))
        ttk.Button(controls, text="Ulangi", command=self.reset_animation).pack(side="left")
        ttk.Button(controls, text="Hasil akhir", command=self.show_final).pack(side="right")
        progress = tk.Frame(panel, bg=WHITE)
        progress.pack(fill="x")
        self.seek_scale = ttk.Scale(progress, from_=0, to=1, variable=self.progress_value, command=self._seek)
        self.seek_scale.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._label(progress, variable=self.progress_text, size=8, color=MUTED).pack(side="right")
        detail = tk.Frame(panel, bg=SOFT, height=76, padx=11, pady=8)
        detail.pack(fill="x", pady=(6, 0))
        detail.pack_propagate(False)
        self._label(detail, variable=self.step_title, size=10, bold=True, color=TEAL, bg=SOFT, anchor="w").pack(fill="x")
        text = self._label(detail, variable=self.step_detail, color=INK, size=9, bg=SOFT, anchor="nw", justify="left")
        text.pack(fill="x", pady=(3, 0))
        detail.bind("<Configure>", lambda e: text.configure(wraplength=max(250, e.width - 24)))

    def _build_results(self, parent) -> None:
        side = tk.Frame(parent, bg=BG, width=335)
        side.grid(row=0, column=1, sticky="nsew")
        side.grid_propagate(False)
        side.rowconfigure(0, weight=1)
        side.columnconfigure(0, weight=1)
        self.notebook = ttk.Notebook(side)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        results_tab, distance_tab, guide_tab = (tk.Frame(self.notebook, bg=WHITE) for _ in range(3))
        for frame, title in ((results_tab, "Hasil"), (distance_tab, "Jarak"), (guide_tab, "Panduan")):
            self.notebook.add(frame, text=title)
        scroller = tk.Canvas(results_tab, bg=WHITE, highlightthickness=0, width=320)
        bar = ttk.Scrollbar(results_tab, orient="vertical", command=scroller.yview)
        scroller.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        scroller.pack(side="left", fill="both", expand=True)
        cards = tk.Frame(scroller, bg=WHITE, padx=11, pady=11)
        window = scroller.create_window((0, 0), window=cards, anchor="nw")
        cards.bind("<Configure>", lambda _e: scroller.configure(scrollregion=scroller.bbox("all")))
        scroller.bind("<Configure>", lambda e: scroller.itemconfigure(window, width=e.width))
        self._label(cards, "PERBANDINGAN ALGORITMA", size=8, color=MUTED, bold=True).pack(anchor="w", pady=(0, 8))
        for name in (DIJKSTRA, BELLMAN):
            self._make_result_card(cards, name)
        self._label(cards, variable=self.compare_text, size=9, color=TEAL, justify="left", wraplength=270).pack(anchor="w", pady=(2, 7))
        self._label(cards, "Waktu mencakup komputasi dan pencatatan langkah, tanpa animasi. Nilai dapat berubah antar-eksekusi.",
                    size=8, color=MUTED, wraplength=270, justify="left").pack(anchor="w")
        self._bind_scroll(cards, scroller)
        self._label(distance_tab, "Jarak saat langkah ini", size=11, bold=True).pack(anchor="w", padx=12, pady=(14, 3))
        self._label(distance_tab, "∞ = belum ditemukan; Dari = pendahulu.", size=8, color=MUTED).pack(anchor="w", padx=12, pady=(0, 8))
        table_frame = tk.Frame(distance_tab, bg=WHITE)
        table_frame.pack(fill="both", expand=True, padx=6, pady=(0, 8))
        self.distance_table = ttk.Treeview(table_frame, columns=("vertex", "distance", "previous", "state"), show="headings", selectmode="browse")
        for key, title, width in (("vertex", "Simpul", 55), ("distance", "Jarak", 55), ("previous", "Dari", 48), ("state", "Status", 93)):
            self.distance_table.heading(key, text=title)
            self.distance_table.column(key, width=width, minwidth=40, anchor="center")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.distance_table.yview)
        self.distance_table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.distance_table.pack(fill="both", expand=True)
        self.distance_table.tag_configure("current", background="#fff1d9", foreground=INK)
        self.distance_table.tag_configure("settled", background=SOFT, foreground=TEAL)
        guide = tk.Text(guide_tab, wrap="word", font=("Segoe UI", 10), bg=WHITE, fg=INK, relief="flat", padx=14, pady=14, width=26)
        guide.pack(fill="both", expand=True)
        guide.insert("1.0", "Tiga contoh dari soal\n\nA · V1 → V15, bobot 505\nB · V1 → V10, bobot 400\nC · B → H, bobot 9\n\nEksplorasi\n\nPilih contoh, atau buka file graf sendiri. Ubah awal dan tujuan untuk mencoba rute lain.\n\nSeret simpul untuk merapikan graf. Seret latar untuk menggeser; roda mouse untuk zoom. Atur ulang mengembalikan posisi.\n\nDijkstra\n\nMemilih jarak terkecil lewat antrean prioritas. Cocok untuk bobot nonnegatif.\n\nBellman–Ford\n\nMemeriksa sisi secara berulang sampai jarak stabil. Nomor putaran muncul dalam animasi.\n\nKontrol keyboard\n\nSpasi: putar / jeda\n← / →: mundur / maju\nHome: ulangi\nEnd: hasil akhir\n\nPengukuran\n\nDetik dan mikrodetik adalah dua satuan dari pengukuran yang sama. Kecepatan animasi tidak mengubah runtime.")
        guide.configure(state="disabled")
        ttk.Button(side, text="Simpan hasil perbandingan…", command=self.export_results).grid(row=1, column=0, sticky="ew", pady=(9, 0))

    def _make_result_card(self, parent, name: str) -> None:
        card = tk.Frame(parent, bg=WHITE, padx=12, pady=11, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 10))
        self.card_frames[name] = card
        values = {key: tk.StringVar(value="—") for key in ("path", "cost", "time", "counts")}
        self.card_values[name] = values
        self._label(card, name, size=12, bold=True).pack(anchor="w")
        row = tk.Frame(card, bg=WHITE)
        row.pack(fill="x", pady=(6, 5))
        self._label(row, variable=values["cost"], size=25, bold=True, color=TEAL).pack(side="left")
        self._label(row, "BOBOT\nMINIMUM", size=8, color=MUTED, justify="left").pack(side="left", padx=10)
        route = self._label(card, variable=values["path"], size=10, anchor="w", justify="left", wraplength=245)
        route.pack(fill="x", pady=(1, 10))
        self._label(card, "WAKTU KOMPUTASI", size=8, color=MUTED, bold=True).pack(anchor="w")
        self._label(card, variable=values["time"], size=10, bold=True, color=TEAL).pack(anchor="w", pady=(3, 8))
        self._label(card, variable=values["counts"], size=8, color=MUTED, wraplength=245, justify="left").pack(anchor="w")
        card.bind("<Configure>", lambda e: route.configure(wraplength=max(170, e.width - 26)))

    def _bind_scroll(self, widget, canvas) -> None:
        def scroll(event):
            if canvas.bbox("all") and canvas.bbox("all")[3] > canvas.winfo_height():
                canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"
        widget.bind("<MouseWheel>", scroll)
        for child in widget.winfo_children():
            self._bind_scroll(child, canvas)

    @staticmethod
    def _shortcut(event, callback):
        if event.widget.winfo_class() in {"TCombobox", "Entry", "TEntry", "Text", "TScale", "TButton", "Treeview"}:
            return None
        callback()
        return "break"

    def _load_initial(self) -> None:
        self.startup_timer = None
        if self.default_file.exists():
            self.open_file(self.default_file, DEFAULT_SOURCE)
        else:
            self.open_file(example_path(EXAMPLES[0]), EXAMPLES[0].title)

    def _select_source(self, _event=None) -> None:
        label = self.source.get()
        if label in self.source_paths:
            self.open_file(self.source_paths[label], label)

    def choose_file(self) -> None:
        path = filedialog.askopenfilename(title="Buka file graf", filetypes=[("Graf teks", "*.txt"), ("Semua berkas", "*.*")])
        if path:
            self.open_file(Path(path))

    def open_file(self, path: Path, label: str | None = None) -> None:
        if self.startup_timer:
            self.after_cancel(self.startup_timer)
            self.startup_timer = None
        try:
            graph, start, goal = load_graph(path)
        except (OSError, UnicodeError, ValueError, OverflowError) as exc:
            messagebox.showerror("Graf tidak dapat dibuka", str(exc), parent=self)
            if self.source_path:
                self.source.set(next((name for name, value in self.source_paths.items() if value == self.source_path), self.source_path.name))
            return
        self._pause()
        self.graph, self.start, self.goal = graph, start, goal
        self.source_path = path.resolve()
        name = label or f"File · {path.name}"
        self.source_paths[name] = self.source_path
        self.source_selector.configure(values=list(self.source_paths))
        self.source.set(name)
        self.start_value.set(start)
        self.goal_value.set(goal)
        for selector in (self.start_selector, self.goal_selector):
            selector.configure(values=list(graph), state="readonly")
        edges = set()
        for vertex, neighbors in graph.items():
            for neighbor, weight in neighbors.items():
                edges.add(tuple(sorted((vertex, neighbor))) if graph[neighbor].get(vertex) == weight else (vertex, neighbor))
        self.source_info.set(f"{path.name}   ·   {len(graph)} simpul   ·   {len(edges)} sisi   ·   Bobot nonnegatif")
        self.canvas.set_graph(graph, start, goal)
        self.distance_table.delete(*self.distance_table.get_children())
        for vertex in graph:
            self.distance_table.insert("", "end", iid=vertex, values=(vertex, "∞", "—", "Belum"))
        self.calculate()

    def _change_endpoints(self, _event=None) -> None:
        if not self.graph:
            return
        self.start, self.goal = self.start_value.get(), self.goal_value.get()
        self.canvas.set_graph(self.graph, self.start, self.goal)
        self.calculate()

    def swap_endpoints(self) -> None:
        if self.graph:
            start, goal = self.start_value.get(), self.goal_value.get()
            self.start_value.set(goal)
            self.goal_value.set(start)
            self._change_endpoints()

    def calculate(self) -> None:
        if not self.graph:
            return
        self._pause()
        self.results = {DIJKSTRA: dijkstra(self.graph, self.start, self.goal), BELLMAN: bellman_ford(self.graph, self.start, self.goal)}
        self.route_label.set(f"{self.start}  →  {self.goal}")
        for name, result in self.results.items():
            values = self.card_values[name]
            values["cost"].set(number(result.cost) if result.path else "—")
            values["path"].set(" → ".join(result.path) if result.path else "Tujuan tidak terjangkau")
            values["time"].set(f"{result.runtime_ns / 1_000_000_000:.6f} s  ({result.runtime_ns / 1000:.1f} µs)")
            values["counts"].set(f"{sum(s.kind == 'inspect' for s in result.steps)} sisi diperiksa  ·  {sum(s.kind == 'relax' for s in result.steps)} pembaruan")
        first, second = self.results.values()
        self.compare_text.set(("✓ Kedua algoritma menghasilkan bobot yang sama." if first.path else "Kedua algoritma: tujuan tidak terjangkau.")
                              if first.cost == second.cost else "Hasil berbeda. Periksa graf dan implementasi.")
        self._select_algorithm()

    def _select_algorithm(self) -> None:
        self._pause()
        result = self.results.get(self.algorithm.get())
        if not result:
            return
        self.playback = Playback(self.graph, self.start, self.goal, result)
        for name, card in self.card_frames.items():
            card.configure(highlightbackground=TEAL if name == self.algorithm.get() else BORDER)
        self.seek_scale.configure(to=max(1, len(result.steps)))
        self._render(False)

    def _render(self, animate: bool = True) -> None:
        state = self.playback
        if not state:
            return
        self.step_title.set(state.title)
        self.step_detail.set(state.detail)
        self.progress_text.set(f"{state.index} / {len(state.result.steps)} langkah")
        self._syncing = True
        self.progress_value.set(state.index)
        self._syncing = False
        self.canvas.set_state(state.distances, state.visited, state.current, state.active_edge,
                              state.result.path if state.finished else [], animate=animate)
        for vertex in self.graph:
            status = "Diproses" if vertex == state.current else "Tetap" if vertex in state.visited else "Sementara" if math.isfinite(state.distances[vertex]) else "Belum"
            tag = "current" if vertex == state.current else "settled" if vertex in state.visited else ""
            self.distance_table.item(vertex, values=(vertex, number(state.distances[vertex]), state.previous.get(vertex, "—"), status), tags=(tag,))
        self.play_button.configure(text="Ⅱ  Jeda" if self.playing else "↻  Putar lagi" if state.finished else "▶  Putar")

    def reset_animation(self) -> None:
        self._pause()
        if self.playback:
            self.playback.reset()
            self._render(False)

    def toggle_play(self) -> None:
        if not self.playback:
            return
        if self.playing:
            self._pause()
            return
        if self.playback.finished:
            self.playback.reset()
        self.playing = True
        self._tick()

    def _pause(self) -> None:
        self.playing = False
        if self.timer:
            self.after_cancel(self.timer)
            self.timer = None
        if hasattr(self, "play_button"):
            self.play_button.configure(text="↻  Putar lagi" if self.playback and self.playback.finished else "▶  Putar")

    def _tick(self) -> None:
        self.timer = None
        if not self.playing or not self.playback:
            return
        self.playback.advance()
        if self.playback.finished:
            self._pause()
        self._render()
        if self.playing:
            self.timer = self.after(SPEEDS[self.speed.get()], self._tick)

    def _change_speed(self, _event=None) -> None:
        if self.playing and self.timer:
            self.after_cancel(self.timer)
            self.timer = self.after(SPEEDS[self.speed.get()], self._tick)

    def next_step(self) -> None:
        self._pause()
        if self.playback:
            self.playback.advance()
            self._render()

    def previous_step(self) -> None:
        self._pause()
        if self.playback:
            self.playback.seek(self.playback.index - 1)
            self._render(False)

    def show_final(self) -> None:
        self._pause()
        if self.playback:
            self.playback.seek(len(self.playback.result.steps))
            self._render()

    def _seek(self, value: str) -> None:
        if self._syncing or not self.playback:
            return
        self._pause()
        self.playback.seek(round(float(value)))
        self._render(False)

    def reset_view(self) -> None:
        self.canvas.reset_view()

    def _hover_vertex(self, vertex: str | None) -> None:
        if vertex is None or vertex not in self.graph:
            self.canvas_hint.set(CANVAS_HINT)
            return
        distance = self.playback.distances.get(vertex, math.inf) if self.playback else math.inf
        neighbors = ", ".join(f"{neighbor} ({number(weight)})" for neighbor, weight in self.graph[vertex].items())
        self.canvas_hint.set(f"{vertex} · jarak {number(distance)} · tetangga: {neighbors or 'tidak ada'}")

    def export_results(self) -> None:
        if not self.results:
            return
        path = filedialog.asksaveasfilename(parent=self, title="Simpan hasil perbandingan", defaultextension=".txt",
                                           initialfile="hasil_jalur.txt", filetypes=[("Berkas teks", "*.txt")])
        if path:
            try:
                Path(path).write_text(result_report(self.results, str(self.source_path), self.start, self.goal), encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("Hasil gagal disimpan", str(exc), parent=self)
                return
            messagebox.showinfo("Hasil tersimpan", f"Hasil kedua algoritma disimpan ke {Path(path).name}.", parent=self)

    def close(self) -> None:
        self._pause()
        if self.startup_timer:
            self.after_cancel(self.startup_timer)
        self.canvas.dispose()
        self.destroy()
