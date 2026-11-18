# GeoHealth: Sistem Informasi Geospasial Fasilitas Kesehatan untuk Mitigasi Dampak Karhutla

Aplikasi web GIS berbasis Location-Based Service (LBS) untuk memetakan persebaran fasilitas kesehatan (Rumah Sakit, Puskesmas, dan Klinik), menyaring kesiapan layanan penanganan gangguan pernapasan akibat asap kebakaran hutan dan lahan (IGD 24 jam, oksigen, dokter jaga, tempat tidur), serta menganalisis wilayah dengan akses fasilitas kesehatan terbatas di **Provinsi Sumatera Selatan**.

## Fitur Utama

1. **Peta Persebaran Fasilitas Kesehatan (Bentuk + Warna)**: Membedakan Rumah Sakit (lingkaran dengan palang), Puskesmas (persegi), dan Klinik Pratama (segitiga) beserta batas kabupaten/kota pilot rawan karhutla (Ogan Komering Ilir, Banyuasin, Musi Banyuasin, dan Kota Palembang).
2. **Pencarian Fasilitas Terdekat (kNN & Range Query) + Arah Kompas**: Menghitung jarak garis lurus *great-circle* (Haversine/geodesik dalam meter) dan arah azimuth kompas dari lokasi GPS pengguna atau titik yang diklik pada peta, dilengkapi tombol darurat satu klik **Cari IGD terdekat**.
3. **Penyaringan Berdasarkan Kebutuhan Darurat Asap**: Saringan stok oksigen, IGD 24 jam, dokter jaga, ketersediaan tempat tidur, jenis fasilitas, dan radius jangkauan (5 s.d. 120 km).
4. **Lapisan Kontekstual Titik Panas (Hotspot) Karhutla**: Menampilkan titik panas 7 hari terakhir (NASA FIRMS VIIRS / sampel berlabel) dan peringatan otomatis jumlah titik panas dalam radius 5 km dari posisi pengguna.
5. **Analisis Wilayah Akses Terbatas (Grid Heksagonal Uber H3)**: Mengagregasi kepadatan titik panas dan jarak ke fasilitas kesehatan siap IGD+oksigen pada sel H3 resolusi 6 untuk merekomendasikan prioritas lokasi posko kesehatan darurat.
6. **Pelindungan Privasi Lokasi (UU PDP No. 27/2022)**: Pembulatan koordinat otomatis ($\pm 110\text{ m}$), *accuracy gating* ($> 500\text{ m}$), *plausibility check* kecepatan perpindahan, dan kebijakan tanpa penyimpanan jejak lokasi (`Cache-Control: no-store`).

## Cara Menjalankan

### 1. Persiapan Lingkungan Python

```powershell
cd backend
python -m pip install -r requirements.txt
```

### 2. Menjalankan Database Spasial

Aplikasi mendukung **PostgreSQL + PostGIS** melalui Docker Compose (dan secara otomatis beralih ke engine spasial lokal `SQLite + Shapely STRtree + PyProj Geod` apabila layanan Docker/WSL2 belum berjalan di host):

```powershell
# Opsional: salin konfigurasi environment
Copy-Item .env.example .env

# Jika Docker Desktop & WSL2 aktif:
docker compose up -d
```

> Catatan Windows: Jika Docker Desktop menampilkan pesan *WSL is not installed*, jalankan `wsl --install` dari PowerShell Administrator lalu mulai ulang (restart) Windows sekali agar kernel WSL2 aktif, kemudian jalankan `docker compose up -d`.

### 3. Menjalankan Pipeline ETL (Data Kabupaten, OSM, Hotspot, dan Simulasi)

```powershell
cd backend
python -m etl.run_all
```

Untuk mengimpor dataset CSV fasilitas kesehatan milik sendiri, taruh file `.csv` di folder `data/custom/` (lihat format di `data/custom/README.md`) lalu jalankan `python -m etl.import_csv`.

### 4. Menjalankan Server Aplikasi Web

```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Buka `http://127.0.0.1:8000` di peramban.

### 5. Menjalankan Pengujian Otomatis

```powershell
cd backend
python -m pytest -q
```

## Dokumentasi Tambahan

- [Metodologi Geospasial & Keputusan Desain](docs/metodologi.md)
- [Kebijakan Privasi & Keamanan Lokasi](docs/privasi.md)
- [Format Impor Dataset CSV Kustom](data/custom/README.md)
