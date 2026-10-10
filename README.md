# Tugas 1 MMAI1001 — Proyek Gabungan

Satu aplikasi mandiri yang menggabungkan tiga karya:

| Bagian | Sumber | Yang dipertahankan |
|---|---|---|
| Desain aplikasi | **Ichsan** | Tema terang/teal, header, pemilih contoh dan awal/tujuan, susunan panel, kontrol putar/jeda, maju/mundur, penggeser progres, kecepatan, penjelasan langkah |
| Graf dan animasi | **Irfan** | Kanvas gelap, grid titik, tata letak spring, simpul bercahaya, jarak di simpul, pohon pendahulu, sisi Bézier, partikel bergerak, animasi jalur akhir, tooltip, geser simpul, klik kanan untuk awal/tujuan |
| Panel kanan | **Ardi** | Tab Hasil Perbandingan dan Simulasi Langkah, kartu kedua algoritma, badge metode, tabel Simpul / Jarak d[v] / Via π[v] / Keterangan, warna status, auto-scroll |

Ketiga folder sumber tidak diperlukan saat menjalankan aplikasi ini. Semua kode dan contoh input yang dibutuhkan ada di folder ini.

## Menjalankan

Gunakan Python 3.10+ dengan Tkinter. Aplikasi hanya memakai pustaka standar; tidak membutuhkan paket pip.

Dari folder repo:

```bash
python MMAIKelompok5.py
```

Mode terminal tetap bisa digunakan tanpa layar:

```bash
python MMAIKelompok5.py --cli
python MMAIKelompok5.py --cli --goal V10 --export hasil_V10.json
```

Folder tujuan ekspor harus sudah ada; aplikasi membuat berkas, bukan foldernya.

Gunakan `python3` jika nama perintah Python pada sistem Anda adalah `python3`. Berkas default dan contoh ditemukan relatif terhadap program, sehingga aplikasi bisa dibuka dari folder kerja lain.

Untuk memeriksa Tkinter, jalankan `python -m tkinter`. GUI memerlukan sesi desktop.

## Cara memakai GUI

1. Pilih contoh A/B/C atau **Buka file…**. Hasil kedua algoritma dihitung otomatis.
2. Ubah **Awal** dan **Tujuan**, gunakan tombol tukar, atau klik kanan pada simpul.
3. Pilih **Dijkstra** atau **Bellman–Ford** pada kontrol di bawah graf.
4. Gunakan **Putar/Jeda**, **Mundur**, **Maju**, **Ulangi**, atau **Hasil akhir**. Penggeser progres dapat digunakan untuk berpindah ke langkah tertentu.
5. Tab **Simulasi Langkah** menampilkan tabel Ardi yang diperbarui sesuai langkah graf. Tab **Hasil Perbandingan** menampilkan kartu rute, bobot, runtime, dan jumlah langkah.
6. Seret simpul untuk merapikan graf, seret latar untuk menggeser, dan gulir atau gunakan tombol `+`/`−` untuk zoom. **Atur ulang** mengembalikan tata letak.
7. **Simpan hasil perbandingan…** mengekspor JSON atau teks. JSON juga memuat graf, statistik, dan seluruh sampel benchmark.

Keyboard saat fokus bukan pada kontrol input: **Spasi** untuk putar/jeda, **←/→** untuk mundur/maju, **Home** untuk ulangi, dan **End** untuk hasil akhir.

Posisi simpul hanya untuk visualisasi; menggeser graf tidak mengubah bobot atau hasil pencarian. Animasi dan tabel menggunakan objek playback yang sama, sehingga bergerak maju/mundur tidak mengubah runtime hasil perhitungan.

## Input dan hasil acuan

```text
graph = {
    'A': {'B': 2, 'C': 9},
    'B': {'C': 1},
    'C': {}
}
A C
```

Gunakan `graph` atau `graf`. Nama simpul tidak boleh kosong atau mengandung spasi. Semua tetangga harus terdaftar sebagai simpul. Input diparsing sebagai literal, bukan dieksekusi sebagai kode Python. Kunci duplikat, bobot negatif, boolean, serta nilai nonfinite ditolak. Sisi dua arah ditulis pada kedua simpul. Bentuk `BH` untuk nama simpul satu karakter diterima sesuai soal.

