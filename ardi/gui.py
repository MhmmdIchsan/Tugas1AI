"""Enhanced Tkinter interface for comparing and animating shortest path searches."""

from __future__ import annotations

from collections import deque
import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from ardi.algorithms import Result, Step, bellman_ford, dijkstra
    from ardi.graph_io import Graph, load_graph
except (ImportError, ModuleNotFoundError):
    from algorithms import Result, Step, bellman_ford, dijkstra
    from graph_io import Graph, load_graph

# Warna
BG_MAIN = "#F8FAFC"       # Slate 50
CARD_BG = "#FFFFFF"       # White
CARD_BORDER = "#E2E8F0"   # Slate 200
TEXT_MAIN = "#0F172A"     # Slate 900
TEXT_MUTED = "#64748B"    # Slate 500
TEXT_SUBTLE = "#94A3B8"   # Slate 400

COLOR_START = "#10B981"   # Emerald 500
COLOR_START_BG = "#ECFDF5"# Emerald 50
COLOR_GOAL = "#EF4444"    # Red 500
COLOR_GOAL_BG = "#FEF2F2" # Red 50
COLOR_CURRENT = "#F59E0B" # Amber 500
COLOR_CURRENT_BG = "#FFFBEB" # Amber 50
COLOR_VISITED = "#3B82F6" # Blue 500
COLOR_VISITED_BG = "#EFF6FF" # Blue 50
COLOR_PATH = "#2563EB"    # Blue 600
COLOR_EDGE = "#CBD5E1"    # Slate 300
COLOR_GRID = "#F1F5F9"    # Slate 100


def format_number(value: float) -> str:
    if math.isinf(value):
        return "∞"
    return f"{value:g}"


