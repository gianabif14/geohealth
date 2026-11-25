# GeoHealth: Sistem Informasi Geospasial Fasilitas Kesehatan untuk Mitigasi Dampak Karhutla (Skala Nasional)

Aplikasi web GIS berbasis Location-Based Service (LBS) untuk memetakan persebaran fasilitas kesehatan (Rumah Sakit, Puskesmas, dan Klinik) di **seluruh Indonesia**, menyaring kesiapan layanan penanganan gangguan pernapasan akibat asap kebakaran hutan dan lahan (IGD 24 jam, oksigen, dokter jaga, tempat tidur), serta menganalisis wilayah dengan akses fasilitas kesehatan terbatas berbasis grid heksagonal Uber H3.

## Cakupan Wilayah

- **Cakupan Nasional Indonesia**: `-11.10` s.d. `6.10` Lintang, `94.90` s.d. `141.10` Bujur.
- **Batas Administrasi**: ~514 kabupaten/kota se-Indonesia (`data/admin/kabupaten_indonesia.geojson`).

## Fitur Utama

1. **Peta Persebaran Fasilitas Kesehatan & Clustering Nasional**:
   - Membedakan Rumah Sakit, Puskesmas, dan Klinik beserta status kesiapan layanan darurat asap.
   - Menggunakan *viewport loading* (`bbox`) dengan *debounce* serta clustering marker (`Leaflet.markercluster`) agar peta tetap ringan saat *zoom out* ke seluruh Indonesia.
   - Layer batas administrasi kabupaten/kota ditampilkan adaptif pada tingkat zoom menengah/dekat (`zoom >= 7`).
2. **Pencarian Lokasi & Fasilitas Terdekat (kNN & Range Query) + Arah Kompas**:
   - Pencarian kota/lokasi se-Indonesia menggunakan geocoding Nominatim OpenStreetMap (`countrycodes=id`) atau posisi GPS pengguna.
   - Menghitung jarak garis lurus *great-circle* (Haversine/geodesik dalam meter), arah azimuth kompas, serta rute jalan melalui OSRM, dilengkapi tombol darurat satu klik **Cari IGD terdekat**.
3. **Penyaringan Berdasarkan Kebutuhan Darurat Asap**:
   - Saringan stok oksigen, IGD 24 jam, dokter jaga, ketersediaan tempat tidur, jenis fasilitas, dan radius jangkauan.
4. **Feed Hotspot Nasional (NASA FIRMS)**:
   - Memuat titik panas seluruh Indonesia dari sumber **VIIRS NOAA-20 NRT** dan **MODIS NRT** (rentang 24 jam / 3 hari / 7 hari) sesuai area pandang peta (`bbox`) dengan batas `limit` aman, serta menghitung jumlah titik panas dalam radius 5 km dari posisi pengguna.
5. **Analisis Wilayah Akses Terbatas (Grid Heksagonal Uber H3)**:
   - Mengagregasi kepadatan titik panas dan jarak ke fasilitas kesehatan siap IGD+oksigen pada sel H3 resolusi 6 menggunakan indeks spasial `STRtree` untuk merekomendasikan peringkat kabupaten dan top sel H3 paling kritis (`< 500 ms`).
6. **Pelindungan Privasi Lokasi (UU PDP No. 27/2022)**:
   - Pembulatan koordinat otomatis ($\pm 110\text{ m}$), *accuracy gating* ($> 500\text{ m}$), *plausibility check* kecepatan perpindahan, validasi cakupan wilayah Indonesia (`422` untuk koordinat di luar wilayah), dan kebijakan tanpa penyimpanan jejak lokasi (`Cache-Control: no-store`).

## Ringkasan Arsitektur & Direktori

| Direktori | Peran & Komponen Utama |
|---|---|
| `backend/etl/`, `data/` | Pipeline batas ~514 kabupaten/kota (`load_admin.py`), faskes OSM nasional via Geofabrik/Overpass (`fetch_osm.py`, `import_csv.py`), simulasi status (`simulate_status.py`), dan feed hotspot FIRMS nasional dengan `STRtree` (`fetch_firms.py`). |
| `backend/app/`, `backend/sql/`, `backend/tests/` | Konfigurasi bbox nasional (`config.py`, `geo.py`, `privacy.py`), optimasi query `bbox`, `ST_SimplifyPreserveTopology`, & `limit` (`db.py`, `routers/hotspot.py`), optimasi `STRtree` analisis H3 (`services/akses.py`, `routers/analisis.py`), metadata (`routers/meta.py`), dan unit test (`tests/`). |
| `frontend/` | Pencarian lokasi Nominatim Indonesia, *viewport loading* (`bbox` + debounce), `Leaflet.markercluster`, visibilitas layer kabupaten (`zoom >= 7`), dan pembaruan teks UI cakupan Indonesia. |

## Endpoint API Utama

Semua kontrak JSON utama tetap terjaga dengan dukungan filter skala nasional:

- `GET /api/meta` — Ringkasan metadata cakupan (`"Indonesia"`), jumlah faskes, status, dan pembaruan hotspot terakhir.
- `GET /api/terdekat?lat=&lon=&radius_km=&...` — Pencarian faskes terdekat dengan validasi cakupan Indonesia dan *location cloaking*.
- `GET /api/hotspot?hari=&bbox=&limit=` — GeoJSON titik panas nasional sesuai rentang hari dan viewport `bbox`.
- `GET /api/hotspot/dekat?lat=&lon=&radius_km=&hari=` — Titik panas terdekat dari titik acuan.
- `GET /api/kabupaten?bbox=` — GeoJSON batas kabupaten/kota (mendukung filter `bbox` dan penyederhanaan geometri di PostGIS).
- `GET /api/analisis/akses?limit=50` — Peringkat prioritas posko kabupaten/kota dan daftar top sel H3 paling kritis.

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

### 3. Menjalankan Pipeline ETL Nasional

```powershell
cd backend
python -m etl.run_all
```

Untuk mengimpor dataset CSV fasilitas kesehatan milik sendiri (atau hasil ekstrak OSM Geofabrik `indonesia-latest.osm.pbf`), simpan di folder `data/custom/` (lihat format di `data/custom/README.md`) lalu jalankan `python -m etl.import_csv`.

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

## Alur Integrasi Tim (Merge Berurutan)

1. Merge branch **Orang 1** (`feat/etl-indonesia`) ke `main` -> jalankan `python -m etl.run_all` pada database lokal/staging.
2. Merge branch **Orang 2** (`feat/api-indonesia`) ke `main` -> jalankan `python -m pytest -q` untuk memastikan seluruh API & uji performa lulus.
3. Merge branch **Orang 3** (`feat/ui-indonesia`) ke `main` -> lakukan uji *end-to-end* di browser (pencarian kota lintas pulau, pergeseran peta dengan `bbox` hotspot 24 jam / 3 hari / 7 hari, serta tab **Analisis Akses & Posko**).

## Dokumentasi Tambahan

- [Metodologi Geospasial & Keputusan Desain](docs/metodologi.md)
- [Kebijakan Privasi & Keamanan Lokasi](docs/privasi.md)
- [Format Impor Dataset CSV Kustom](data/custom/README.md)