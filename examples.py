"""Tiga contoh masukan resmi dari halaman 3-4 PDF tugas.

Berkas contoh disimpan terpisah dari ``graf.txt`` yang dapat diedit pengguna,
sehingga pemilih contoh selalu membuka data asli soal apa pun folder kerja
yang sedang dipakai.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Example:
    """Satu pilihan contoh di pemilih pada GUI.

    ``expected_cost`` adalah bobot minimum hasil jawaban resmi; dipakai uji
    untuk memeriksa bahwa aplikasi masih menghitung hal yang sama.
    """

    key: str
    title: str
    description: str
    filename: str
    expected_cost: int


EXAMPLES: tuple[Example, ...] = (
    Example(
        key="a",
        title="Contoh A · V1 → V15",
        description="15 simpul · tujuan V15 · bobot minimum 505",
        filename="contoh_a.txt",
        expected_cost=505,
    ),
    Example(
        key="b",
        title="Contoh B · V1 → V10",
        description="15 simpul · tujuan V10 · bobot minimum 400",
        filename="contoh_b.txt",
        expected_cost=400,
    ),
    Example(
        key="c",
        title="Contoh C · B → H",
        description="10 simpul · tujuan H · bobot minimum 9",
        filename="contoh_c.txt",
        expected_cost=9,
    ),
)


def example_path(example: Example) -> Path:
    """Kembalikan lokasi absolut berkas contoh, bebas dari folder kerja aktif.

    Path dihitung relatif terhadap berkas modul ini, sehingga berkas
    ``contoh/contoh_a.txt`` tetap ditemukan walau aplikasi dijalankan dari
    folder lain.
    """
    return Path(__file__).resolve().parent / "contoh" / example.filename