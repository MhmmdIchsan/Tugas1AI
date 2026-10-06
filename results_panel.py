"""Right panel adapted from Ardi: result cards and live distance table."""
from __future__ import annotations
import math
import tkinter as tk
from tkinter import ttk
from playback import number as format_number

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


class ResultsPanel(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=CARD_BG)
        self.app = app
        self.insight_text_var = tk.StringVar(self)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True)
        result_tab = tk.Frame(self.notebook, bg=CARD_BG)
        simulation_tab = tk.Frame(self.notebook, bg=CARD_BG)
        self.notebook.add(result_tab, text='Hasil Perbandingan')
        self.notebook.add(simulation_tab, text='Simulasi Langkah')
        self.notebook.select(simulation_tab)
        scroller = tk.Canvas(result_tab, bg=CARD_BG, highlightthickness=0, width=410)
        scrollbar = ttk.Scrollbar(result_tab, command=scroller.yview)
        scrollbar.pack(side='right', fill='y')
        scroller.pack(side='left', fill='both', expand=True)
        scroller.configure(yscrollcommand=scrollbar.set)
        content = tk.Frame(scroller, bg=CARD_BG)
        window = scroller.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda e: scroller.configure(scrollregion=scroller.bbox('all')))
        scroller.bind('<Configure>', lambda e: scroller.itemconfigure(window, width=e.width))
        self._build_results_tab(content)
        self._build_simulation_tab(simulation_tab)
        self.export_button = ttk.Button(self, text='Simpan hasil perbandingan…', command=app.export_results)
        self.export_button.pack(side='bottom', fill='x', pady=(9, 0), before=self.notebook)

    def clear(self):
        self.route_header_var.set('Menghitung kedua algoritma…')
        self.route_summary_var.set('Hasil baru akan tampil setelah perhitungan selesai.')
        self.insight_text_var.set('')
        for card in (self.dijkstra_card, self.bellman_card):
            for key in ('path', 'cost', 'time', 'steps'):
                card[key].configure(text='—')

    def show_results(self, comparison, start, goal):
        self.route_header_var.set(f'Pencarian jalur [{start}] → [{goal}]')
        cards = (self.dijkstra_card, self.bellman_card)
        for card, result in zip(cards, comparison.results):
            timing = comparison.timings[result.name]
            card['path'].configure(text=' → '.join(result.path) or 'Tidak ada jalur')
            card['cost'].configure(text=format_number(result.cost))
            card['time'].configure(text=f'{timing.median_us:.3f} µs (median 31 uji)')
            card['steps'].configure(text=f'{len(result.steps)} rekaman · {result.metrics.inspected_edges} sisi diperiksa')
        first, second = comparison.results
        if not comparison.consistent:
            summary = 'Hasil kedua algoritma berbeda. Periksa input dan implementasi.'
        elif not first.path:
            summary = 'Kedua algoritma: tujuan tidak dapat dijangkau.'
        else:
            summary = f'Bobot optimal: {format_number(first.cost)}. ' + ('Rute dan bobot identik.' if first.path == second.path else 'Bobot sama; rute ekuivalen.')
        self.route_summary_var.set(summary)
        self.summary.set(summary)
        faster = min(comparison.timings, key=lambda name: comparison.timings[name].median_us)
        low = comparison.timings[faster].median_us
        high = max(t.median_us for t in comparison.timings.values())
        self.insight_text_var.set(f'Pada pengukuran ini {faster} memiliki median lebih rendah' +
            (f' ({high/low:.2f}×).' if low else '.') +
            ' Runtime tidak mencakup animasi atau pencatatan langkah. Hasil dapat berubah antar-eksekusi.')

    def render(self, state):
        result = state.result
        self.action_title.set(state.title)
        self.action_detail.set(state.detail)
        self.algorithm_label.set(result.name)
        self.progress_text.set(f'Langkah {state.index} / {len(result.steps)}')
        self.progress_bar.configure(maximum=max(1, len(result.steps)), value=state.index)
        route_nodes = set(result.path) if state.finished else set()
        for vertex in state.graph:
            distance = state.distances[vertex]
            role = ' (Awal/Tujuan)' if vertex == state.start == state.goal else ' (Awal)' if vertex == state.start else ' (Tujuan)' if vertex == state.goal else ''
            if vertex in route_nodes:
                status, tag = 'Rute Terpendek', 'path'
            elif vertex == state.updated:
                status, tag = 'Jarak Diperbarui', 'relaxed'
            elif vertex == state.current and not state.finished:
                status, tag = 'Sedang Diproses', 'active'
            elif vertex in state.visited:
                status, tag = 'Tetap (Permanen)', 'visited'
            elif state.finished and result.name == 'Bellman–Ford' and not result.trace_truncated and distance != math.inf:
                status, tag = 'Tetap (Permanen)', 'visited'
            elif vertex == state.start:
                status, tag = 'Simpul Awal (0)', 'start'
            elif distance != math.inf:
                status, tag = 'Jarak Sementara', 'relaxed'
            else:
                status, tag = 'Belum Terjangkau (∞)', 'default'
            values = (vertex+role, format_number(distance), state.previous.get(vertex, '—'), status)
            if self.dist_tree.exists(vertex):
                self.dist_tree.item(vertex, values=values, tags=(tag,))
            else:
                self.dist_tree.insert('', 'end', iid=vertex, values=values, tags=(tag,))
        target = state.updated or state.current or (state.goal if state.finished else state.start)
        if self.dist_tree.exists(target):
            self.dist_tree.see(target)

    def _build_simulation_tab(self, parent):
        header = tk.Frame(parent, bg=CARD_BG, padx=12, pady=12)
        header.pack(fill='x')
        self.algorithm_label = tk.StringVar(self, value='Dijkstra')
        tk.Label(header, textvariable=self.algorithm_label, bg=CARD_BG, fg=TEXT_MAIN,
                 font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        self.summary = tk.StringVar(self, value='Menunggu hasil perhitungan.')
        summary = tk.Label(header, textvariable=self.summary, bg=CARD_BG, fg=TEXT_MUTED,
                           font=('Segoe UI', 9), justify='left', anchor='w')
        summary.pack(fill='x', pady=(4, 0))
        header.bind('<Configure>', lambda e: summary.configure(wraplength=max(180, e.width-28)))
        self.progress_text = tk.StringVar(self, value='0 / 0 langkah')
        self.progress_bar = ttk.Progressbar(header)
        self.progress_bar.pack(fill='x', pady=(10, 2))
        tk.Label(header, textvariable=self.progress_text, bg=CARD_BG, fg=TEXT_MUTED,
                 font=('Segoe UI', 9)).pack(anchor='e')
        action = tk.Frame(parent, bg='#F8FAFC', padx=12, pady=12,
                          highlightbackground=CARD_BORDER, highlightthickness=1)
        action.pack(fill='x', padx=12, pady=(0, 10))
        tk.Label(action, text='DETAIL LANGKAH SAAT INI', bg='#F8FAFC', fg=TEXT_MUTED,
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w')
        self.action_title = tk.StringVar(self, value='Siap menjelajahi graf')
        self.action_detail = tk.StringVar(self, value='Pilih algoritma lalu putar animasi.')
        title = tk.Label(action, textvariable=self.action_title, bg='#F8FAFC', fg=TEXT_MAIN,
                        font=('Segoe UI', 11, 'bold'), anchor='w', justify='left')
        title.pack(fill='x', pady=(5, 4))
        detail = tk.Label(action, textvariable=self.action_detail, bg='#F8FAFC', fg=TEXT_MAIN,
                          font=('Segoe UI', 9), anchor='w', justify='left')
        detail.pack(fill='x')
        action.bind('<Configure>', lambda e: [w.configure(wraplength=max(180, e.width-26)) for w in (title, detail)])
        # Live Distances Table (Shows current best known distances in a structured table)
        dist_frame = tk.Frame(parent, bg=CARD_BG, padx=12, pady=4)
        dist_frame.pack(fill="both", expand=True, pady=(0, 8))

        dist_header = tk.Frame(dist_frame, bg=CARD_BG)
        dist_header.pack(fill="x", pady=(0, 4))

        tk.Label(
            dist_header,
            text="Jarak simpul terkini · dist[v]",
            bg=CARD_BG,
            fg=TEXT_MAIN,
            font=("Segoe UI", 9, "bold")
        ).pack(side="left")

        tk.Label(
            dist_header,
            text="Mengikuti simpul aktif",
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 8)
        ).pack(side="right")

        table_box = tk.Frame(dist_frame, bg=CARD_BG)
        table_box.pack(fill="both", expand=True)

        columns = ("node", "dist", "via", "status")
        self.dist_tree = ttk.Treeview(table_box, columns=columns, show="headings", height=7, selectmode="browse")

        self.dist_tree.heading("node", text="Simpul")
        self.dist_tree.heading("dist", text="Jarak d[v]")
        self.dist_tree.heading("via", text="Via π[v]")
        self.dist_tree.heading("status", text="Keterangan / Status")

        self.dist_tree.column("node", width=98, minwidth=65, anchor="center")
        self.dist_tree.column("dist", width=70, minwidth=55, anchor="center")
        self.dist_tree.column("via", width=55, minwidth=45, anchor="center")
        self.dist_tree.column("status", width=152, minwidth=120, anchor="w")

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
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w")

        self.route_summary_var = tk.StringVar(value="Memuat data perbandingan...")
        tk.Label(
            info_card,
            textvariable=self.route_summary_var,
            bg="#F8FAFC",
            fg=TEXT_MUTED,
            font=("Segoe UI", 9),
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
        insight = tk.Label(insight_frame, textvariable=self.insight_text_var, bg='#F0FDF4', fg='#166534',
                           font=('Segoe UI', 9), justify='left', anchor='w')
        insight.pack(fill='x')
        insight_frame.bind('<Configure>', lambda e: insight.configure(wraplength=max(180, e.width-28)))

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
            font=("Segoe UI", 11, "bold")
        ).pack(side="left")

        tk.Label(
            card_header,
            text=badge_text,
            bg=badge_bg,
            fg=badge_fg,
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=2
        ).pack(side="right")

        # Metric values
        metrics_grid = tk.Frame(frame, bg=CARD_BG, pady=6)
        metrics_grid.pack(fill="x")
        metrics_grid.columnconfigure(1, weight=1)

        # Row 1: Path
        tk.Label(metrics_grid, text="Rute:", bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 9), width=8, anchor="w").grid(row=0, column=0, sticky="w")
        path_label = tk.Label(metrics_grid, text="-", bg=CARD_BG, fg=COLOR_PATH, font=("Consolas", 9, "bold"), anchor="w", wraplength=340, justify="left")
        path_label.grid(row=0, column=1, sticky="w")

        # Row 2: Total Cost
        tk.Label(metrics_grid, text="Bobot:", bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 9), width=8, anchor="w").grid(row=1, column=0, sticky="w")
        cost_label = tk.Label(metrics_grid, text="-", bg=CARD_BG, fg=TEXT_MAIN, font=("Segoe UI", 9, "bold"), anchor="w")
        cost_label.grid(row=1, column=1, sticky="w")

        # Row 3: Runtime
        tk.Label(metrics_grid, text="Waktu:", bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 9), width=8, anchor="w").grid(row=2, column=0, sticky="w")
        time_label = tk.Label(metrics_grid, text="-", bg=CARD_BG, fg=TEXT_MAIN, font=("Segoe UI", 9, "bold"), anchor="w")
        time_label.grid(row=2, column=1, sticky="w")

        # Row 4: Steps Count
        tk.Label(metrics_grid, text="Langkah:", bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 9), width=8, anchor="w").grid(row=3, column=0, sticky="w")
        steps_label = tk.Label(metrics_grid, text="-", bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 9), anchor="w")
        steps_label.grid(row=3, column=1, sticky="w")

        metrics_grid.bind("<Configure>", lambda e: path_label.configure(wraplength=max(130, e.width-80)))

        return {
            "frame": frame,
            "path": path_label,
            "cost": cost_label,
            "time": time_label,
            "steps": steps_label,
        }
