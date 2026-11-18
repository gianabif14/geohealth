# Kebijakan Privasi & Keamanan Data Lokasi GeoHealth

Dokumen ini merangkum penerapan prinsip pelindungan data pribadi (UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi) dan ketahanan lokasi dari Modul Pertemuan 2 Location-Based Service.

## 1. Prinsip Minimisasi Data Lokasi

| Prinsip | Implementasi di GeoHealth |
|---|---|
| Ambil lokasi hanya saat dibutuhkan | Koordinat hanya dikirim ketika pengguna menekan tombol **Pakai lokasi saya**, memilih titik pada peta, atau mengubah parameter pencarian terdekat. Tidak ada pelacakan latar belakang (*background tracking*). |
| Pembulatan spasial (*spatial cloaking* ringan) | Secara bawaan (`exact=false`), fungsi `validate_and_cloak_location()` membulatkan koordinat pengguna menjadi 3 angka desimal ($\approx 110\text{ m}$ di ekuator). Presisi ini cukup untuk mengurutkan rumah sakit dan puskesmas terdekat tanpa mengungkap alamat rumah persis pengguna. |
| Tanpa penyimpanan jejak (*zero retention*) | Server tidak memiliki tabel basis data untuk menyimpan koordinat pengguna. Middleware `privacy_no_store_middleware` menambahkan header `Cache-Control: no-store` dan `X-Privacy-Policy: no-location-retention`, serta menyensor parameter `lat`/`lon` menjadi `[REDACTED]` pada state request. |
| Opsi presisi eksplisit | Pengguna dapat mencentang **Koordinat tepat (rute)** bila membutuhkan presisi 5 desimal khusus untuk titik awal perhitungan rute jalan. |

## 2. Validasi Batas Wilayah, Accuracy Gating, dan Plausibility Check

1. **Validasi Bounding Box Sumatera Selatan**: Permintaan `/api/terdekat` dan `/api/hotspot/dekat` menolak koordinat di luar rentang $-5,20^\circ$ s.d. $-1,40^\circ\text{ LS}$ dan $101,80^\circ$ s.d. $106,40^\circ\text{ BT}$ dengan status HTTP `422 Unprocessable Entity` dan pesan penjelasan yang jelas.
2. **Accuracy Gating**: Jika perangkat melaporkan `accuracy > 500 m` (misalnya saat peramban hanya memperoleh posisi dari Cell-ID atau IP), API menyertakan `peringatan_akurasi` dan antarmuka menyarankan pengguna memilih titik secara manual pada peta.
3. **Plausibility Check (Deteksi Indikasi Fake GPS / Teleportasi)**: Apabila klien mengirimkan koordinat sebelumnya (`prev_lat`, `prev_lon`, `dt_seconds`) dan kecepatan perpindahan melebihi $140\text{ km/jam}$, sistem memberikan peringatan `peringatan_plausibilitas` bahwa terdeteksi perpindahan tidak wajar. Karena GeoHealth merupakan layanan informasi darurat publik (bukan aplikasi presensi atau pembuka hak akses), sistem tetap menampilkan daftar fasilitas kesehatan terdekat sambil memberi tahu pengguna agar memeriksa pengaturan *mock location* atau VPN mereka.
