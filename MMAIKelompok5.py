"""Titik masuk aplikasi gabungan Dijkstra dan Bellman–Ford — MMAI1001.

Dua mode jalan:

* Tanpa argumen: membuka antarmuka graphical (GUI) berbasis Tkinter.
* Dengan ``--cli``: menjalankan perbandingan di terminal dan mencetak ringkasan,
  tanpa memerlukan layar.

Berkas graf dibaca relatif terhadap lokasi berkas ini, sehingga aplikasi tetap
menemukan berkas default dan folder contoh dari folder kerja mana pun.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from comparison import compare, comparison_data, export_json, format_number
from graph_io import load_graph


def _prepare_stdout() -> None:
    """Paksa keluaran terminal ke UTF-8.

    Console Windows bawaan (``cp1252``/``charmap``) tidak dapat mencetak
    karakter seperti ``→`` dan ``–`` yang dipakai pada keluaran perbandingan.
    Kegagalan encoding membuat program berhenti dengan galat yang menyesatkan,
    jadi keluaran dialihkan ke UTF-8 lebih dulu bila stdout mendukungnya.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    """Jalankan aplikasi; kembalikan kode keluar untuk argv yang diberikan.

    Mengembalikan 0 bila pencarian sukses, 1 bila kedua algoritma memberi
    bobot berbeda, dan 2 bila masukan tidak valid atau GUI tidak dapat dibuka.
    """
    _prepare_stdout()
    parser = argparse.ArgumentParser(description="Perbandingan Dijkstra dan Bellman–Ford — MMAI1001")
    parser.add_argument("file", nargs="?", type=Path, default=Path(__file__).with_name("graf.txt"),
                        help="file graf; default graf.txt di sebelah program")
    parser.add_argument("--cli", action="store_true", help="jalankan tanpa GUI/Tkinter")
    parser.add_argument("--start", help="ganti verteks awal (mode CLI)")
    parser.add_argument("--goal", help="ganti verteks tujuan (mode CLI)")
    parser.add_argument("--repeat", type=int, default=31, help="pengukuran benchmark (default 31)")
    parser.add_argument("--export", type=Path, help="simpan hasil CLI beserta sampel waktu ke JSON")
    args = parser.parse_args(argv)
    if not args.cli and (args.start or args.goal or args.export or args.repeat != 31):
        parser.error("--start, --goal, --repeat, dan --export digunakan bersama --cli")
    if args.cli:
        try:
            graph, start, goal = load_graph(args.file)
            start, goal = args.start or start, args.goal or goal
            comparison = compare(graph, start, goal, repetitions=args.repeat, record_steps=False)
            print(f"Graf: {args.file.name} | {len(graph)} verteks | {start} → {goal}")
            for result in comparison.results:
                timing = comparison.timings[result.name]
                print(f"\n{result.name}\n  Jalur terpendek: {' → '.join(result.path) or 'Tidak ada jalur'}")
                print(f"  Bobot minimum: {format_number(result.cost)}")
                print(f"  Runtime median: {timing.median_us:.3f} µs ({args.repeat} pengukuran tanpa trace)")
                print(f"  Sisi diperiksa: {result.metrics.inspected_edges}; relaksasi: {result.metrics.relaxations}")
            print("\nPerbandingan: " + ("bobot minimum konsisten" if comparison.consistent else "PERBEDAAN HASIL"))
            if args.export:
                export_json(args.export, comparison_data(comparison, graph, start, goal, str(args.file)))
                print(f"Hasil disimpan: {args.export}")
            return 0 if comparison.consistent else 1
        except (OSError, UnicodeError, ValueError) as exc:
            print(f"Gagal: {exc}", file=sys.stderr)
            return 2
    try:
        from gui import ShortestPathApp
    except ImportError as exc:
        print(f"GUI membutuhkan Python dengan Tcl/Tk (Tkinter): {exc}\n"
              "Uji instalasi: python -m tkinter. Lihat README.md.\n"
              "Mode terminal tetap tersedia: python MMAIKelompok5.py --cli", file=sys.stderr)
        return 2
    try:
        ShortestPathApp(args.file).mainloop()
    except Exception as exc:
        import tkinter
        if not isinstance(exc, tkinter.TclError):
            raise
        print(f"GUI tidak dapat dibuka: {exc}\nGunakan sesi desktop atau mode --cli.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
