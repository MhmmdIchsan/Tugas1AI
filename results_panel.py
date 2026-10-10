"""Panel kanan antarmuka: perbandingan hasil algoritma dan simulasi langkah.

Panel ini (``ResultsPanel``) terbagi menjadi dua tab:

* Tab "Hasil Perbandingan" memuat kartu header yang menyebut simpul awal dan
  tujuan beserta ringkasan perbandingan, dua kartu hasil—one untuk Dijkstra,
  satu untuk Bellman–Ford—yang memuat rute, bobot total, runtime, dan jumlah
  langkah, lalu satu kartu catatan analitis tentang algoritma mana yang
  lebih cepat pada pengukuran tadi.
* Tab "Simulasi Langkah" memuat ringkasan langkah yang sedang berjalan
  beserta bilah kemajuan, dan sebuah tabel keadaan langsung yang berisi
  simpul (vertex), jarak d[v], pendahulu (predecessor) via π(v), serta
  keterangan status tiap simpul seperti "Rute Terpendek", "Jarak Diperbarui",
  atau "Belum Terjangkau (∞)".

Kedua tab disinkronkan dengan pemutar ulang (playback). Setiap kali pengguna
memutar, menjeda, menggeser, atau mundur satu langkah, objek ``Playback``
mengirim keadaan terbaru ke ``ResultsPanel.render``; panel lalu menggambar ulang
seluruh isinya mengikuti langkah tersebut. Tab "Hasil Perbandingan" terisi
sekali pada hitungan pertama dan tetap sama selama pemutaran, sedangkan tabel
jarak selalu mencerminkan langkah yang sedang diputar.
"""
from __future__ import annotations
import math
import tkinter as tk
from tkinter import ttk
from playback import number as format_number

# Palet warna. Semua warna ditulis sebagai literal heksadesimal supaya panel
# tidak bergantung pada tema ttk di luar dirinya, dan nilainya sengaja tidak
# diubah—hanya keterangan perannya yang ditulis di sini.

# Warna dasar: latar panel, isi kartu, dan warna teks.
BG_MAIN = "#F8FAFC"       # Latar panel dan kartu: area di belakang simpul
CARD_BG = "#FFFFFF"       # Isi kartu dan tabel (putih)
CARD_BORDER = "#E2E8F0"   # Garis tipis pembatas kartu
TEXT_MAIN = "#0F172A"     # Teks utama, misalnya judul kartu dan nilai metrik
TEXT_MUTED = "#64748B"    # Teks sekunder, misalnya label baris metrik
TEXT_SUBTLE = "#94A3B8"   # Teks paling redup, untuk keterangan kecil

# Warna status simpul. Tiap status punya dua warna: warna solid untuk bercak
# pada graf, dan warna latar pucat (varian *-BG) untuk baris tabel.
COLOR_START = "#10B981"   # Simpul awal, titik asal pencarian
COLOR_START_BG = "#ECFDF5"# Latar baris tabel untuk simpul awal
COLOR_GOAL = "#EF4444"    # Simpul tujuan, titik akhir pencarian
COLOR_GOAL_BG = "#FEF2F2" # Latar baris tabel untuk simpul tujuan
COLOR_CURRENT = "#F59E0B" # Simpul yang sedang diproses pada langkah terkini
COLOR_CURRENT_BG = "#FFFBEB" # Latar baris tabel untuk simpul yang aktif
COLOR_VISITED = "#3B82F6" # Simpul yang jaraknya sudah ditetapkan (tetap permanen)
COLOR_VISITED_BG = "#EFF6FF" # Latar baris tabel untuk simpul yang sudah ditetapkan
COLOR_PATH = "#2563EB"    # Sisi dan simpul yang membentuk rute terpendek
COLOR_EDGE = "#CBD5E1"    # Sisi (edge) umum pada graf yang belum menjadi rute
COLOR_GRID = "#F1F5F9"    # Garis bantu pada kanvas graf


