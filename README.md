# Tugas 1 — Pencarian Jalur Terpendek

Program membaca `graf.txt`, menghitung jalur terpendek dengan Dijkstra dan Bellman–Ford, membandingkan jalur, bobot, serta waktu perhitungannya, kemudian menganimasikan langkah algoritma di GUI Tkinter. Ketiga contoh dari PDF tugas tersedia langsung melalui pemilih contoh.

## Menjalankan

1. Pasang Python 3.10 atau lebih baru dengan dukungan Tkinter. Program hanya memakai pustaka standar Python.
2. Simpan seluruh file Python, `graf.txt`, dan folder `contoh/` dalam satu folder proyek. Ikut sertakan `graph_view.py`, `playback.py`, dan `examples.py`.
3. Ganti `X` pada nama file utama dengan nomor kelompok sebenarnya, lalu jalankan:

   ```powershell
   python MMAIKelompokX.py
   ```

   Jika nama berkas sudah diganti, sesuaikan perintah tersebut. Perintah boleh dijalankan dari folder lain dengan menyebut path lengkap ke file utama.

4. Program otomatis membuka `graf.txt` di folder yang sama dan langsung menghitung hasil kedua algoritma. Pilih contoh soal dari daftar atau gunakan **Buka file…** untuk memuat file sendiri. Pilihan **graf.txt · file utama** kembali memuat input utama.

Jalankan pemeriksaan otomatis dengan `python -m unittest -v test_tugas1.py` dari folder proyek.

## Memilih graf dan rute

| Pilihan | Graf dan rute bawaan | Bobot minimum |
|---|---|---:|
| Contoh A | 15 simpul, V1 → V15 | 505 |
| Contoh B | 15 simpul, V1 → V10 | 400 |
| Contoh C | 10 simpul, B → H | 9 |

Contoh A dan B menggunakan struktur graf yang sama dengan tujuan berbeda. Contoh C menggunakan graf lain dengan nama simpul A–J. Salinan ketiga contoh disimpan di `contoh/`, sehingga tetap tersedia saat Anda mengubah `graf.txt` untuk percobaan sendiri.

Ubah titik awal dan tujuan melalui daftar simpul, atau gunakan tombol **⇄** untuk menukar arah. Hasil kedua algoritma otomatis dihitung kembali dan animasi kembali ke awal. Perubahan rute melalui GUI hanya berlaku pada sesi program; isi file sumber tidak ditimpa. Untuk membaca perubahan yang dibuat di editor, buka kembali file tersebut dengan **Buka file…**. **Hitung ulang** menghitung graf yang sudah dimuat dan memperbarui waktu pengukurannya.

## Menggunakan tampilan interaktif

- **Animasi:** pilih Dijkstra atau Bellman–Ford, lalu tekan **Putar/Jeda**. Gunakan **Mundur/Maju** untuk menelusuri proses, **Ulangi** untuk kembali ke awal, atau **Hasil akhir** untuk melihat jalur akhir.
- **Linimasa:** geser indikator progres untuk menuju langkah tertentu. Kecepatan **0.5×, 1×, 2×, atau 4×** mengatur jeda animasi; durasi ini tidak dihitung sebagai runtime algoritma.
- **Graf:** tarik simpul untuk merapikan posisi, tarik area kosong untuk menggeser kanvas, dan gunakan roda mouse untuk memperbesar atau memperkecil. Tombol **Atur ulang** mengembalikan tata letak serta pembesaran awal.
- **Jarak dan pendahulu:** angka pada simpul dan tabel pada tab **Jarak** mengikuti langkah yang sedang ditampilkan. Nilai `∞` berarti belum ditemukan jalur ke simpul tersebut; pendahulu adalah simpul sebelumnya pada jalur terbaik yang sudah ditemukan pada langkah itu. Dijkstra berhenti ketika tujuan dipastikan, sehingga jarak simpul lain yang belum selesai masih dapat bersifat sementara.
- **Penjelasan:** panel langkah menerangkan pemilihan simpul, pemeriksaan sisi, perubahan jarak, atau putaran Bellman–Ford. Tab **Hasil** menampilkan hasil akhir kedua algoritma, meskipun animasi masih berlangsung. Tab **Panduan** merangkum penggunaan antarmuka.
- **Ekspor hasil:** tekan **Simpan hasil perbandingan…** untuk menyimpan perbandingan kedua algoritma ke file teks.

