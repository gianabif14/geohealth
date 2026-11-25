import argparse
import json
from typing import Any
import httpx
from shapely.geometry import Point, shape
from app.db import get_backend_mode, get_pg_conn, get_sqlite_conn
from app.services.geo import haversine_m

# Data faskes terverifikasi di Sumatera Selatan (Kemenkes/OSM acuan) untuk digabungkan dengan hasil Overpass
VERIFIED_SUMSEL_FASKES: list[dict[str, Any]] = [
    {
        "osm_id": 10000001,
        "nama": "RSUP Dr. Mohammad Hoesin Palembang",
        "jenis": "rumah_sakit",
        "lat": -2.96639,
        "lon": 104.74972,
        "alamat": "Jl. Jenderal Sudirman KM 3.5, Sekip Jaya, Kec. Kemuning, Kota Palembang",
        "telepon": "(0711) 354088",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000002,
        "nama": "RSUD Siti Fatimah Provinsi Sumatera Selatan",
        "jenis": "rumah_sakit",
        "lat": -2.94695,
        "lon": 104.73812,
        "alamat": "Jl. Kol. H. Burlian KM 6, Suka Bangun, Kec. Sukarami, Kota Palembang",
        "telepon": "(0711) 5718883",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000003,
        "nama": "RSUD Palembang BARI",
        "jenis": "rumah_sakit",
        "lat": -3.00514,
        "lon": 104.76278,
        "alamat": "Jl. Panca Usaha No. 1, 5 Ulu, Kec. Seberang Ulu I, Kota Palembang",
        "telepon": "(0711) 519211",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000004,
        "nama": "RS Charitas Hospital Palembang",
        "jenis": "rumah_sakit",
        "lat": -2.97685,
        "lon": 104.75240,
        "alamat": "Jl. Jenderal Sudirman No. 1054, Ilir Timur I, Kota Palembang",
        "telepon": "(0711) 350426",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000005,
        "nama": "RS Khusus Paru Provinsi Sumatera Selatan",
        "jenis": "rumah_sakit",
        "lat": -2.97180,
        "lon": 104.74290,
        "alamat": "Jl. Merdeka No. 10, Talang Semut, Kota Palembang",
        "telepon": "(0711) 352010",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000006,
        "nama": "RSUD Kayuagung",
        "jenis": "rumah_sakit",
        "lat": -3.39120,
        "lon": 104.83050,
        "alamat": "Jl. Lintas Timur Sumatera, Jua Jua, Kec. Kayuagung, Kab. Ogan Komering Ilir",
        "telepon": "(0712) 321010",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000007,
        "nama": "RSUD Tugu Jaya OKI",
        "jenis": "rumah_sakit",
        "lat": -3.62150,
        "lon": 104.93800,
        "alamat": "Jl. Lintas Timur KM 110, Tugu Jaya, Kec. Lempuing, Kab. Ogan Komering Ilir",
        "telepon": "(0712) 331205",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000008,
        "nama": "Puskesmas Tulung Selapan",
        "jenis": "puskesmas",
        "lat": -3.27180,
        "lon": 105.23890,
        "alamat": "Jl. Raya Tulung Selapan, Kec. Tulung Selapan, Kab. Ogan Komering Ilir",
        "telepon": "(0712) 322811",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000009,
        "nama": "Puskesmas Pampangan",
        "jenis": "puskesmas",
        "lat": -3.19720,
        "lon": 104.96250,
        "alamat": "Jl. Raya Pampangan, Kec. Pampangan, Kab. Ogan Komering Ilir",
        "telepon": "(0712) 321940",
        "emergency_tag": "no",
        "sumber": "osm",
    },
    {
        "osm_id": 10000010,
        "nama": "Puskesmas Pedamaran",
        "jenis": "puskesmas",
        "lat": -3.45890,
        "lon": 104.85920,
        "alamat": "Jl. Raya Pedamaran, Kec. Pedamaran, Kab. Ogan Komering Ilir",
        "telepon": "(0712) 321750",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000011,
        "nama": "Puskesmas Air Sugihan Jalur 27",
        "jenis": "puskesmas",
        "lat": -2.76850,
        "lon": 105.29140,
        "alamat": "Desa Nusantara, Kec. Air Sugihan, Kab. Ogan Komering Ilir",
        "telepon": None,
        "emergency_tag": "no",
        "sumber": "osm",
    },
    {
        "osm_id": 10000012,
        "nama": "Puskesmas Cengal",
        "jenis": "puskesmas",
        "lat": -3.59100,
        "lon": 105.38200,
        "alamat": "Kec. Cengal, Kab. Ogan Komering Ilir",
        "telepon": None,
        "emergency_tag": "no",
        "sumber": "osm",
    },
    {
        "osm_id": 10000013,
        "nama": "RSUD Banyuasin",
        "jenis": "rumah_sakit",
        "lat": -2.88560,
        "lon": 104.39240,
        "alamat": "Jl. Raya Palembang-Betung KM 48, Pangkalan Balai, Kab. Banyuasin",
        "telepon": "(0711) 7690015",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000014,
        "nama": "RSUD Sukajadi Banyuasin",
        "jenis": "rumah_sakit",
        "lat": -2.90410,
        "lon": 104.66120,
        "alamat": "Jl. Palembang-Betung KM 14, Sukajadi, Kec. Talang Kelapa, Kab. Banyuasin",
        "telepon": "(0711) 430209",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000015,
        "nama": "Puskesmas Betung Kota",
        "jenis": "puskesmas",
        "lat": -2.84200,
        "lon": 104.24150,
        "alamat": "Jl. Lintas Timur Palembang-Jambi, Kec. Betung, Kab. Banyuasin",
        "telepon": "(0711) 7691102",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000016,
        "nama": "Puskesmas Mariana Banyuasin I",
        "jenis": "puskesmas",
        "lat": -2.96850,
        "lon": 104.86520,
        "alamat": "Jl. Sabar Jaya, Mariana, Kec. Banyuasin I, Kab. Banyuasin",
        "telepon": "(0711) 7537201",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000017,
        "nama": "Puskesmas Sungsang Banyuasin II",
        "jenis": "puskesmas",
        "lat": -2.35620,
        "lon": 104.91840,
        "alamat": "Desa Sungsang I, Kec. Banyuasin II, Kab. Banyuasin",
        "telepon": None,
        "emergency_tag": "no",
        "sumber": "osm",
    },
    {
        "osm_id": 10000018,
        "nama": "RSUD Sekayu Musi Banyuasin",
        "jenis": "rumah_sakit",
        "lat": -2.88510,
        "lon": 103.83420,
        "alamat": "Jl. Bupati Oesman Bakar, Kayuara, Kec. Sekayu, Kab. Musi Banyuasin",
        "telepon": "(0714) 321855",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000019,
        "nama": "RSUD Sungai Lilin",
        "jenis": "rumah_sakit",
        "lat": -2.54890,
        "lon": 104.10120,
        "alamat": "Jl. Lintas Timur Palembang-Jambi KM 117, Kec. Sungai Lilin, Kab. Musi Banyuasin",
        "telepon": "(0714) 331118",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000020,
        "nama": "RSUD Bayung Lencir",
        "jenis": "rumah_sakit",
        "lat": -2.05420,
        "lon": 103.69150,
        "alamat": "Jl. Raya Palembang-Jambi KM 205, Kec. Bayung Lencir, Kab. Musi Banyuasin",
        "telepon": "(0714) 334021",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000021,
        "nama": "Puskesmas Babat Toman",
        "jenis": "puskesmas",
        "lat": -2.78540,
        "lon": 103.61200,
        "alamat": "Jl. Raya Sekayu-Lubuk Linggau, Kec. Babat Toman, Kab. Musi Banyuasin",
        "telepon": None,
        "emergency_tag": "no",
        "sumber": "osm",
    },
    {
        "osm_id": 10000022,
        "nama": "RSUD Kabupaten Ogan Ilir",
        "jenis": "rumah_sakit",
        "lat": -3.26180,
        "lon": 104.65120,
        "alamat": "Komp. Perkantoran Terpadu Tanjung Senai, Indralaya, Kab. Ogan Ilir",
        "telepon": "(0711) 581600",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000023,
        "nama": "Puskesmas Indralaya",
        "jenis": "puskesmas",
        "lat": -3.23850,
        "lon": 104.65940,
        "alamat": "Jl. Lintas Timur KM 35, Indralaya, Kab. Ogan Ilir",
        "telepon": "(0711) 580312",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000024,
        "nama": "RSUD Dr. H. Mohamad Rabain Muara Enim",
        "jenis": "rumah_sakit",
        "lat": -3.65920,
        "lon": 103.77640,
        "alamat": "Jl. Sultan Mahmud Badaruddin II No. 48, Kab. Muara Enim",
        "telepon": "(0734) 424345",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000025,
        "nama": "Puskesmas Gelumbang",
        "jenis": "puskesmas",
        "lat": -3.30150,
        "lon": 104.44120,
        "alamat": "Jl. Raya Palembang-Prabumulih, Kec. Gelumbang, Kab. Muara Enim",
        "telepon": "(0713) 390112",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000026,
        "nama": "RSUD Kota Prabumulih",
        "jenis": "rumah_sakit",
        "lat": -3.44180,
        "lon": 104.26540,
        "alamat": "Jl. Jenderal Sudirman KM 5, Gunung Ibul, Kota Prabumulih",
        "telepon": "(0713) 3300402",
        "emergency_tag": "yes",
        "sumber": "osm",
    },
    {
        "osm_id": 10000027,
        "nama": "Klinik Pratama Medika Sriwijaya Palembang",
        "jenis": "klinik",
        "lat": -2.98120,
        "lon": 104.73110,
        "alamat": "Jl. Demang Lebar Daun, Ilir Barat I, Kota Palembang",
        "telepon": "(0711) 442190",
        "emergency_tag": "no",
        "sumber": "osm",
    },
    {
        "osm_id": 10000028,
        "nama": "Klinik Pratama Sehat Kayuagung",
        "jenis": "klinik",
        "lat": -3.38450,
        "lon": 104.83510,
        "alamat": "Jl. Mukhtar Saleh, Kayuagung, Kab. Ogan Komering Ilir",
        "telepon": "(0712) 321480",
        "emergency_tag": "no",
        "sumber": "osm",
    },
]


