"""Dua algoritma jalur terpendek pada domain masukan bersama yang sama.

Keduanya menerima graf berarah dengan bobot tidak negatif dan berbagi
kontrak masukan yang identik, sehingga hasilnya selalu dapat dibandingkan
langsung.

Pengukuran runtime (runtime_ns) mencakup inisialisasi, pencacah operasi, dan
rekonstruksi rute, tetapi **tidak** mencakup validasi masukan maupun pembacaan
berkas. Gunakan ``record_steps=False`` bila hanya membutuhkan angka waktu tanpa
jejak animasi.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
import itertools
import math
from time import perf_counter_ns
from graph_io import Graph, Number, validate_graph


@dataclass(frozen=True)
class Step:
    """Satu peristiwa pencarian, dipakai sebagai sumber data animasi.

    ``kind`` menentukan jenis peristiwa:

    * ``visit``   — sebuah simpul ditetapkan jaraknya (Dijkstra).
    * ``inspect`` — sisi (edge) diperiksa, belum tentu menghasilkan perubahan.
    * ``relax``   — jarak tetangga diperbarui karena ditemukan rute lebih pendek.
    * ``pass``    — satu putaran penuh pemindaian sisi (Bellman–Ford).
    * ``done``    — pencarian selesai; selalu menjadi peristiwa terakhir.
    """

    kind: str  # visit, inspect, relax, pass, done
    node: str | None = None
    neighbor: str | None = None
    distance: Number | None = None
    iteration: int | None = None


@dataclass(frozen=True)
class Metrics:
    """Pencacah operasi hasil pencarian, untuk membandingkan efisiensi.

    ``settled_vertices`` tidak dipakai Bellman–Ford; pada algoritma itu jumlah
    putaran dikembalikan melalui ``passes``.
    """

    inspected_edges: int = 0
    relaxations: int = 0
    settled_vertices: int = 0
    passes: int = 0


@dataclass(frozen=True)
class Result:
    """Keluaran lengkap satu algoritma: rute, bobot, waktu, jejak, dan pencacah.

    ``cost`` bernilai ``math.inf`` bila tujuan tidak terjangkau, dan
    ``path`` berupa daftar kosong dalam kasus tersebut. ``steps`` kosong bila
    algoritma dijalankan dengan ``record_steps=False``.
    """

    name: str
    path: list[str]
    cost: Number
    runtime_ns: int
    steps: list[Step]
    metrics: Metrics
    trace_truncated: bool = False


class _Trace:
    """Membatasi memori jejak tanpa menghentikan pencarian yang sedang berjalan.

    Jejak berhenti ditambah setelah ``limit`` tercapai dan hanya menandai
    ``truncated``; jawaban akhirnya tetap dihitung lengkap.
    """
    def __init__(self, enabled: bool, limit: int) -> None:
        if limit < 1:
            raise ValueError("Batas langkah harus minimal 1.")
        self.enabled, self.limit = enabled, limit
        self.steps: list[Step] = []
        self.truncated = False

    def add(self, kind: str, node: str | None = None,
            neighbor: str | None = None, distance: Number | None = None,
            iteration: int | None = None) -> None:
        if not self.enabled:
            return
        if kind == "done" or len(self.steps) < self.limit:
            self.steps.append(Step(kind, node, neighbor, distance, iteration))
        else:
            self.truncated = True


def _path(previous: dict[str, str], start: str, goal: str) -> list[str]:
    if start == goal:
        return [start]
    if goal not in previous:
        return []
    route = [goal]
    while route[-1] != start:
        route.append(previous[route[-1]])
    route.reverse()
    return route


def _sum(cost: Number, weight: Number) -> Number:
    """Jumlahkan bobot tanpa tertukar dengan kondisi "tidak terjangkau".

    Luapan (overflow) float harus dilaporkan sebagai kesalahan masukan, bukan
    dibiarkan menjadi ``inf`` yang artinya "tidak ada jalur".
    """
    try:
        value = cost + weight
    except OverflowError as exc:
        raise ValueError("Total bobot melampaui kapasitas float; gunakan skala lebih kecil.") from exc
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Total bobot melampaui kapasitas float; gunakan skala lebih kecil.")
    return value


def dijkstra(graph: Graph, start: str, goal: str, *,
             record_steps: bool = True, max_steps: int = 20_000) -> Result:
    """Jalur terpendek Dijkstra memakai heap biner (binary heap) dengan duplikat malas.

    Heap menyimpan pasangan ``(jarak, nomor urut, simpul)``. Nomor urut
    monoton dari ``itertools.count`` diperlukan karena jarak bisa bernilai sama:
    tanpa pengikat itu, Tuple akan dibandingkan simpul demi simpul.

    Duplikat dibiarkan menumpuk lalu diabaikan ketika keluar dari heap. Cara ini
    dipilih karena entri yang sama tidak selalu menandakan bahwa pemrosesan
    sudah melewati titik yang benar. Pencarian berhenti begitu tujuan ditetapkan
    (settled), sebab pada bobot tidak negatif jarak saat itu sudah final.

    Kompleksitas waktu O(V + E·log(E+1)) dan ruang tambahan O(V+E), di luar
    jejak animasi. Untuk graf sederhana biasanya dibatasi O((V+E)·log V).
    """
    validate_graph(graph, start, goal)
    began = perf_counter_ns()
    trace = _Trace(record_steps, max_steps)
    distances: dict[str, Number] = {v: math.inf for v in graph}
    distances[start] = 0
    previous: dict[str, str] = {}
    settled: set[str] = set()
    counter = itertools.count()
    queue = [(0, next(counter), start)]
    inspected = relaxed = 0
    while queue:
        cost, _, vertex = heapq.heappop(queue)
        if vertex in settled:
            continue
        settled.add(vertex)
        trace.add("visit", vertex, distance=cost)
        if vertex == goal:
            break
        for neighbor, weight in graph[vertex].items():
            inspected += 1
            trace.add("inspect", vertex, neighbor)
            candidate = _sum(cost, weight)
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = vertex
                heapq.heappush(queue, (candidate, next(counter), neighbor))
                relaxed += 1
                trace.add("relax", vertex, neighbor, candidate)
    path = _path(previous, start, goal) if distances[goal] != math.inf else []
    trace.add("done")
    elapsed = perf_counter_ns() - began
    return Result("Dijkstra", path, distances[goal], elapsed, trace.steps,
                  Metrics(inspected, relaxed, len(settled)), trace.truncated)


def bellman_ford(graph: Graph, start: str, goal: str, *,
                 record_steps: bool = True, max_steps: int = 20_000) -> Result:
    """Bellman–Ford: pindai seluruh sisi di tempat, maksimum V-1 putaran.

    Berbeda dari Dijkstra, bobot disimpan dalam daftar sisi eksplisit sehingga
    tiap putaran benar-benar memeriksa semua sisi. Putaran dihentikan lebih
    awal begitu tidak ada satu pun jarak yang berubah, karena kondisi itu sudah
    menjamin kestabilan jarak.

    Pembaruan dilakukan di tempat (in-place), sehingga satu putaran dapat
    menyalurkan beberapa sisi sekaligus. Kontrak masukan bersama aplikasi
    ini menolak bobot negatif, jadi ini bukan API Bellman–Ford umum yang
    menangani bobot negatif maupun siklus berbobot negatif.

    Kompleksitas waktu O(VE+V) dan ruang tambahan O(V+E).
    """
    validate_graph(graph, start, goal)
    began = perf_counter_ns()
    trace = _Trace(record_steps, max_steps)
    distances: dict[str, Number] = {v: math.inf for v in graph}
    distances[start] = 0
    previous: dict[str, str] = {}
    edges = [(v, n, w) for v, neighbors in graph.items() for n, w in neighbors.items()]
    inspected = relaxed = passes = 0
    for iteration in range(1, len(graph)):
        passes += 1
        changed = False
        trace.add("pass", iteration=iteration)
        for vertex, neighbor, weight in edges:
            inspected += 1
            trace.add("inspect", vertex, neighbor, iteration=iteration)
            if distances[vertex] == math.inf:
                continue
            candidate = _sum(distances[vertex], weight)
            if candidate < distances[neighbor]:
                distances[neighbor] = candidate
                previous[neighbor] = vertex
                changed = True
                relaxed += 1
                trace.add("relax", vertex, neighbor, candidate, iteration)
        if not changed:
            break
    path = _path(previous, start, goal) if distances[goal] != math.inf else []
    trace.add("done")
    elapsed = perf_counter_ns() - began
    return Result("Bellman–Ford", path, distances[goal], elapsed, trace.steps,
                  Metrics(inspected, relaxed, passes=passes), trace.truncated)