| Contoh | Rute | Bobot |
|---|---|---:|
| A | V1 → V2 → V5 → V9 → V12 → V15 | 505 |
| B | V1 → V4 → V6 → V10 | 400 |
| C | B → C → F → E → H | 9 |

Runtime GUI adalah median 31 pengukuran, dengan tiga putaran pemanasan dan urutan algoritma bergantian. Waktu mencakup inisialisasi, pencarian, pencacah operasi, dan rekonstruksi rute; pembacaan berkas, validasi, penyimpanan jejak, serta animasi tidak dihitung. Runtime bisa berubah antar-eksekusi.

Dijkstra berhenti ketika tujuan ditetapkan. Jarak pada simpul lain yang belum ditetapkan tetap diberi label **Jarak Sementara**, walaupun animasi telah selesai. Bellman–Ford menghitung jarak hingga tidak berubah atau batas V−1 putaran. Implementasi keduanya menggunakan kontrak input nonnegatif yang sama.

## Struktur dan integrasi

| Berkas | Peran |
|---|---|
| `MMAIKelompok5.py` | Peluncur GUI/CLI mandiri |
| `gui.py` | Desain dan kontrol Ichsan; koordinasi komputasi dan playback |
| `graph_view.py` | Renderer dan efek animasi dari Irfan, dipisahkan menjadi komponen kanvas |
| `results_panel.py` | Kartu hasil dan tabel kanan dari Ardi |
| `playback.py` | Rekonstruksi keadaan langkah maju/mundur dari Ichsan |
| `algorithms.py`, `graph_io.py`, `comparison.py` | Algoritma, validasi, benchmark, dan ekspor dari Irfan |
| `layout.py` | Tata letak spring dari Irfan |
| `examples.py`, `contoh/` | Pemilih tiga contoh soal dari Ichsan |
| `tests/` | Uji algoritma, input, CLI, dan integrasi GUI |

Komputasi dijalankan di thread pekerja; hanya thread utama yang mengakses widget Tk. Satu playback menyuplai keadaan graf dan tabel kanan. Pengukur runtime terpisah dari animasi frame kanvas.

Setiap modul terdokumentasi di dalam berkasnya sendiri memakai docstring berbahasa Indonesia: docstring modul menjelaskan peran dan batas tanggung jawabnya, fungsi dan kelas publik menjelaskan parameter, nilai balik, serta alasan di balik pilihan algoritmanya, sementara method privat diberi komentar satu baris. Baca `help(algorithms)` atau `python -c "import gui; help(gui.ShortestPathApp)"` untuk menampilkannya langsung di terminal.

Untuk menjaga visualisasi tetap responsif, GUI dibatasi 120 simpul dan 1.200 entri sisi; gunakan CLI untuk graf lebih besar. Jejak animasi dibatasi 20.000 langkah, dengan pemberitahuan jika terpotong. Jawaban akhir tetap dihitung lengkap. Keterbacaan graf padat dapat ditingkatkan menggunakan zoom dan geser simpul.

## Pengujian

Dari folder repo:

```bash
python -m unittest -v
```

Perintah di atas menjalankan seluruh 29 uji di folder `tests/`. Untuk satu berkas saja:

```bash
python -m unittest tests.test_algorithms
python -m unittest tests.test_gui
python -m unittest tests.test_tugas1
```

Jalankan dari folder repo, bukan `python tests/test_gui.py`: berkas uji mengimpor modul aplikasi pada folder repo, yang tidak ada di `sys.path` bila berkas dijalankan langsung.

Uji GUI membutuhkan Tkinter dan layar yang aktif. Jika tidak tersedia, kelas uji GUI dilaporkan **skipped**, bukan dianggap sudah diuji. Uji mencakup tiga contoh soal, kasus tepi, 35 graf acak dibandingkan dengan Floyd–Warshall, peluncuran CLI dari folder lain, sinkronisasi graf/tabel, maju/mundur, zoom/geser, pergantian algoritma, ekspor, serta tampilan pada ukuran minimum.