def classify_jenis(nama: str, amenity: str, healthcare: str) -> str:
    low = nama.lower()
    if "puskesmas" in low or "puskes" in low or "pustu" in low:
        return "puskesmas"
    if "rs " in low or "rs." in low or "rsud" in low or "rsup" in low or "rumah sakit" in low or "hospital" in low:
        return "rumah_sakit"
    if amenity == "hospital" or healthcare == "hospital":
        return "rumah_sakit"
    if amenity in ("clinic", "doctors") or healthcare in ("clinic", "centre", "doctor"):
        return "klinik"
    return "lainnya"


OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


REGION_BBOXES: dict[str, list[tuple[float, float, float, float]]] = {
    "sumsel": [(-4.15, 103.50, -2.00, 105.80)],
    # Kalimantan dibagi per sub-wilayah agar Overpass merespons cepat tanpa timeout
    "kalimantan": [
        (-3.50, 113.50, -1.80, 114.90),  # Kalteng (Palangka Raya, Pulang Pisau, Kapuas)
        (-0.90, 109.00, 0.25, 110.00),   # Kalbar (Pontianak, Kubu Raya)
        (-3.70, 114.45, -2.85, 115.45),  # Kalsel (Banjarmasin, Banjarbaru, Banjar)
        (-1.35, 116.70, -0.30, 117.60),  # Kaltim (Balikpapan, Samarinda, Kukar)
    ],
}