Saat fokus berada di area graf, gunakan **Spasi** untuk putar/jeda, **←/→** untuk langkah sebelumnya/berikutnya, **Home** untuk awal, dan **End** untuk hasil. Pintasan tidak mengambil alih input saat Anda menggunakan kontrol formulir.

Warna dan penanda membedakan titik awal, tujuan, sisi yang sedang diperiksa, pembaruan jarak, serta jalur akhir. Legenda di GUI menjelaskan maknanya. Pada graf berarah, panah menunjukkan arah sisi; menarik simpul hanya mengubah tampilan dan tidak mengubah bobot atau hubungan graf.

## Format input

Isi berkas berupa satu assignment `graph = {...}` atau `graf = {...}`, diikuti baris titik awal dan tujuan. Contoh:

```text
graph = {
    'A': {'B': 4, 'C': 2},
    'B': {'A': 4},
    'C': {},
}
A C
```

Setiap simpul tujuan dari sebuah sisi harus terdaftar sebagai kunci utama dictionary. Sisi berarah didukung; untuk sisi dua arah, tulis kedua arahnya. Bobot harus berupa angka finite dan tidak negatif, karena kedua algoritma dibandingkan pada input yang sama dan Dijkstra memerlukan bobot nonnegatif. Jika nama semua simpul terdiri atas satu karakter, format `BH` pada contoh ketiga soal juga diterima sebagai `B H`.

Jika tujuan tidak terjangkau, hasil menampilkan “Tidak ada jalur”. Waktu ditampilkan dalam detik (s) dengan enam angka di belakang koma dan nilai setaranya dalam mikrodetik (µs) di sampingnya, misalnya `0.000100 s (100.0 µs)`. Keduanya berasal dari satu pengukuran perhitungan algoritma beserta pencatatan langkah, tanpa waktu animasi. Angka waktu dari PDF hanya ilustrasi dan tidak harus sama.

## Isi berkas

- `MMAIKelompokX.py`: titik masuk program.
- `graph_io.py`: pembacaan dan validasi input tanpa mengeksekusi kode dari file.
- `algorithms.py`: Dijkstra, Bellman–Ford, hasil, dan langkah animasi.
- `gui.py`: pilihan contoh/rute, pemutaran langkah, tabel jarak, kartu hasil, dan ekspor teks.
- `graph_view.py`: gambar graf serta interaksi tarik simpul, geser, dan zoom.
- `playback.py`: keadaan jarak/pendahulu serta pemutaran ulang langkah secara maju, mundur, dan langsung ke posisi tertentu.
- `examples.py` dan `contoh/`: katalog serta tiga file contoh resmi dari PDF.
- `graf.txt`: input utama yang dapat diedit sendiri.
- `contoh_V1_V10.txt` dan `contoh_B_H.txt`: salinan contoh lama yang tetap dapat dibuka melalui **Buka file**.
- `test_tugas1.py`: uji tiga contoh dan kondisi gagal.
- `laporan/LAPORAN.md` dan `laporan/LAPORAN.docx`: laporan proyek. Isi nama dan nomor kelompok sebelum dikumpulkan.
- `laporan/NASKAH_VIDEO.md`: alur presentasi untuk tiga anggota. Rekam video sekitar 10 menit dengan kontribusi semuanya.

## Sebelum pengumpulan

Isi identitas kelompok di laporan, ganti `X` pada nama program utama, jalankan uji di komputer anggota lain, dan rekam video presentasi yang memperlihatkan program berjalan.

Saat mengirim arsip proyek, sertakan semua modul Python, `graf.txt`, folder `contoh/`, laporan, dan video. Folder `laporan/` diabaikan oleh konfigurasi Git proyek; sertakan isinya secara manual jika menyiapkan pengumpulan dari hasil clone atau arsip Git. Batas pengumpulan pada PDF: **Sabtu, 10 Oktober 2026 pukul 23.59 WIB**.
