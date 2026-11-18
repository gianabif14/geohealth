from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


JenisFaskes = Literal["rumah_sakit", "puskesmas", "klinik", "lainnya"]
SumberFaskes = Literal["osm", "csv", "sampel"]
SumberStatus = Literal["osm", "manual", "simulasi"]
SumberHotspot = Literal["firms", "sampel"]


class StatusFaskesOut(BaseModel):
    buka: bool
    igd_24jam: bool
    dokter_jaga: bool
    oksigen: bool
    tempat_tidur_tersedia: int
    tempat_tidur_total: int
    catatan_layanan: str | None = None
    sumber: SumberStatus
    diperbarui_pada: datetime


class FaskesDetailOut(BaseModel):
    id: int
    osm_id: int | None = None
    nama: str
    jenis: JenisFaskes
    alamat: str | None = None
    telepon: str | None = None
    kabupaten: str | None = None
    sumber: SumberFaskes
    lat: float
    lon: float
    status: StatusFaskesOut
    jarak_m: float | None = None
    azimuth_deg: float | None = None
    arah_kompas: str | None = None


class PrivacyCheckOut(BaseModel):
    dibulatkan_m: int = Field(description="Presisi pembulatan koordinat dalam meter untuk minimisasi data")
    peringatan_akurasi: str | None = None
    peringatan_plausibilitas: str | None = None


class TerdekatResponseOut(BaseModel):
    radius_km: float
    jumlah_ditemukan: int
    hotspot_sekitar_5km: int
    privasi: PrivacyCheckOut
    hasil: list[FaskesDetailOut]


class KabupatenSkorOut(BaseModel):
    id: int
    nama: str
    kode: str
    is_pilot: bool
    jumlah_faskes: int
    jumlah_faskes_siap_igd_oksigen: int
    jumlah_hotspot_7hari: int
    rerata_jarak_faskes_siap_km: float
    skor_akses_terbatas: float
    prioritas_posko: Literal["tinggi", "sedang", "rendah"]


class H3CellSkorOut(BaseModel):
    h3_index: str
    kabupaten: str | None = None
    boundary: list[list[float]]
    centroid_lat: float
    centroid_lon: float
    n_hotspot: int
    jarak_faskes_siap_km: float
    faskes_terdekat_nama: str | None = None
    skor: float
    kategori: Literal["tinggi", "sedang", "rendah"]


class AnalisisAksesResponseOut(BaseModel):
    metodologi: str
    catatan_sumber: str
    kabupaten_ranking: list[KabupatenSkorOut]
    sel_h3: list[H3CellSkorOut]


class MetaResponseOut(BaseModel):
    wilayah_cakupan: str
    kabupaten_pilot: list[str]
    total_faskes: int
    faskes_per_sumber: dict[str, int]
    status_per_sumber: dict[str, int]
    total_hotspot: int
    hotspot_per_sumber: dict[str, int]
    hotspot_terakhir_diperbarui: datetime | None = None
    catatan_transparansi: list[str]