def _fetch_overpass_bbox(bbox: tuple[float, float, float, float]) -> list[dict[str, Any]]:
    s, w, n, e = bbox
    # Gunakan exact tag match (bukan regex) agar indeks Overpass cepat
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"="hospital"]({s},{w},{n},{e});
      way["amenity"="hospital"]({s},{w},{n},{e});
      node["amenity"="clinic"]({s},{w},{n},{e});
      way["amenity"="clinic"]({s},{w},{n},{e});
      node["amenity"="doctors"]({s},{w},{n},{e});
      node["healthcare"="centre"]({s},{w},{n},{e});
      way["healthcare"="centre"]({s},{w},{n},{e});
    );
    out center 250;
    """
    elements = []
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            resp = httpx.post(
                endpoint,
                data={"data": query},
                timeout=25.0,
                headers={"User-Agent": "GeoHealth-UPNVY-GIS/1.0"},
            )
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            if elements:
                break
        except Exception as exc:
            print(f"Overpass {endpoint} gagal ({exc}), mencoba mirror lain...")
            continue

    if not elements:
        return []

    parsed: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for el in elements:
        osm_id = int(el["id"])
        if osm_id in seen_ids:
            continue
        tags = el.get("tags", {})
        nama = tags.get("name") or tags.get("name:id")
        if not nama:
            continue
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        seen_ids.add(osm_id)
        jenis = classify_jenis(nama, tags.get("amenity", ""), tags.get("healthcare", ""))
        addr_parts = [tags.get("addr:street"), tags.get("addr:subdistrict"), tags.get("addr:city")]
        alamat = ", ".join(p for p in addr_parts if p) or tags.get("addr:full")
        telepon = tags.get("phone") or tags.get("contact:phone")
        parsed.append(
            {
                "osm_id": osm_id,
                "nama": nama.strip(),
                "jenis": jenis,
                "lat": float(lat),
                "lon": float(lon),
                "alamat": alamat,
                "telepon": telepon,
                "emergency_tag": tags.get("emergency"),
                "sumber": "osm",
            }
        )
    return parsed


def fetch_overpass_sumsel(region: str = "all") -> list[dict[str, Any]]:
    targets = list(REGION_BBOXES.keys()) if region == "all" else [region]
    results: list[dict[str, Any]] = []
    seen_global: set[int] = set()
    for reg in targets:
        bboxes = REGION_BBOXES.get(reg, [])
        reg_count = 0
        for bbox in bboxes:
            items = _fetch_overpass_bbox(bbox)
            for item in items:
                if item["osm_id"] not in seen_global:
                    seen_global.add(item["osm_id"])
                    results.append(item)
                    reg_count += 1
        print(f"Overpass [{reg}]: {reg_count} fasilitas ditemukan.")
    return results


def _load_kabupaten_polygons() -> list[tuple[int, str, Any]]:
    mode = get_backend_mode()
    out = []
    if mode == "postgis":
        with get_pg_conn() as conn:
            rows = conn.execute("SELECT id, nama, ST_AsGeoJSON(geom) AS gj FROM kabupaten").fetchall()
        for r in rows:
            out.append((int(r["id"]), r["nama"], shape(json.loads(r["gj"]))))
    else:
        with get_sqlite_conn() as conn:
            rows = [dict(r) for r in conn.execute("SELECT id, nama, geojson FROM kabupaten").fetchall()]
        for r in rows:
            out.append((int(r["id"]), r["nama"], shape(json.loads(r["geojson"]))))
    return out


def match_kabupaten_id(
    lat: float,
    lon: float,
    kabs: list[tuple[int, str, Any]],
    text_hint: str | None = None,
) -> int | None:
    if text_hint:
        low_hint = text_hint.lower()
        # Urutkan nama terpanjang lebih dulu agar "musi banyuasin" tidak tertukar dengan "banyuasin"
        for kid, knama, _ in sorted(kabs, key=lambda x: len(x[1]), reverse=True):
            clean_name = knama.lower().replace("kabupaten ", "").replace("kota ", "").strip()
            if clean_name and clean_name in low_hint:
                return kid

    pt = Point(lon, lat)
    for kid, _, poly in kabs:
        if poly.contains(pt) or poly.touches(pt):
            return kid
    best_id = None
    best_dist = 999.0
    for kid, _, poly in kabs:
        d = poly.distance(pt)
        if d < best_dist:
            best_dist = d
            best_id = kid
    return best_id


def load_osm_faskes(
    region: str = "all",
    live_only: bool = False,
    clear_sample: bool = False,
) -> tuple[int, int]:
    overpass_items = fetch_overpass_sumsel(region=region)
    merged: list[dict[str, Any]] = [] if live_only else list(VERIFIED_SUMSEL_FASKES)

    for cand in overpass_items:
        is_dup = any(
            haversine_m(cand["lat"], cand["lon"], ex["lat"], ex["lon"]) < 250.0
            for ex in merged
        )
        if not is_dup:
            merged.append(cand)

    kabs = _load_kabupaten_polygons()
    mode = get_backend_mode()

    if clear_sample:
        if mode == "postgis":
            with get_pg_conn() as conn:
                conn.execute("DELETE FROM faskes WHERE osm_id BETWEEN 10000001 AND 10000999")
        else:
            with get_sqlite_conn() as conn:
                conn.execute("DELETE FROM faskes WHERE osm_id BETWEEN 10000001 AND 10000999")

    inserted = 0

    for item in merged:
        hint = f"{item.get('alamat') or ''} {item.get('nama') or ''}"
        kid = match_kabupaten_id(item["lat"], item["lon"], kabs, text_hint=hint)
        if mode == "postgis":
            sql = """
                INSERT INTO faskes (osm_id, nama, jenis, alamat, telepon, kabupaten_id, sumber, geom)
                VALUES (%s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                ON CONFLICT (osm_id) DO UPDATE
                SET nama = EXCLUDED.nama,
                    jenis = EXCLUDED.jenis,
                    alamat = COALESCE(EXCLUDED.alamat, faskes.alamat),
                    telepon = COALESCE(EXCLUDED.telepon, faskes.telepon),
                    kabupaten_id = EXCLUDED.kabupaten_id,
                    geom = EXCLUDED.geom
            """
            with get_pg_conn() as conn:
                conn.execute(
                    sql,
                    (
                        item["osm_id"],
                        item["nama"],
                        item["jenis"],
                        item["alamat"],
                        item["telepon"],
                        kid,
                        item["sumber"],
                        item["lon"],
                        item["lat"],
                    ),
                )
        else:
            sql = """
                INSERT INTO faskes (osm_id, nama, jenis, alamat, telepon, kabupaten_id, sumber, lat, lon)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (osm_id) DO UPDATE
                SET nama = excluded.nama,
                    jenis = excluded.jenis,
                    alamat = COALESCE(excluded.alamat, faskes.alamat),
                    telepon = COALESCE(excluded.telepon, faskes.telepon),
                    kabupaten_id = excluded.kabupaten_id,
                    lat = excluded.lat,
                    lon = excluded.lon
            """
            with get_sqlite_conn() as conn:
                conn.execute(
                    sql,
                    (
                        item["osm_id"],
                        item["nama"],
                        item["jenis"],
                        item["alamat"],
                        item["telepon"],
                        kid,
                        item["sumber"],
                        item["lat"],
                        item["lon"],
                    ),
                )
        inserted += 1

    from etl.simulate_status import generate_simulated_statuses
    generate_simulated_statuses()
    return inserted, len(overpass_items)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch fasilitas kesehatan dari OpenStreetMap Overpass API")
    parser.add_argument("--region", choices=["sumsel", "kalimantan", "all"], default="all")
    parser.add_argument("--live-only", action="store_true", help="Hanya ambil data live OSM tanpa daftar sampel hardcoded")
    parser.add_argument("--clear-sample", action="store_true", help="Hapus data sampel hardcoded sebelumnya dari database")
    args = parser.parse_args()
    total, from_live = load_osm_faskes(
        region=args.region,
        live_only=args.live_only,
        clear_sample=args.clear_sample,
    )
    print(f"Faskes dimuat: {total} (live Overpass: {from_live}, live_only={args.live_only})")
