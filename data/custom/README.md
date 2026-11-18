# Format Impor Dataset Fasilitas Kesehatan (`data/custom/`)

Taruh file `.csv` di folder ini lalu jalankan:

```powershell
python -m etl.import_csv
```

## Kolom Wajib dan Opsional

```csv
nama,jenis,lat,lon,alamat,telepon,igd_24jam,oksigen,dokter_jaga,tt_total,tt_tersedia,catatan_layanan
RSUD Kayuagung,rumah_sakit,-3.3912,104.8305,"Jl. Lintas Timur Sumatera, Kayuagung",(0712) 321010,true,true,true,180,24,Rujukan ISPA OKI
```

- `jenis`: `rumah_sakit`, `puskesmas`, `klinik`, atau `lainnya`
- `lat`, `lon`: Koordinat desimal WGS84 (EPSG:4326) di wilayah Provinsi Sumatera Selatan
- Semua baris yang diimpor dari CSV dengan nilai layanan eksplisit diberi label `sumber = 'manual'`.
