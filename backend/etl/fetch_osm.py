import argparse
import json
import time
from pathlib import Path
from typing import Any
import httpx
from shapely.geometry import Point, shape
from shapely.strtree import STRtree
from app.db import get_backend_mode, get_pg_conn, get_sqlite_conn
from app.services.geo import haversine_m

CHECKPOINT_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "cache" / "osm_overpass_checkpoint.json"
)

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

# Bounding box koridor utama 38 provinsi Indonesia (s, w, n, e) untuk loop Overpass
PROVINCE_BBOXES: dict[str, tuple[float, float, float, float]] = {
    "aceh": (5.45, 95.25, 5.62, 95.42),
    "sumut": (3.48, 98.58, 3.68, 98.76),
    "sumbar": (-1.02, 100.30, -0.85, 100.45),
    "riau": (0.42, 101.36, 0.58, 101.52),
    "kepri": (1.05, 103.90, 1.18, 104.10),
    "jambi": (-1.68, 103.52, -1.54, 103.68),
    "bengkulu": (-3.86, 102.24, -3.75, 102.35),
    "sumsel": (-3.45, 104.65, -2.88, 104.88),
    "babel": (-2.18, 106.06, -2.08, 106.18),
    "lampung": (-5.46, 105.20, -5.35, 105.32),
    "banten": (-6.22, 106.12, -6.08, 106.25),
    "dki_jakarta": (-6.30, 106.75, -6.12, 106.92),
    "jabar": (-6.96, 107.55, -6.85, 107.68),
    "jateng": (-7.04, 110.36, -6.94, 110.48),
    "diy": (-7.84, 110.33, -7.74, 110.43),
    "jatim": (-7.34, 112.68, -7.22, 112.80),
    "bali": (-8.72, 115.16, -8.62, 115.26),
    "ntb": (-8.64, 116.07, -8.55, 116.17),
    "ntt": (-10.22, 123.54, -10.12, 123.66),
    "kalbar": (-0.12, 109.25, 0.05, 109.45),
    "kalteng": (-2.30, 113.84, -2.12, 114.00),
    "kalsel": (-3.48, 114.52, -3.25, 114.86),
    "kaltim": (-0.58, 117.06, -0.42, 117.22),
    "kaltara": (3.26, 117.54, 3.36, 117.65),
    "sulut": (1.42, 124.78, 1.54, 124.88),
    "gorontalo": (0.50, 123.02, 0.60, 123.12),
    "sulteng": (-0.95, 119.82, -0.82, 119.94),
    "sulbar": (-2.72, 118.84, -2.64, 118.94),
    "sulsel": (-5.20, 119.38, -5.08, 119.52),
    "sultra": (-4.06, 122.46, -3.95, 122.58),
    "maluku": (-3.74, 128.14, -3.62, 128.24),
    "malut": (0.74, 127.32, 0.84, 127.42),
    "papua_barat": (-0.92, 134.00, -0.82, 134.10),
    "papua_barat_daya": (-0.94, 131.22, -0.84, 131.34),
    "papua": (-2.64, 140.64, -2.50, 140.76),
    "papua_tengah": (-3.42, 135.45, -3.32, 135.56),
    "papua_pegunungan": (-4.14, 138.90, -4.05, 139.00),
    "papua_selatan": (-8.55, 140.35, -8.45, 140.45),
}

REGION_BBOXES: dict[str, list[tuple[float, float, float, float]]] = {
    "sumsel": [PROVINCE_BBOXES["sumsel"]],
    "kalimantan": [
        PROVINCE_BBOXES["kalteng"],
        PROVINCE_BBOXES["kalbar"],
        PROVINCE_BBOXES["kalsel"],
        PROVINCE_BBOXES["kaltim"],
    ],
    "indonesia": list(PROVINCE_BBOXES.values()),
}