class ShortestPathApp(tk.Tk):
    def __init__(self, default_file: Path | str) -> None:
        super().__init__()
        self.title("Visualisasi & Perbandingan Algoritma Pencarian Jalur Terpendek")
        self.geometry("1280x820")
        self.minsize(1020, 680)
        self.configure(bg=BG_MAIN)

        self.default_file = Path(default_file)
        self.graph: Graph = {}
        self.start = ""
        self.goal = ""
        self.results: dict[str, Result] = {}
        self.events: list[Step] = []
        self.step_index = 0
        self.visited: set[str] = set()
        self.current: str | None = None
        self.active_edge: tuple[str, str] | None = None
        self.current_distances: dict[str, float] = {}
        self.current_predecessors: dict[str, str] = {}
        self.finished = False
        self.playing = False
        self.timer: str | None = None

        # State Variables
        self.file_path_var = tk.StringVar(value="Belum ada file")
        self.file_info_var = tk.StringVar(value="Memuat...")
        self.algorithm = tk.StringVar(value="Dijkstra")
        self.speed = tk.IntVar(value=240)
        self.status = tk.StringVar(value="Siap. Pilih file graf untuk memulai.")
        self.progress_text = tk.StringVar(value="Langkah 0 / 0 (0%)")
        self.step_action_title = tk.StringVar(value="Menunggu Animasi")
        self.step_action_desc = tk.StringVar(value="Pilih algoritma lalu klik Putar atau Satu Langkah.")
        self.layout_mode = tk.StringVar(value="Alur Kiri ke Kanan (Hierarkis)")
        self.insight_text_var = tk.StringVar(value="")

        self._init_styles()
        self._build_ui()
        self._populate_presets()

        self.after(100, lambda: self.open_file(self.default_file) if self.default_file.exists() else None)

    def _init_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("aqua")
        except tk.TclError:
            pass

    def _build_ui(self) -> None:
        # Header Toolbar
        self._build_header()

        # Main Split Body
        main_paned = tk.PanedWindow(self, orient="horizontal", bg=BG_MAIN, sashwidth=6, borderwidth=0)
        main_paned.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # Left Column: Graph Visualizer
        graph_frame = tk.Frame(main_paned, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1)
        main_paned.add(graph_frame, minsize=560, stretch="always")
        self._build_graph_panel(graph_frame)

        # Right Column: Side Control & Results Panel
        side_frame = tk.Frame(main_paned, bg=CARD_BG, highlightbackground=CARD_BORDER, highlightthickness=1)
        main_paned.add(side_frame, minsize=460, stretch="never")
        self._build_side_panel(side_frame)

        # Bottom Global Status Bar
        self._build_footer()

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=BG_MAIN, padx=16, pady=12)
        header.pack(fill="x")

        # Title Block
        title_block = tk.Frame(header, bg=BG_MAIN)
        title_block.pack(side="left")

        title_label = tk.Label(
            title_block,
            text="Pencarian Jalur Terpendek",
            bg=BG_MAIN,
            fg=TEXT_MAIN,
            font=("Helvetica Neue", 18, "bold")
        )
        title_label.pack(anchor="w")

        subtitle_label = tk.Label(
            title_block,
            text="Perbandingan Komprehensif Algoritma Dijkstra vs Bellman–Ford",
            bg=BG_MAIN,
            fg=TEXT_MUTED,
            font=("Helvetica Neue", 10)
        )
        subtitle_label.pack(anchor="w")

        # Right Controls: Preset & File Selector
        top_controls = tk.Frame(header, bg=BG_MAIN)
        top_controls.pack(side="right", fill="y")

        preset_lbl = tk.Label(top_controls, text="Contoh Soal:", bg=BG_MAIN, fg=TEXT_MUTED, font=("Helvetica Neue", 9, "bold"))
        preset_lbl.pack(side="left", padx=(0, 6))

        self.preset_combo = ttk.Combobox(top_controls, state="readonly", width=26)
        self.preset_combo.pack(side="left", padx=(0, 8))
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)

        ttk.Button(top_controls, text="Buka File Lain...", command=self.choose_file).pack(side="left", padx=(0, 6))
        ttk.Button(top_controls, text="Hitung Ulang", command=self.calculate).pack(side="left")

    def _build_graph_panel(self, parent: tk.Frame) -> None:
        # Title bar for Graph
        top_bar = tk.Frame(parent, bg=CARD_BG, padx=14, pady=10)
        top_bar.pack(fill="x")

        tk.Label(
            top_bar,
            text="Visualisasi Graf",
            bg=CARD_BG,
            fg=TEXT_MAIN,
            font=("Helvetica Neue", 12, "bold")
        ).pack(side="left")

        # Layout Shape Selector
        layout_box = tk.Frame(top_bar, bg=CARD_BG)
        layout_box.pack(side="left", padx=(14, 0))
        tk.Label(layout_box, text="Bentuk:", bg=CARD_BG, fg=TEXT_MUTED, font=("Helvetica Neue", 9, "bold")).pack(side="left", padx=(0, 4))
        self.layout_combo = ttk.Combobox(
            layout_box,
            state="readonly",
            textvariable=self.layout_mode,
            values=("Alur Kiri ke Kanan (Hierarkis)", "Melingkar (Circular)", "Dua Jalur (Dual Track)"),
            width=23
        )
        self.layout_combo.pack(side="left")
        self.layout_combo.bind("<<ComboboxSelected>>", lambda _event: self.draw_graph())

        self.graph_info_label = tk.Label(
            top_bar,
            textvariable=self.file_info_var,
            bg="#F1F5F9",
            fg=TEXT_MUTED,
            font=("Helvetica Neue", 9, "bold"),
            padx=10,
            pady=3
        )
        self.graph_info_label.pack(side="right")

        # Graph Canvas
        self.canvas = tk.Canvas(parent, bg="#FCFDFD", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self.canvas.bind("<Configure>", lambda _event: self.draw_graph())

        # Legend Bar
        legend_frame = tk.Frame(parent, bg="#F8FAFC", padx=12, pady=7, highlightbackground=CARD_BORDER, highlightthickness=1)
        legend_frame.pack(fill="x", padx=10, pady=(0, 10))

        legends = [
            ("● Awal", COLOR_START),
            ("● Tujuan", COLOR_GOAL),
            ("● Sedang Diproses", COLOR_CURRENT),
            ("● Dikunjungi", COLOR_VISITED),
            ("━ Jalur Terpendek", COLOR_PATH),
        ]
        for text, color in legends:
            lbl = tk.Label(legend_frame, text=text, fg=color, bg="#F8FAFC", font=("Helvetica Neue", 9, "bold"))
            lbl.pack(side="left", padx=10)

    def _build_side_panel(self, parent: tk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab 1: Perbandingan Hasil
        self.tab_results = tk.Frame(notebook, bg=CARD_BG)
        notebook.add(self.tab_results, text="Hasil Perbandingan")
        self._build_results_tab(self.tab_results)

        # Tab 2: Simulasi & Penjelasan Langkah
        self.tab_sim = tk.Frame(notebook, bg=CARD_BG)
        notebook.add(self.tab_sim, text="Simulasi Langkah")
        self._build_simulation_tab(self.tab_sim)

    def _build_results_tab(self, parent: tk.Frame) -> None:
        # Comparison Header Card
        info_card = tk.Frame(parent, bg="#F8FAFC", padx=14, pady=10, highlightbackground=CARD_BORDER, highlightthickness=1)
        info_card.pack(fill="x", padx=12, pady=(12, 8))

        self.route_header_var = tk.StringVar(value="Awal: - ➔ Tujuan: -")
        tk.Label(
            info_card,
            textvariable=self.route_header_var,
            bg="#F8FAFC",
            fg=TEXT_MAIN,
            font=("Helvetica Neue", 11, "bold")
        ).pack(anchor="w")

        self.route_summary_var = tk.StringVar(value="Memuat data perbandingan...")
        tk.Label(
            info_card,
            textvariable=self.route_summary_var,
            bg="#F8FAFC",
            fg=TEXT_MUTED,
            font=("Helvetica Neue", 9),
            wraplength=410,
            justify="left"
        ).pack(anchor="w", pady=(3, 0))

        # Comparison Cards (Dijkstra vs Bellman-Ford)
        cards_container = tk.Frame(parent, bg=CARD_BG)
        cards_container.pack(fill="both", expand=True, padx=12, pady=4)

        # Dijkstra Card
        self.dijkstra_card = self._create_algo_card(
            cards_container,
            title="Dijkstra",
            badge_text="Priority Queue (Min-Heap)",
            badge_bg="#EFF6FF",
            badge_fg=COLOR_PATH
        )
        self.dijkstra_card["frame"].pack(fill="x", pady=(0, 8))

        # Bellman-Ford Card
        self.bellman_card = self._create_algo_card(
            cards_container,
            title="Bellman–Ford",
            badge_text="Iterative Edge Relaxation",
            badge_bg="#FEF3C7",
            badge_fg="#B45309"
        )
        self.bellman_card["frame"].pack(fill="x", pady=(0, 8))

        # Analytical Insight Card
        insight_frame = tk.Frame(parent, bg="#F0FDF4", padx=12, pady=8, highlightbackground="#BBF7D0", highlightthickness=1)
        insight_frame.pack(fill="x", padx=12, pady=(0, 12))

    def _create_algo_card(self, parent: tk.Frame, title: str, badge_text: str, badge_bg: str, badge_fg: str) -> dict:
        frame = tk.Frame(parent, bg=CARD_BG, padx=12, pady=10, highlightbackground=CARD_BORDER, highlightthickness=1)

        # Header of card
        card_header = tk.Frame(frame, bg=CARD_BG)
        card_header.pack(fill="x")

        tk.Label(
            card_header,
            text=title,
            bg=CARD_BG,
            fg=TEXT_MAIN,
            font=("Helvetica Neue", 11, "bold")
        ).pack(side="left")

        tk.Label(
            card_header,
            text=badge_text,
            bg=badge_bg,
            fg=badge_fg,
            font=("Helvetica Neue", 8, "bold"),
            padx=8,
            pady=2
        ).pack(side="right")

        # Metric values
        metrics_grid = tk.Frame(frame, bg=CARD_BG, pady=6)
        metrics_grid.pack(fill="x")

        # Row 1: Path
        tk.Label(metrics_grid, text="Rute:", bg=CARD_BG, fg=TEXT_MUTED, font=("Helvetica Neue", 9), width=8, anchor="w").grid(row=0, column=0, sticky="w")
        path_label = tk.Label(metrics_grid, text="-", bg=CARD_BG, fg=COLOR_PATH, font=("Menlo", 9, "bold"), anchor="w", wraplength=340, justify="left")
        path_label.grid(row=0, column=1, sticky="w")

        # Row 2: Total Cost
        tk.Label(metrics_grid, text="Bobot:", bg=CARD_BG, fg=TEXT_MUTED, font=("Helvetica Neue", 9), width=8, anchor="w").grid(row=1, column=0, sticky="w")
        cost_label = tk.Label(metrics_grid, text="-", bg=CARD_BG, fg=TEXT_MAIN, font=("Helvetica Neue", 9, "bold"), anchor="w")
        cost_label.grid(row=1, column=1, sticky="w")

        # Row 3: Runtime
        tk.Label(metrics_grid, text="Waktu:", bg=CARD_BG, fg=TEXT_MUTED, font=("Helvetica Neue", 9), width=8, anchor="w").grid(row=2, column=0, sticky="w")
        time_label = tk.Label(metrics_grid, text="-", bg=CARD_BG, fg=TEXT_MAIN, font=("Helvetica Neue", 9, "bold"), anchor="w")
        time_label.grid(row=2, column=1, sticky="w")

        # Row 4: Steps Count
        tk.Label(metrics_grid, text="Langkah:", bg=CARD_BG, fg=TEXT_MUTED, font=("Helvetica Neue", 9), width=8, anchor="w").grid(row=3, column=0, sticky="w")
        steps_label = tk.Label(metrics_grid, text="-", bg=CARD_BG, fg=TEXT_MUTED, font=("Helvetica Neue", 9), anchor="w")
        steps_label.grid(row=3, column=1, sticky="w")

        return {
            "frame": frame,
            "path": path_label,
            "cost": cost_label,
            "time": time_label,
            "steps": steps_label,
        }

    def _build_simulation_tab(self, parent: tk.Frame) -> None:
        # Selector & Controls Section
        ctrl_card = tk.Frame(parent, bg=CARD_BG, padx=12, pady=10)
        ctrl_card.pack(fill="x")

        # Algorithm Chooser Row
        algo_row = tk.Frame(ctrl_card, bg=CARD_BG)
        algo_row.pack(fill="x", pady=(0, 8))

        tk.Label(algo_row, text="Algoritma Aktif:", bg=CARD_BG, fg=TEXT_MAIN, font=("Helvetica Neue", 9, "bold")).pack(side="left")
        selector = ttk.Combobox(algo_row, state="readonly", textvariable=self.algorithm, values=("Dijkstra", "Bellman–Ford"), width=16)
        selector.pack(side="right")
        selector.bind("<<ComboboxSelected>>", lambda _event: self.reset_animation())

        # Playback Buttons Row (evenly distributed across 4 columns)
        btn_row = tk.Frame(ctrl_card, bg=CARD_BG)
        btn_row.pack(fill="x", pady=(0, 8))
        btn_row.columnconfigure((0, 1, 2, 3), weight=1)

        self.btn_reset = ttk.Button(btn_row, text="⏪ Awal", command=self.reset_animation)
        self.btn_reset.grid(row=0, column=0, sticky="ew", padx=2)

        self.play_button = ttk.Button(btn_row, text="▶ Putar", command=self.toggle_play)
        self.play_button.grid(row=0, column=1, sticky="ew", padx=2)

        self.btn_next = ttk.Button(btn_row, text="⏭ Langkah", command=self.next_step)
        self.btn_next.grid(row=0, column=2, sticky="ew", padx=2)

        self.btn_skip = ttk.Button(btn_row, text="⏩ Selesai", command=self.skip_to_end)
        self.btn_skip.grid(row=0, column=3, sticky="ew", padx=2)

        # Progress bar & Indicator
        self.progress_bar = ttk.Progressbar(ctrl_card, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill="x", pady=(4, 2))

        prog_label = tk.Label(ctrl_card, textvariable=self.progress_text, bg=CARD_BG, fg=TEXT_MUTED, font=("Helvetica Neue", 8))
        prog_label.pack(anchor="e")

        # Speed Slider
        speed_row = tk.Frame(ctrl_card, bg=CARD_BG)
        speed_row.pack(fill="x", pady=(6, 0))

        self.speed_label_var = tk.StringVar(value="Jeda: 240 ms / langkah")
        tk.Label(speed_row, textvariable=self.speed_label_var, bg=CARD_BG, fg=TEXT_MUTED, font=("Helvetica Neue", 8)).pack(side="left")
        speed_slider = ttk.Scale(speed_row, from_=50, to=800, variable=self.speed, command=self._on_speed_change)
        speed_slider.pack(side="right", fill="x", expand=True, padx=(8, 0))

        # Live Step Explanation Card (Key Educational Feature!)
        action_card = tk.Frame(parent, bg="#F8FAFC", padx=12, pady=10, highlightbackground=CARD_BORDER, highlightthickness=1)
        action_card.pack(fill="x", padx=12, pady=(6, 8))

        action_header = tk.Frame(action_card, bg="#F8FAFC")
        action_header.pack(fill="x")

        tk.Label(action_header, text="🔍 Detail Langkah Saat Ini:", bg="#F8FAFC", fg=TEXT_MAIN, font=("Helvetica Neue", 9, "bold")).pack(side="left")

        self.action_badge = tk.Label(
            action_header,
            textvariable=self.step_action_title,
            bg="#E2E8F0",
            fg=TEXT_MAIN,
            font=("Helvetica Neue", 8, "bold"),
            padx=7,
            pady=2
        )
        self.action_badge.pack(side="right")

        tk.Label(
            action_card,
            textvariable=self.step_action_desc,
            bg="#F8FAFC",
            fg=TEXT_MAIN,
            font=("Helvetica Neue", 9),
            wraplength=410,
            justify="left"
        ).pack(anchor="w", pady=(6, 0))

        # Live Distances Table (Shows current best known distances in a structured table)
        dist_frame = tk.Frame(parent, bg=CARD_BG, padx=12, pady=4)
        dist_frame.pack(fill="both", expand=True, pady=(0, 8))

        dist_header = tk.Frame(dist_frame, bg=CARD_BG)
        dist_header.pack(fill="x", pady=(0, 4))

        tk.Label(
            dist_header,
            text="Tabel Jarak Simpul Terkini (dist[v]):",
            bg=CARD_BG,
            fg=TEXT_MAIN,
            font=("Helvetica Neue", 9, "bold")
        ).pack(side="left")

        tk.Label(
            dist_header,
            text="Auto-scroll ke simpul aktif",
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=("Helvetica Neue", 8)
        ).pack(side="right")

        table_box = tk.Frame(dist_frame, bg=CARD_BG)
        table_box.pack(fill="both", expand=True)

        columns = ("node", "dist", "via", "status")
        self.dist_tree = ttk.Treeview(table_box, columns=columns, show="headings", height=7, selectmode="browse")

        self.dist_tree.heading("node", text="Simpul")
        self.dist_tree.heading("dist", text="Jarak d[v]")
        self.dist_tree.heading("via", text="Via π[v]")
        self.dist_tree.heading("status", text="Keterangan / Status")

        self.dist_tree.column("node", width=80, anchor="center")
        self.dist_tree.column("dist", width=80, anchor="center")
        self.dist_tree.column("via", width=65, anchor="center")
        self.dist_tree.column("status", width=160, anchor="w")

        # Treeview Tag Styles
        self.dist_tree.tag_configure("start", background="#ECFDF5", foreground="#065F46")
        self.dist_tree.tag_configure("goal", background="#FEF2F2", foreground="#991B1B")
        self.dist_tree.tag_configure("relaxed", background="#DCFCE7", foreground="#15803D")
        self.dist_tree.tag_configure("visited", background="#EFF6FF", foreground="#1E40AF")
        self.dist_tree.tag_configure("active", background="#FEF3C7", foreground="#B45309")
        self.dist_tree.tag_configure("path", background="#DBEAFE", foreground="#1D4ED8")
        self.dist_tree.tag_configure("default", background="#FFFFFF", foreground="#0F172A")

        dist_scroll = ttk.Scrollbar(table_box, orient="vertical", command=self.dist_tree.yview)
        self.dist_tree.configure(yscrollcommand=dist_scroll.set)

        self.dist_tree.pack(side="left", fill="both", expand=True)
        dist_scroll.pack(side="right", fill="y")

    def _build_footer(self) -> None:
        footer = tk.Frame(self, bg=BG_MAIN, padx=16, pady=6)
        footer.pack(fill="x", side="bottom")

        tk.Label(footer, textvariable=self.status, fg=TEXT_MUTED, bg=BG_MAIN, font=("Helvetica Neue", 9), anchor="w").pack(side="left", fill="x", expand=True)
        tk.Label(footer, text="Tugas 1 Kecerdasan Artifisial", fg=TEXT_SUBTLE, bg=BG_MAIN, font=("Helvetica Neue", 9)).pack(side="right")

    def _populate_presets(self) -> None:
        folder = Path(__file__).parent
        presets = []
        if (folder / "graf.txt").exists():
            presets.append("graf.txt (Contoh 1: V1 → V15)")
        if (folder / "contoh_V1_V10.txt").exists():
            presets.append("contoh_V1_V10.txt (Contoh 2: V1 → V10)")
        if (folder / "contoh_B_H.txt").exists():
            presets.append("contoh_B_H.txt (Contoh 3: B → H)")

        self.preset_combo["values"] = presets
        if presets:
            self.preset_combo.current(0)

    def _on_preset_selected(self, _event=None) -> None:
        val = self.preset_combo.get()
        folder = Path(__file__).parent
        filename = val.split(" ")[0]
        target_file = folder / filename
        if target_file.exists():
            self.open_file(target_file)

    def _on_speed_change(self, val) -> None:
        ms = int(float(val))
        self.speed_label_var.set(f"Jeda: {ms} ms / langkah")

    def choose_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Pilih Berkas Graf",
            filetypes=[("Berkas Teks", "*.txt"), ("Semua Berkas", "*.*")]
        )
        if path:
            self.open_file(Path(path))

    def open_file(self, path: Path) -> None:
        try:
            graph, start, goal = load_graph(path)
        except (OSError, UnicodeError, ValueError) as exc:
            messagebox.showerror("Gagal Membuka Graf", str(exc))
            self.status.set(f"Gagal membaca graf: {exc}")
            return
        self._pause()
        self.graph, self.start, self.goal = graph, start, goal
        self.file_path_var.set(path.name)

        num_edges = sum(len(neighbors) for neighbors in graph.values())
        self.file_info_var.set(f"{path.name}  |  {len(graph)} Simpul  |  {num_edges} Sisi  |  {start} ➔ {goal}")

        self.results.clear()
        self.reset_animation()
        self.calculate()

    def calculate(self) -> None:
        if not self.graph:
            messagebox.showinfo("Belum Ada Graf", "Buka file graf.txt terlebih dahulu.")
            return
        self._pause()
        self.results = {
            "Dijkstra": dijkstra(self.graph, self.start, self.goal),
            "Bellman–Ford": bellman_ford(self.graph, self.start, self.goal),
        }
        self._update_results_display()
        self.reset_animation()
        self.status.set("Perhitungan selesai. Animasi dan perbandingan siap ditinjau.")

    def _update_results_display(self) -> None:
        if not self.results:
            return

        res_dijkstra = self.results.get("Dijkstra")
        res_bellman = self.results.get("Bellman–Ford")

        self.route_header_var.set(f"Pencarian Jalur dari Simpul [{self.start}] ke [{self.goal}]")

        # Update Dijkstra Card
        if res_dijkstra:
            d_route = " ➔ ".join(res_dijkstra.path) if res_dijkstra.path else "Tidak ada jalur"
            self.dijkstra_card["path"].configure(text=d_route)
            self.dijkstra_card["cost"].configure(text=format_number(res_dijkstra.cost))
            self.dijkstra_card["time"].configure(text=f"{res_dijkstra.runtime_ns / 1000:.2f} µs ({res_dijkstra.runtime_ns:,} ns)")
            self.dijkstra_card["steps"].configure(text=f"{len(res_dijkstra.steps)} operasi langkah")

        # Update Bellman-Ford Card
        if res_bellman:
            b_route = " ➔ ".join(res_bellman.path) if res_bellman.path else "Tidak ada jalur"
            self.bellman_card["path"].configure(text=b_route)
            self.bellman_card["cost"].configure(text=format_number(res_bellman.cost))
            self.bellman_card["time"].configure(text=f"{res_bellman.runtime_ns / 1000:.2f} µs ({res_bellman.runtime_ns:,} ns)")
            self.bellman_card["steps"].configure(text=f"{len(res_bellman.steps)} operasi langkah")

        # Comparative Summary & Insights
        if res_dijkstra and res_bellman:
            same_cost = math.isclose(res_dijkstra.cost, res_bellman.cost, rel_tol=1e-9)
            same_path = res_dijkstra.path == res_bellman.path

            if math.isinf(res_dijkstra.cost):
                self.route_summary_var.set("Simpul tujuan tidak dapat dijangkau dari simpul awal.")
                self.insight_text_var.set("Kedua algoritma mengonfirmasi bahwa tidak ada rute yang menghubungkan simpul awal ke tujuan.")
            else:
                match_text = "Rute dan total bobot identik." if same_path else "Bobot minimum identik (rute ekuivalen)."
                self.route_summary_var.set(f"Bobot Optimal: {format_number(res_dijkstra.cost)}. {match_text}")

                fastest = "Dijkstra" if res_dijkstra.runtime_ns < res_bellman.runtime_ns else "Bellman–Ford"
                ratio = max(res_dijkstra.runtime_ns, res_bellman.runtime_ns) / max(1, min(res_dijkstra.runtime_ns, res_bellman.runtime_ns))

                self.insight_text_var.set(
                    f"Dijkstra membutuhkan {len(res_dijkstra.steps)} langkah, sedangkan Bellman–Ford membutuhkan {len(res_bellman.steps)} langkah. "
                    f"Dijkstra lebih cepat ({ratio:.1f}x) karena langsung memilih simpul berjarak terkecil melalui Priority Queue, "
                    f"sedangkan Bellman–Ford merelaksasi seluruh sisi pada setiap iterasi."
                )

    def reset_animation(self) -> None:
        self._pause()
        result = self.results.get(self.algorithm.get())
        self.events = result.steps if result else []
        self.step_index = 0
        self.visited.clear()
        self.current = None
        self.active_edge = None
        self.finished = False

        # Reset Live Distance Map
        self.current_distances = {v: math.inf for v in self.graph}
        if self.start and self.start in self.current_distances:
            self.current_distances[self.start] = 0
        self.current_predecessors = {}

        if hasattr(self, "dist_tree"):
            self.dist_tree.delete(*self.dist_tree.get_children())

        self.progress_bar["maximum"] = max(1, len(self.events))
        self.progress_bar["value"] = 0
        self.progress_text.set(f"Langkah 0 / {len(self.events)} (0%)")

        self.step_action_title.set("Awal Simulasi")
        self.step_action_desc.set(f"Simpul awal {self.start} ditetapkan dengan jarak awal 0. Klik 'Putar' atau 'Langkah'.")
        self.action_badge.configure(bg="#E2E8F0", fg=TEXT_MAIN)

        self._update_distance_table()
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
        self.play_button.configure(text="⏸ Jeda")
        self._play_tick()

    def _pause(self) -> None:
        self.playing = False
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        if hasattr(self, "play_button"):
            self.play_button.configure(text="▶ Putar")

    def _play_tick(self) -> None:
        if not self.playing:
            return
        self.next_step()
        if self.playing and self.step_index < len(self.events):
            interval = max(40, int(self.speed.get()))
            self.timer = self.after(interval, self._play_tick)
        else:
            self._pause()

    def skip_to_end(self) -> None:
        self._pause()
        if not self.events:
            return
        while self.step_index < len(self.events) and not self.finished:
            self._apply_step(self.events[self.step_index])
            self.step_index += 1

        pct = int((self.step_index / max(1, len(self.events))) * 100)
        self.progress_bar["value"] = self.step_index
        self.progress_text.set(f"Langkah {self.step_index} / {len(self.events)} ({pct}%)")
        self._update_distance_table()
        self.draw_graph()

    def next_step(self) -> None:
        if self.step_index >= len(self.events):
            self._pause()
            return

        step = self.events[self.step_index]
        self.step_index += 1
        self._apply_step(step)

        pct = int((self.step_index / max(1, len(self.events))) * 100)
        self.progress_bar["value"] = self.step_index
        self.progress_text.set(f"Langkah {self.step_index} / {len(self.events)} ({pct}%)")
        self._update_distance_table()
        self.draw_graph()

    def _apply_step(self, step: Step) -> None:
        self.active_edge = None

        if step.kind == "pass":
            self.step_action_title.set(f"Iterasi #{step.iteration}")
            self.action_badge.configure(bg="#FEF3C7", fg="#B45309")
            self.step_action_desc.set(f"Bellman–Ford memulai iterasi ke-{step.iteration} untuk mengevaluasi seluruh relaksasi sisi.")
            self.status.set(f"Bellman–Ford: Iterasi {step.iteration} sedang berlangsung...")

        elif step.kind == "visit":
            self.current = step.node
            if step.node:
                self.visited.add(step.node)
                if step.distance is not None:
                    self.current_distances[step.node] = step.distance
            self.step_action_title.set(f"Kunjungi: {step.node}")
            self.action_badge.configure(bg="#DBEAFE", fg=COLOR_PATH)
            self.step_action_desc.set(f"Dijkstra menetapkan simpul {step.node} sebagai permanen dengan jarak terpendek {format_number(step.distance or 0)}.")
            self.status.set(f"Dijkstra: Menetapkan {step.node} (jarak: {format_number(step.distance or 0)}).")

        elif step.kind == "inspect":
            self.current = step.node
            self.active_edge = (step.node or "", step.neighbor or "")
            self.step_action_title.set("Memeriksa Sisi")
            self.action_badge.configure(bg="#F1F5F9", fg=TEXT_MAIN)
            self.step_action_desc.set(f"Mengecek sisi {step.node} ➔ {step.neighbor} untuk melihat apakah jarak dapat diperpendek.")
            self.status.set(f"Periksa sisi: {step.node} ➔ {step.neighbor}.")

        elif step.kind == "relax":
            self.current = step.node
            self.active_edge = (step.node or "", step.neighbor or "")
            if step.neighbor and step.distance is not None:
                old_d = self.current_distances.get(step.neighbor, math.inf)
                self.current_distances[step.neighbor] = step.distance
                self.current_predecessors[step.neighbor] = step.node or ""
                self.step_action_title.set(f"Relaksasi: {step.neighbor}")
                self.action_badge.configure(bg="#DCFCE7", fg="#15803D")
                self.step_action_desc.set(
                    f"Jarak ke {step.neighbor} berhasil diperbarui dari {format_number(old_d)} menjadi {format_number(step.distance)} melalui {step.node}."
                )
                self.status.set(f"Perbarui jarak {step.neighbor} ➔ {format_number(step.distance)}.")

        elif step.kind == "done":
            self.finished = True
            result = self.results[self.algorithm.get()]
            self.step_action_title.set("Selesai")
            self.action_badge.configure(bg="#DCFCE7", fg="#15803D")
            if result.path:
                route_str = " ➔ ".join(result.path)
                self.step_action_desc.set(f"🎉 Rute terpendek berhasil ditemukan: {route_str} (Total Bobot: {format_number(result.cost)}).")
                self.status.set(f"Selesai: {route_str}")
            else:
                self.step_action_desc.set("Tujuan tidak dapat dijangkau dari simpul awal.")
                self.status.set("Selesai: Simpul tujuan tak terjangkau.")

    def _update_distance_table(self) -> None:
        if not hasattr(self, "dist_tree") or not self.graph:
            return

        result = self.results.get(self.algorithm.get())
        route_nodes = set(result.path) if (self.finished and result) else set()

        for vertex in self.graph:
            dist_val = self.current_distances.get(vertex, math.inf)
            dist_str = format_number(dist_val)
            via_val = self.current_predecessors.get(vertex, "-")

            # Determine label and role
            role = ""
            if vertex == self.start:
                role = " (Awal)"
            elif vertex == self.goal:
                role = " (Tujuan)"
            label = f"{vertex}{role}"

            # Determine status and color tag
            if vertex in route_nodes and self.finished:
                status_text = "🔷 Rute Terpendek"
                tag = "path"
            elif vertex == self.current and not self.finished:
                status_text = "🟠 Sedang Diproses"
                tag = "active"
            elif vertex == self.start:
                status_text = "🟢 Simpul Awal (0)"
                tag = "start"
            elif vertex in self.visited:
                status_text = "🔵 Tetap (Permanen)"
                tag = "visited"
            elif math.isfinite(dist_val):
                status_text = "⚡ Terjangkau (Aktif)"
                tag = "relaxed"
            else:
                status_text = "⚪ Belum Terjangkau (∞)"
                tag = "default"

            row_values = (label, dist_str, via_val, status_text)

            if self.dist_tree.exists(vertex):
                self.dist_tree.item(vertex, values=row_values, tags=(tag,))
            else:
                self.dist_tree.insert("", "end", iid=vertex, values=row_values, tags=(tag,))

        # Auto-scroll to current active or updated vertex
        target_focus = self.current or (self.start if not self.finished else self.goal)
        if target_focus and self.dist_tree.exists(target_focus):
            self.dist_tree.see(target_focus)

    def draw_graph(self) -> None:
        if not hasattr(self, "canvas"):
            return
        canvas = self.canvas
        canvas.delete("all")

        if not self.graph:
            canvas.create_text(
                max(canvas.winfo_width() // 2, 250),
                max(canvas.winfo_height() // 2, 250),
                text="Buka file graf untuk menampilkan visualisasi",
                fill=TEXT_MUTED,
                font=("Helvetica Neue", 12)
            )
            return

    def _get_node_positions(self, width: float, height: float) -> dict[str, tuple[float, float]]:
        layout_type = self.layout_mode.get() if hasattr(self, "layout_mode") else "Hierarkis"
        vertices = list(self.graph.keys())
        num_v = len(vertices)
        if num_v == 0:
            return {}

        padding_x = 75
        padding_y = 65

        if "Melingkar" in layout_type:
            radius = min((width - 2 * padding_x) / 2, (height - 2 * padding_y) / 2)
            cx, cy = width / 2, height / 2
            return {
                vertex: (
                    cx + radius * math.cos(-math.pi / 2 + 2 * math.pi * index / num_v),
                    cy + radius * math.sin(-math.pi / 2 + 2 * math.pi * index / num_v)
                )
                for index, vertex in enumerate(vertices)
            }

        elif "Dua Jalur" in layout_type:
            # Dual Track (Upper & Lower tracks between Start and Goal)
            others = [v for v in vertices if v != self.start and v != self.goal]
            half = math.ceil(len(others) / 2)
            top_track = others[:half]
            bottom_track = others[half:]

            positions: dict[str, tuple[float, float]] = {}
            cy = height / 2
            positions[self.start] = (padding_x, cy)
            positions[self.goal] = (width - padding_x, cy)

            x_step_top = (width - 2 * padding_x) / max(1, len(top_track) + 1)
            for idx, node in enumerate(top_track):
                positions[node] = (padding_x + (idx + 1) * x_step_top, cy - height * 0.26)

            x_step_bot = (width - 2 * padding_x) / max(1, len(bottom_track) + 1)
            for idx, node in enumerate(bottom_track):
                positions[node] = (padding_x + (idx + 1) * x_step_bot, cy + height * 0.26)

            return positions

        else:
            # Default: Alur Kiri ke Kanan (Hierarchical BFS Layers from Start node)
            layers: dict[int, list[str]] = {}
            visited: set[str] = {self.start} if self.start else set()
            queue = deque([(self.start, 0)]) if self.start else deque()

            while queue:
                u, d = queue.popleft()
                layers.setdefault(d, []).append(u)
                for v in self.graph.get(u, {}):
                    if v not in visited:
                        visited.add(v)
                        queue.append((v, d + 1))

            for u in vertices:
                if u not in visited:
                    max_d = max(layers.keys(), default=0) + 1
                    layers.setdefault(max_d, []).append(u)
                    visited.add(u)

            if not layers:
                layers[0] = vertices

            # Move goal to dedicated final column if sharing column with other nodes
            max_l = max(layers.keys(), default=0)
            if self.goal and self.goal in layers.get(max_l, []) and len(layers.get(max_l, [])) > 1:
                layers[max_l].remove(self.goal)
                layers[max_l + 1] = [self.goal]

            sorted_keys = sorted(layers.keys())
            usable_w = max(100, width - 2 * padding_x)
            usable_h = max(100, height - 2 * padding_y)
            x_step = usable_w / max(1, len(sorted_keys) - 1)

            positions: dict[str, tuple[float, float]] = {}
            for col_idx, k in enumerate(sorted_keys):
                nodes_in_col = layers[k]
                x = padding_x + col_idx * x_step
                y_step = usable_h / (len(nodes_in_col) + 1)
                for row_idx, node in enumerate(nodes_in_col):
                    y = padding_y + (row_idx + 1) * y_step
                    positions[node] = (x, y)

            return positions

    def draw_graph(self) -> None:
        if not hasattr(self, "canvas"):
            return
        canvas = self.canvas
        canvas.delete("all")

        if not self.graph:
            canvas.create_text(
                max(canvas.winfo_width() // 2, 250),
                max(canvas.winfo_height() // 2, 250),
                text="Buka file graf untuk menampilkan visualisasi",
                fill=TEXT_MUTED,
                font=("Helvetica Neue", 12)
            )
            return

        width = max(canvas.winfo_width(), 520)
        height = max(canvas.winfo_height(), 420)

        # Draw subtle modern background dots grid
        grid_step = 32
        for x in range(0, width, grid_step):
            for y in range(0, height, grid_step):
                canvas.create_rectangle(x, y, x + 1.5, y + 1.5, fill=COLOR_GRID, outline="")

        positions = self._get_node_positions(width, height)

        result = self.results.get(self.algorithm.get())
        route_edges = set(zip(result.path, result.path[1:])) if (self.finished and result) else set()
        drawn_edges: set[tuple[str, str]] = set()

        # Pass 1: Draw regular edges
        for vertex, neighbors in self.graph.items():
            for neighbor, weight in neighbors.items():
                is_reciprocal = self.graph.get(neighbor, {}).get(vertex) == weight
                key = tuple(sorted((vertex, neighbor))) if is_reciprocal else (vertex, neighbor)

                if key in drawn_edges:
                    continue
                drawn_edges.add(key)

                x1, y1 = positions[vertex]
                x2, y2 = positions[neighbor]

                is_in_route = (vertex, neighbor) in route_edges or (is_reciprocal and (neighbor, vertex) in route_edges)
                is_active = (self.active_edge == (vertex, neighbor)) or (is_reciprocal and self.active_edge == (neighbor, vertex))

                if is_in_route:
                    color = COLOR_PATH
                    thickness = 4.5
                elif is_active:
                    color = COLOR_CURRENT
                    thickness = 3.5
                else:
                    color = COLOR_EDGE
                    thickness = 1.8

                # Self-loop handling
                if vertex == neighbor:
                    canvas.create_arc(
                        x1 - 28, y1 - 44, x1 + 28, y1 + 4,
                        start=25, extent=290, style="arc", outline=color, width=thickness
                    )
                    continue

                dist_v = math.hypot(x2 - x1, y2 - y1)
                ux, uy = (x2 - x1) / dist_v, (y2 - y1) / dist_v
                start_x, start_y = x1 + ux * 24, y1 + uy * 24
                end_x, end_y = x2 - ux * 24, y2 - uy * 24

                # Draw the edge line
                arrow_mode = "none" if is_reciprocal else "last"
                canvas.create_line(
                    start_x, start_y, end_x, end_y,
                    fill=color,
                    width=thickness,
                    arrow=arrow_mode,
                    arrowshape=(10, 12, 4) if not is_reciprocal else None
                )

                # Weight badge
                mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
                badge_bg = "#FFFFFF" if not is_in_route else "#EFF6FF"
                badge_border = COLOR_PATH if is_in_route else COLOR_CURRENT if is_active else CARD_BORDER
                badge_text_color = COLOR_PATH if is_in_route else COLOR_CURRENT if is_active else TEXT_MUTED

                canvas.create_rectangle(
                    mid_x - 14, mid_y - 9, mid_x + 14, mid_y + 9,
                    fill=badge_bg, outline=badge_border, width=1.2
                )
                canvas.create_text(
                    mid_x, mid_y,
                    text=format_number(weight),
                    fill=badge_text_color,
                    font=("Helvetica Neue", 8, "bold")
                )

        # Pass 2: Draw Vertices (Nodes)
        route_nodes = set(result.path) if (self.finished and result) else set()

        for vertex, (x, y) in positions.items():
            node_r = 21

            fill_color = "#FFFFFF"
            border_color = CARD_BORDER
            border_width = 2
            text_color = TEXT_MAIN

            if vertex in self.visited:
                fill_color = COLOR_VISITED_BG
                border_color = COLOR_VISITED

            if vertex in route_nodes:
                fill_color = "#DBEAFE"
                border_color = COLOR_PATH
                border_width = 3

            if vertex == self.start:
                fill_color = COLOR_START_BG
                border_color = COLOR_START
                border_width = 3.5

            if vertex == self.goal:
                fill_color = COLOR_GOAL_BG
                border_color = COLOR_GOAL
                border_width = 3.5

            if vertex == self.current and not self.finished:
                fill_color = COLOR_CURRENT_BG
                border_color = COLOR_CURRENT
                border_width = 3.5

            # Glow / Ring for Start and Goal
            if vertex == self.start or vertex == self.goal:
                glow_color = "#A7F3D0" if vertex == self.start else "#FECACA"
                canvas.create_oval(
                    x - (node_r + 5), y - (node_r + 5),
                    x + (node_r + 5), y + (node_r + 5),
                    fill="", outline=glow_color, width=2
                )

            # Node Circle
            canvas.create_oval(
                x - node_r, y - node_r,
                x + node_r, y + node_r,
                fill=fill_color, outline=border_color, width=border_width
            )

            # Node Text
            canvas.create_text(
                x, y,
                text=vertex,
                fill=text_color,
                font=("Helvetica Neue", 9, "bold")
            )

            # Badges above Start / Goal nodes
            if vertex == self.start:
                canvas.create_rectangle(
                    x - 22, y - node_r - 18, x + 22, y - node_r - 6,
                    fill=COLOR_START, outline=""
                )
                canvas.create_text(
                    x, y - node_r - 12,
                    text="AWAL",
                    fill="white",
                    font=("Helvetica Neue", 7, "bold")
                )
            elif vertex == self.goal:
                canvas.create_rectangle(
                    x - 25, y - node_r - 18, x + 25, y - node_r - 6,
                    fill=COLOR_GOAL, outline=""
                )
                canvas.create_text(
                    x, y - node_r - 12,
                    text="TUJUAN",
                    fill="white",
                    font=("Helvetica Neue", 7, "bold")
                )


if __name__ == "__main__":
    ShortestPathApp(Path(__file__).with_name("graf.txt")).mainloop()