class ResultsPanel(tk.Frame):
    """Panel kanan berisi dua tab: ringkasan perbandingan dan simulasi langkah.

Panel dibangun sebagai ``tk.Frame`` biasa. Isinya terbagi menjadi tab
    "Hasil Perbandingan" (hasil akhir kedua algoritma, tidak berubah selama
    pemutaran) dan tab "Simulasi Langkah" (keadaan graf pada langkah yang
    sedang diputar, berubah mengikuti pemutaran ulang). Tab perbandingan
    diberi area gulir (scroll) agar isi kartu tidak terpotong pada panel
    yang pendek. Tombol simpan diletakkan di bagian bawah panel, di luar
    notebook, agar tetap terlihat meski isi tab sedang digulir.

    Atribut yang dipegang panel:

    * ``route_header_var``, ``route_summary_var`` — teks header dan ringkasan
      pada tab perbandingan.
    * ``dijkstra_card``, ``bellman_card`` — kamus (dictionary) dengan kunci
      ``frame``, ``path``, ``cost``, ``time``, ``steps``, yang dipakai
      `clear` dan `show_results` untuk mengisi angka.
    * ``insight_text_var`` — catatan analitis tentang runtime.
    * ``dist_tree`` — tabel jarak yang juga dibaca langsung oleh bagian
      grafik antarmuka, sehingga keduanya tidak pernah berbeda isi.
    * ``algorithm_label``, ``summary``, ``progress_text``, ``progress_bar``,
      ``action_title``, ``action_detail`` — bagian atas tab simulasi yang
      diperbarui pada setiap langkah.

    Antarmuka publiknya sengaja dibatasi pada tiga metode: `clear`,
    `show_results`, dan `render`. Metode privat lain hanya dipakai di dalam
    kelas.
    """

    # Membangun notebook, dua tab, tombol simpan, dan isi tiap tab.
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
        """Kosongkan tab perbandingan sebelum perhitungan baru dimulai.

        Dipanggil setiap kali pengguna menekan hitung ulang atau mengganti
        graf, supaya angka lama tidak sempat tertinggal di layar. Header,
        ringkasan, dan catatan analitis diganti teks "sedang dihitung",
        sedangkan keempat metrik pada tiap kartu dikembalikan ke tanda
        pisah (—) karena belum ada hasil yang sah untuk ditampilkan.

        Tabel jarak tidak ikut dikosongkan di sini; pengisian ulang barisnya
        ditangani pemanggil agar isinya sesuai graf yang baru dimuat.
        """
        self.route_header_var.set('Menghitung kedua algoritma…')
        self.route_summary_var.set('Hasil baru akan tampil setelah perhitungan selesai.')
        self.insight_text_var.set('')
        for card in (self.dijkstra_card, self.bellman_card):
            for key in ('path', 'cost', 'time', 'steps'):
                card[key].configure(text='—')

    def show_results(self, comparison, start, goal):
        """Isi tab perbandingan dari hasil satu kali perbandingan.

        Parameter:

        * ``comparison`` — objek ``Comparison`` dari modul ``comparison``,
          berisi ``results`` (keluaran lengkap kedua algoritma, termasuk
          ``path``, ``cost``, ``steps``, dan ``metrics``), ``timings``
          (statistik runtime), serta ``consistent`` yang menandai apakah
          kedua algoritma sepakat soal bobot minimum.
        * ``start`` — nama simpul asal.
        * ``goal`` — nama simpul tujuan.

        Yang diperbarui: header menjadi pencarian jalur dari ``start`` ke
        ``goal``; tiap kartu algoritma terisi rute, bobot (diformat dengan
        ``format_number``), runtime median dari benchmark, serta jumlah
        rekaman langkah dan sisi yang diperiksa; lalu satu baris ringkasan
        yang membaca perbandingan itu. Ringkasan yang sama juga disalin ke
        ``self.summary`` milik tab simulasi, sehingga kedua tab menyebut
        hasil yang sama persis.

        Bila bobot kedua algoritma berbeda, ringkasan memperingatkan bahwa
        ada yang perlu diperiksa pada masukan atau implementasi. Bila
        tujuan tidak terjangkau, keduanya disebut tidak terjangkau. Selain
        itu, ringkasan menyatakan apakah rutenya identik atau hanya
        berbobot sama. Kartu catatan analitis diisi algoritma dengan runtime
        median terendah beserta rasionya terhadap yang tertinggi, disertai
        peringatan bahwa runtime tidak mencakup animasi maupun pencatatan
        langkah dan dapat berbeda antar-eksekusi.

        Metode ini hanya mengisi nilai; pemutaran ulang belum dimulai saat
        dipanggil, jadi pemutar ulang tetap perlu disiapkan oleh pemanggil.
        """
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
        """Gambar ulang seluruh tab simulasi mengikuti keadaan pemutaran saat ini.

        Parameter ``state`` adalah objek ``Playback`` (atau apa pun yang
        memenuhi kontrak sama) yang menyimpan ``graph``, ``start``, ``goal``,
        ``result``, ``index``, ``distances``, ``previous``, ``visited``,
        ``current``, ``updated``, ``finished``, ``title``, dan ``detail``.

        Bagian atas tab lebih dulu diperbarui: judul dan penjelasan langkah,
        nama algoritma, serta bilah kemajuan yang menunjukkan ``index``
        terhadap jumlah langkah. Setelah itu tiap simpul (vertex) pada graf
        ditulis ulang satu baris tabel dengan empat kolom: nama simpul
        disertai peran "(Awal)", "(Tujuan)", atau "(Awal/Tujuan)" bila
        berimpit; jarak d[v] yang diformat; pendahulu (predecessor) dari
        ``state.previous``, atau tanda pisah bila belum ada; dan keterangan
        status. Baris yang sudah ada hanya diperbarui lewat ``item``, baris
        baru disisipkan lewat ``insert``, sehingga posisi baris di tabel
        tetap mengikuti urutan simpul pada graf dan pilihan pengguna tidak
        hilang. Baris juga diberi ``tag`` warna agar warnanya ikut berubah
        mengikuti status baru.

        Urutan pemeriksaan status menentukan apa yang ditampilkan bila
        beberapa kondisi berlaku bersamaan. Diurutkan dari yang paling
        khusus: simpul pada rute terpendek (hanya setelah pencarian selesai),
        simpul yang jaraknya baru diperbarui pada langkah ini, simpul yang
        sedang diproses, simpul yang sudah ditetapkan, simpul awal, simpul
        yang sudah punya jarak berhingga, lalu simpul yang belum terjangkau
        (jarak tak hingga). Pengecualian khusus Bellman–Ford: bila pencarian
        selesai, jejaknya tidak terpotong, dan jaraknya berhingga, simpul
        ditampilkan sebagai tetap permanen karena algoritma itu tidak
        membedakan simpul yang sudah ditetapkan maupun belum.

        Di akhir, tabel digulir (``see``) ke simpul yang baru diperbarui,
        yang sedang diproses, atau—bila pencarian selesai—simpul tujuan, agar
        baris yang sedang menjelaskan langkah berada di pandangan.

        Metode inilah yang menjaga panel tetap sinkron dengan pemutaran:
        ia dipanggil setiap kali keadaan berubah, sehingga menggeser slider
        ke belakang juga menampilkan keadaan yang benar, bukan sekadar
        menjalankan ulang animasi.
        """
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

    # Membangun tab simulasi langkah: judul algoritma, ringkasan, bilah kemajuan,
    # kartu langkah terkini, dan tabel jarak yang dapat digulir.
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
        # Tabel jarak terkini: jarak terbaik yang sudah diketahui tiap simpul,
        # disusun rapi dalam tabel berlabel simpul, d[v], via π(v), dan status.
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

        # Gaya baris tabel lewat tag Treeview: satu pasangan warna per status
        # simpul, dipakai ulang setiap kali baris digambar ulang.
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

    # Membangun tab hasil perbandingan yang dapat digulir: kartu judul,
    # dua kartu algoritma, dan kartu catatan analitis.
    def _build_results_tab(self, parent: tk.Frame) -> None:
        # Kartu judul: simpul asal dan tujuan, disusul ringkasan perbandingan.
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

        # Wadah dua kartu perbandingan: Dijkstra di atas, Bellman–Ford di bawahnya.
        cards_container = tk.Frame(parent, bg=CARD_BG)
        cards_container.pack(fill="both", expand=True, padx=12, pady=4)

        # Kartu Dijkstra, dengan badge yang menyebut teknik antrean prioritasnya.
        self.dijkstra_card = self._create_algo_card(
            cards_container,
            title="Dijkstra",
            badge_text="Priority Queue (Min-Heap)",
            badge_bg="#EFF6FF",
            badge_fg=COLOR_PATH
        )
        self.dijkstra_card["frame"].pack(fill="x", pady=(0, 8))

        # Kartu Bellman–Ford, dengan badge yang menyebut teknik relaksasi(iteratif)
        # atas sisi yang dipindai berulang.
        self.bellman_card = self._create_algo_card(
            cards_container,
            title="Bellman–Ford",
            badge_text="Iterative Edge Relaxation",
            badge_bg="#FEF3C7",
            badge_fg="#B45309"
        )
        self.bellman_card["frame"].pack(fill="x", pady=(0, 8))

        # Kartu catatan analitis: algoritma mana yang lebih cepat menurut
        # pengukuran, beserta peringatan cara mengukur runtime.
        insight_frame = tk.Frame(parent, bg="#F0FDF4", padx=12, pady=8, highlightbackground="#BBF7D0", highlightthickness=1)
        insight_frame.pack(fill="x", padx=12, pady=(0, 12))
        insight = tk.Label(insight_frame, textvariable=self.insight_text_var, bg='#F0FDF4', fg='#166534',
                           font=('Segoe UI', 9), justify='left', anchor='w')
        insight.pack(fill='x')
        insight_frame.bind('<Configure>', lambda e: insight.configure(wraplength=max(180, e.width-28)))

    # Membangun satu kartu hasil algoritma dan mengembalikan label metriknya.
    def _create_algo_card(self, parent: tk.Frame, title: str, badge_text: str, badge_bg: str, badge_fg: str) -> dict:
        frame = tk.Frame(parent, bg=CARD_BG, padx=12, pady=10, highlightbackground=CARD_BORDER, highlightthickness=1)

        # Bagian atas kartu: nama algoritma di kiri, badge teknik di kanan.
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

        # Empat baris metrik: rute, bobot total, runtime, dan jumlah langkah.
        metrics_grid = tk.Frame(frame, bg=CARD_BG, pady=6)
        metrics_grid.pack(fill="x")
        metrics_grid.columnconfigure(1, weight=1)

        # Baris 1: rute (path) hasil pencarian, dapat membungkus beberapa baris.
        tk.Label(metrics_grid, text="Rute:", bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 9), width=8, anchor="w").grid(row=0, column=0, sticky="w")
        path_label = tk.Label(metrics_grid, text="-", bg=CARD_BG, fg=COLOR_PATH, font=("Consolas", 9, "bold"), anchor="w", wraplength=340, justify="left")
        path_label.grid(row=0, column=1, sticky="w")

        # Baris 2: bobot total (total cost) rute tersebut.
        tk.Label(metrics_grid, text="Bobot:", bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 9), width=8, anchor="w").grid(row=1, column=0, sticky="w")
        cost_label = tk.Label(metrics_grid, text="-", bg=CARD_BG, fg=TEXT_MAIN, font=("Segoe UI", 9, "bold"), anchor="w")
        cost_label.grid(row=1, column=1, sticky="w")

        # Baris 3: runtime median hasil benchmark, bukan satu kali eksekusi.
        tk.Label(metrics_grid, text="Waktu:", bg=CARD_BG, fg=TEXT_MUTED, font=("Segoe UI", 9), width=8, anchor="w").grid(row=2, column=0, sticky="w")
        time_label = tk.Label(metrics_grid, text="-", bg=CARD_BG, fg=TEXT_MAIN, font=("Segoe UI", 9, "bold"), anchor="w")
        time_label.grid(row=2, column=1, sticky="w")

        # Baris 4: jumlah rekaman langkah (steps) yang dipakai animasi.
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
