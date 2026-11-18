# Metodologi Geospasial & Transparansi Data GeoHealth

## 1. Sistem Referensi Koordinat (CRS) dan Perhitungan Jarak

Sesuai materi Pertemuan 1 dan Pertemuan 2 mata kuliah Global Positioning System:
- Seluruh geometri disimpan dan dipertukarkan dalam **WGS84 Geographic (`EPSG:4326`)**.
- Perhitungan jarak dan radius **tidak pernah** dilakukan pada derajat mentah maupun proyeksi Web Mercator (`EPSG:3857`) karena distorsi faktor skala $\sec\varphi$.
- Karena wilayah Provinsi Sumatera Selatan membentang melewati batas zona UTM 48S dan 49S ($102^\circ\text{ BT}$ hingga $106^\circ\text{ BT}$), perhitungan jarak kNN dan *range query* dihitung langsung pada permukaan bola/ellipsoid:
  - Pada mode **PostgreSQL/PostGIS**, kueri memakai tipe `geography` (`ST_DWithin(geom::geography, ...)` dan operator indeks GiST `<->`) serta `ST_Azimuth`.
  - Pada mode **SQLite Spatial / Python**, kandidat disaring dengan indeks spasial R-tree (`shapely.STRtree`), lalu dihitung jarak *great-circle* **Haversine** ($R = 6.371.008,8\text{ m}$) dan azimuth geodesik ellipsoid WGS84 (`pyproj.Geod(ellps="WGS84").inv`).

## 2. Transparansi Data Simulasi dan Label Sumber

Setiap entitas fasilitas kesehatan, status layanan, dan titik panas memiliki atribut `sumber` dan waktu pembaruan:
- `faskes.sumber`: `'osm'` (OpenStreetMap & daftar terverifikasi Sumatera Selatan) atau `'csv'` (impor dataset kustom dari `data/custom/`).
- `faskes_status.sumber`: `'simulasi'` (dibangkitkan dengan generator deterministik `SEED = 20261118` pada `backend/etl/simulate_status.py`) atau `'manual'` (dari impor CSV kustom).
- `hotspot.sumber`: `'firms'` (API VIIRS NASA FIRMS) atau `'sampel'` (`data/sample/hotspot_sampel.csv`).

Pada antarmuka pengguna (kartu daftar dan popup peta), setiap informasi kapasitas tempat tidur, stok oksigen, dan IGD 24 jam selalu menampilkan label sumber dan stempel waktu pembaruannya.

## 3. Formula Analisis Wilayah Akses Terbatas (Grid Heksagonal H3)

Untuk mendukung penentuan prioritas posko kesehatan darurat pada masa karhutla:
1. Seluruh titik panas 7 hari terakhir diagregasikan ke dalam grid heksagonal **Uber H3 resolusi 6** (luas rata-rata $\approx 36\text{ km}^2$ per sel).
2. Untuk setiap sel H3 yang memiliki aktivitas titik panas, dihitung:
   - $n_{\text{hotspot}}$: jumlah titik panas 7 hari terakhir di dalam sel tersebut.
   - $d_{\text{siap}}$: jarak garis lurus (km) dari centroid sel H3 ke fasilitas kesehatan terdekat yang memiliki layanan **IGD 24 jam aktif** sekaligus **stok oksigen tersedia**.
3. Skor keterbatasan akses per sel ($0\text{ s.d. }100$) dihitung dengan:
   $$\text{Skor} = 100 \times \left(0,55 \cdot \min\!\left(\frac{d_{\text{siap}}}{\max(d_{\max}, 25)}, 1\right) + 0,45 \cdot \frac{n_{\text{hotspot}}}{n_{\max}}\right)$$
4. Kategori prioritas posko dibagi menjadi:
   - **Tinggi** ($\text{Skor} \ge 60$): titik panas padat dan jauh dari fasilitas kesehatan siap IGD+oksigen.
   - **Sedang** ($35 \le \text{Skor} < 60$).
   - **Rendah** ($\text{Skor} < 35$).

## 4. Alasan Keputusan Visual (Aturan R-31 Antislop)

1. **Mengapa palet kertas hangat (`#F6F3EC`), hijau-biru tua (`#0F5C59`), dan satu aksen oranye-bara (`#B83A14`)?** Warna membawa makna fungsional: hijau-biru menandakan fasilitas pertolongan medis, sedangkan aksen oranye-bara khusus menandai bahaya titik panas dan tombol darurat IGD, di atas latar terang yang mudah dibaca di bawah sinar matahari berasap.
2. **Mengapa tata letak peta penuh layar dengan panel samping di kiri (desktop) dan *bottom sheet* (mobile)?** Keputusan utama pengguna adalah spasial (melihat posisi fasilitas relatif terhadap sebaran titik panas), sehingga peta menjadi titik fokus tunggal dan kontrol berada dalam jangkauan ibu jari di ponsel.
3. **Mengapa font *Atkinson Hyperlegible* dengan fallback *system sans-serif*?** Huruf ini dirancang untuk keterbacaan tinggi pada kondisi penglihatan terbatas atau layar terkena kabut asap.
4. **Mengapa jarak antar-elemen rapat dan terstruktur (8-12 px di dalam kartu, 12-16 px antar-kelompok)?** Memungkinkan pengguna memindai 3-4 fasilitas kesehatan sekaligus tanpa menggulir panjang saat kondisi darurat.
5. **Mengapa kartu daftar fasilitas memiliki variasi hierarki (urutan #1 diberi bingkai tebal dan label kandidat rujukan utama)?** Dalam kondisi darurat pernapasan, fasilitas terdekat pertama yang memenuhi syarat adalah rekomendasi tindakan utama sehingga harus langsung menonjol dibanding urutan berikutnya.
6. **Mengapa menggunakan penanda SVG buatan sendiri dengan tiga bentuk geometri berbeda (lingkaran, persegi, segitiga) dan lingkaran konsentris?** Membedakan Rumah Sakit, Puskesmas, dan Klinik berdasarkan bentuk sekaligus warna (ramah buta warna), sedangkan lingkaran konsentris 5/10 km memberikan ukuran skala jarak secara visual di sekitar pengguna.