def _fetch_overpass_bbox(bbox: tuple[float, float, float, float], timeout_s: float = 15.0) -> list[dict[str, Any]]:
    s, w, n, e = bbox
    query = f"""
    [out:json][timeout:15];
    (
      node["amenity"="hospital"]({s},{w},{n},{e});
      way["amenity"="hospital"]({s},{w},{n},{e});
      node["amenity"="clinic"]({s},{w},{n},{e});
      way["amenity"="clinic"]({s},{w},{n},{e});
      node["amenity"="doctors"]({s},{w},{n},{e});
      node["healthcare"="centre"]({s},{w},{n},{e});
      way["healthcare"="centre"]({s},{w},{n},{e});
    );
    out center 200;
    """
    elements = []
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            resp = httpx.post(
                endpoint,
                data={"data": query},
                timeout=timeout_s,
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


def _load_checkpoint() -> dict[str, list[dict[str, Any]]]:
    if CHECKPOINT_PATH.exists():
        try:
            return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_checkpoint(data: dict[str, list[dict[str, Any]]]) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_overpass_sumsel(
    region: str = "priority",
    rate_limit_sec: float = 0.6,
    resume_checkpoint: bool = True,
) -> list[dict[str, Any]]:
    if region == "indonesia" or region == "all_38":
        target_map = {k: [v] for k, v in PROVINCE_BBOXES.items()}
    elif region == "all" or region == "priority":
        target_map = {
            "sumsel": REGION_BBOXES["sumsel"],
            "kalimantan": REGION_BBOXES["kalimantan"],
        }
    elif region in PROVINCE_BBOXES:
        target_map = {region: [PROVINCE_BBOXES[region]]}
    else:
        target_map = {region: REGION_BBOXES.get(region, [])}

    checkpoint = _load_checkpoint() if resume_checkpoint else {}
    results: list[dict[str, Any]] = []
    seen_global: set[int] = set()

    for reg, bboxes in target_map.items():
        if resume_checkpoint and reg in checkpoint and checkpoint[reg]:
            cached_items = checkpoint[reg]
            for item in cached_items:
                if item["osm_id"] not in seen_global:
                    seen_global.add(item["osm_id"])
                    results.append(item)
            print(f"Overpass [{reg}]: {len(cached_items)} fasilitas dimuat dari checkpoint.")
            continue

        reg_items: list[dict[str, Any]] = []
        for idx, bbox in enumerate(bboxes):
            items = _fetch_overpass_bbox(bbox)
            for item in items:
                if item["osm_id"] not in seen_global:
                    seen_global.add(item["osm_id"])
                    results.append(item)
                reg_items.append(item)
            if idx < len(bboxes) - 1 and rate_limit_sec > 0:
                time.sleep(rate_limit_sec)

        if reg_items:
            checkpoint[reg] = reg_items
            _save_checkpoint(checkpoint)
        print(f"Overpass [{reg}]: {len(reg_items)} fasilitas ditemukan.")
        if rate_limit_sec > 0 and len(target_map) > 2:
            time.sleep(rate_limit_sec)

    return results


_KAB_INDEX_CACHE: dict[int, tuple[STRtree, list[tuple[int, str, str]], list[tuple[int, str, Any]]]] = {}


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


def _get_kabupaten_spatial_index(
    kabs: list[tuple[int, str, Any]]
) -> tuple[STRtree, list[tuple[int, str, str]], list[tuple[int, str, Any]]]:
    cache_key = id(kabs)
    if cache_key in _KAB_INDEX_CACHE:
        return _KAB_INDEX_CACHE[cache_key]
    polys = [poly for _, _, poly in kabs]
    tree = STRtree(polys)
    sorted_names = [
        (kid, knama, knama.lower().strip())
        for kid, knama, _ in sorted(kabs, key=lambda x: len(x[1]), reverse=True)
    ] + [
        (kid, knama, knama.lower().replace("kabupaten ", "").replace("kota ", "").strip())
        for kid, knama, _ in sorted(kabs, key=lambda x: len(x[1]), reverse=True)
    ]
    _KAB_INDEX_CACHE.clear()
    _KAB_INDEX_CACHE[cache_key] = (tree, sorted_names, kabs)
    return tree, sorted_names, kabs


def match_kabupaten_id(
    lat: float,
    lon: float,
    kabs: list[tuple[int, str, Any]],
    text_hint: str | None = None,
) -> int | None:
    if not kabs:
        return None

    tree, sorted_names, _ = _get_kabupaten_spatial_index(kabs)

    if text_hint:
        low_hint = text_hint.lower()
        for kid, _, clean_name in sorted_names:
            if clean_name and clean_name in low_hint:
                return kid

    pt = Point(lon, lat)
    cand_idxs = tree.query(pt)
    for idx in cand_idxs:
        kid, _, poly = kabs[int(idx)]
        if poly.contains(pt) or poly.touches(pt):
            return kid

    # Gunakan STRtree buffer 0.25 derajat (~28 km) untuk mencari poligon terdekat secara cepat
    near_idxs = tree.query(pt.buffer(0.25))
    best_id = None
    best_dist = 0.25
    for idx in near_idxs:
        kid, _, poly = kabs[int(idx)]
        d = poly.distance(pt)
        if d < best_dist:
            best_dist = d
            best_id = kid
    return best_id


def load_osm_faskes(
    region: str = "priority",
    live_only: bool = False,
    clear_sample: bool = False,
    skip_overpass: bool = False,
) -> tuple[int, int]:
    overpass_items = [] if skip_overpass else fetch_overpass_sumsel(region=region)
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
    parser.add_argument(
        "--region",
        default="priority",
        help="Pilihan: priority (Sumsel+Kalimantan), indonesia (38 provinsi), atau kode provinsi",
    )
    parser.add_argument("--live-only", action="store_true", help="Hanya ambil data live OSM tanpa daftar sampel hardcoded")
    parser.add_argument("--clear-sample", action="store_true", help="Hapus data sampel hardcoded sebelumnya dari database")
    parser.add_argument("--skip-overpass", action="store_true", help="Lewati pemanggilan Overpass live")
    args = parser.parse_args()
    total, from_live = load_osm_faskes(
        region=args.region,
        live_only=args.live_only,
        clear_sample=args.clear_sample,
        skip_overpass=args.skip_overpass,
    )
    print(f"Faskes dimuat: {total} (live Overpass: {from_live}, live_only={args.live_only})")
