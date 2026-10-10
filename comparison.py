"""Perbandingan yang dapat diulang dan ekspor JSON portabel.

Modul ini dipakai bersama oleh CLI dan GUI, sehingga angka yang tampil di
antarmuka dan angka yang tercetak di terminal berasal dari pengukuran yang sama
dengan aturan yang sama.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import statistics

from algorithms import Result, bellman_ford, dijkstra
from graph_io import Graph, Number

ALGORITHMS = (dijkstra, bellman_ford)


@dataclass(frozen=True)
class Timing:
    """Statistik waktu satu algoritma dalam mikrodetik.

    ``samples_ns`` menyimpan setiap pengukuran mentah dalam nanodetik sebagai
    bukti pengukuran, bukan hanya ringkasan akhirnya.
    """

    samples_ns: list[int]
    median_us: float
    min_us: float
    max_us: float
    q1_us: float
    q3_us: float


@dataclass(frozen=True)
class Comparison:
    """Hasil satu kali perbandingan kedua algoritma.

    ``results`` berisi keluaran lengkap masing-masing algoritma (termasuk jejak
    langkah untuk animasi), sedangkan ``timings`` berisi statistik benchmark.
    ``consistent`` menandai apakah kedua algoritma sepakat soal bobot minimum.
    """

    results: list[Result]
    timings: dict[str, Timing]
    repetitions: int
    warmups: int
    consistent: bool


def format_number(value: Number) -> str:
    """Ubah bobot menjadi teks; ``inf`` ditampilkan sebagai "Tidak ada jalur"."""
    if value == math.inf:
        return "Tidak ada jalur"
    return str(value) if isinstance(value, int) else f"{value:.12g}"


def costs_equal(left: Number, right: Number) -> bool:
    """Bandingkan dua bobot dengan toleransi mengambang.

    Nilai tak hingga hanya dianggap sama bila keduanya tak hingga, sehingga
    "tidak terjangkau" tidak pernah dianggap sama dengan bobot berhingga.
    """
    if left == right:
        return True
    if left == math.inf or right == math.inf:
        return False
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)


def compare(graph: Graph, start: str, goal: str, *, repetitions: int = 31,
            warmups: int = 3, record_steps: bool = True) -> Comparison:
    """Jalankan kedua algoritma lalu benchmark dengan urutan bergantian.

    Validasi masukan dan operasi berkas berada di luar pewaktu tiap algoritma,
    sedangkan pencacah operasi dan pengiriman jejak yang dinonaktifkan tetap
    termasuk di dalamnya. Jejak untuk animasi GUI diambil dari pemanggilan
    terpisah dan tidak ikut diukur.

    Urutan algoritma dibalik setiap pengukuran untuk mengurangi bias urutan, dan
    seluruh sampel waktu disimpan, bukan hanya nilai akhirnya.
    """
    if not 1 <= repetitions <= 10_000 or not 0 <= warmups <= 1_000:
        raise ValueError("Pengulangan harus 1–10000; pemanasan harus 0–1000.")
    results = [algorithm(graph, start, goal, record_steps=record_steps)
               for algorithm in ALGORITHMS]
    samples: dict[str, list[int]] = {result.name: [] for result in results}
    for index in range(warmups + repetitions):
        order = ALGORITHMS if index % 2 == 0 else ALGORITHMS[::-1]
        for algorithm in order:
            measured = algorithm(graph, start, goal, record_steps=False)
            if index >= warmups:
                samples[measured.name].append(measured.runtime_ns)
    timings = {}
    for name, values in samples.items():
        quartiles = statistics.quantiles(values, n=4, method="inclusive") if len(values) > 1 else values * 3
        timings[name] = Timing(values, statistics.median(values) / 1000,
                               min(values) / 1000, max(values) / 1000,
                               quartiles[0] / 1000, quartiles[2] / 1000)
    return Comparison(results, timings, repetitions, warmups,
                      costs_equal(results[0].cost, results[1].cost))


def comparison_data(comparison: Comparison, graph: Graph, start: str,
                    goal: str, source: str = "") -> dict:
    """Rakit hasil perbandingan menjadi dictionary yang siap diserialisasi.

    Bobot yang tidak terjangkau ditulis sebagai ``null``, bukan ``Infinity``,
    karena nilai tersebut tidak valid dalam JSON. Structuranya juga memuat
    graf masukan, informasi lingkungan, dan penjelasan apa yang termasuk serta
    tidak termasuk dalam pengukuran waktu.
    """
    algorithms = []
    for result in comparison.results:
        algorithms.append({
            "algorithm": result.name, "path": result.path,
            "reachable": bool(result.path),
            "cost": None if result.cost == math.inf else result.cost,
            "metrics": asdict(result.metrics),
            "trace_truncated": result.trace_truncated,
            "timing": asdict(comparison.timings[result.name]),
        })
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": platform.python_version(),
                        "implementation": platform.python_implementation(),
                        "platform": platform.platform(), "processor": platform.processor()},
        "source": source, "start": start, "goal": goal,
        "vertices": len(graph), "directed_edges": sum(map(len, graph.values())),
        "graph": graph, "consistent": comparison.consistent,
        "benchmark": {"repetitions": comparison.repetitions, "warmups": comparison.warmups,
                      "clock": "perf_counter_ns", "trace_recorded_in_timing": False,
                      "includes": "initialization, search, counters, reconstruction",
                      "excludes": "validation, file I/O, trace allocation, layout, animation"},
        "results": algorithms,
    }


def export_json(path: str | Path, data: dict) -> None:
    """Tulis ``data`` sebagai JSON UTF-8 yang rapi, diakhiri baris baru."""
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                          encoding="utf-8")