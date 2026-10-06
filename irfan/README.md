# Tugas 1 — Pencarian Jalur Terpendek

Program membaca `graf.txt`, menghitung jalur terpendek dengan Dijkstra dan Bellman–Ford, membandingkan jalur, bobot, serta waktu perhitungannya, kemudian menganimasikan langkah algoritma di GUI Tkinter.

## Menjalankan

1. Pasang Python 3.10 atau lebih baru dengan dukungan Tkinter. Program hanya memakai pustaka standar Python.
2. Simpan `MMAIKelompokX.py`, `graph_io.py`, `algorithms.py`, `gui.py`, dan `graf.txt` dalam satu folder.
3. Ganti `X` pada nama file utama dengan nomor kelompok sebenarnya, lalu jalankan:

   ```powershell
   python MMAIKelompokX.py
   ```

   Jika nama berkas sudah diganti, sesuaikan perintah tersebut. Perintah boleh dijalankan dari folder lain dengan menyebut path lengkap ke file utama.

4. Program otomatis membuka `graf.txt` di folder yang sama. Tombol **Buka graf.txt** dapat dipakai untuk memilih graf lain. **Hitung keduanya** menjalankan ulang kedua algoritma. Pilih algoritma pada daftar, lalu gunakan **Putar**, **Jeda**, **Satu langkah**, atau **Ulangi** untuk animasi.

Jalankan pemeriksaan otomatis dengan `python -m unittest -v test_tugas1.py` dari folder proyek.

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

Jika tujuan tidak terjangkau, hasil menampilkan “Tidak ada jalur”. Waktu ditampilkan dalam mikrodetik (µs), diukur untuk perhitungan algoritma beserta pencatatan langkah, tanpa waktu animasi. Angka waktu dari PDF hanya ilustrasi dan tidak harus sama.

## Isi berkas

- `MMAIKelompokX.py`: titik masuk program.
- `graph_io.py`: pembacaan dan validasi input tanpa mengeksekusi kode dari file.
- `algorithms.py`: Dijkstra, Bellman–Ford, hasil, dan langkah animasi.
- `gui.py`: gambar graf, kontrol animasi, dan perbandingan hasil.
- `graf.txt`: contoh input pertama dari soal.
- `contoh_V1_V10.txt` dan `contoh_B_H.txt`: dua contoh lain untuk demonstrasi.
- `test_tugas1.py`: uji tiga contoh dan kondisi gagal.
- `LAPORAN.md` dan `LAPORAN.docx`: laporan proyek. Isi nama dan nomor kelompok sebelum dikumpulkan.
- `NASKAH_VIDEO.md`: alur presentasi untuk tiga anggota. Rekam video sekitar 10 menit dengan kontribusi semuanya.

## Sebelum pengumpulan

Isi identitas kelompok di laporan, ganti `X` pada nama program utama, jalankan uji di komputer anggota lain, dan rekam video presentasi yang memperlihatkan program berjalan.
