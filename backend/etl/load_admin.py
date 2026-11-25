import json
from shapely.geometry import MultiPolygon, Polygon, mapping
from app.db import get_backend_mode, get_pg_conn, get_sqlite_conn

# Batas poligon pendekatan tingkat Kabupaten/Kota Sumatera Selatan (WGS84 EPSG:4326)
# Mencakup 4 wilayah pilot prioritas karhutla + kabupaten sekitar di Sumsel
KABUPATEN_DATA = [
    {
        "nama": "Kota Palembang",
        "kode": "ID-SS-71",
        "is_pilot": True,
        "coords": [[(104.64, -3.06), (104.83, -3.06), (104.83, -2.87), (104.64, -2.87), (104.64, -3.06)]],
    },
    {
        "nama": "Kabupaten Ogan Komering Ilir",
        "kode": "ID-SS-02",
        "is_pilot": True,
        "coords": [[
            (104.72, -4.15), (106.05, -4.15), (106.05, -2.65),
            (105.10, -2.65), (105.00, -3.06), (104.72, -3.06), (104.72, -4.15)
        ]],
    },
    {
        "nama": "Kabupaten Banyuasin",
        "kode": "ID-SS-07",
        "is_pilot": True,
        "coords": [[
            (104.20, -2.95), (104.64, -2.95), (104.64, -2.87), (104.83, -2.87),
            (104.83, -3.02), (105.00, -3.02), (105.10, -2.65), (105.45, -2.65),
            (105.45, -1.75), (104.20, -1.75), (104.20, -2.95)
        ]],
    },
    {
        "nama": "Kabupaten Musi Banyuasin",
        "kode": "ID-SS-06",
        "is_pilot": True,
        "coords": [[(103.20, -3.05), (104.20, -3.05), (104.20, -1.70), (103.20, -1.70), (103.20, -3.05)]],
    },
    {
        "nama": "Kabupaten Ogan Ilir",
        "kode": "ID-SS-10",
        "is_pilot": False,
        "coords": [[(104.48, -3.65), (104.72, -3.65), (104.72, -3.06), (104.48, -3.06), (104.48, -3.65)]],
    },
    {
        "nama": "Kabupaten Muara Enim",
        "kode": "ID-SS-03",
        "is_pilot": False,
        "coords": [[(103.45, -4.25), (104.48, -4.25), (104.48, -3.08), (103.45, -3.08), (103.45, -4.25)]],
    },
    {
        "nama": "Kota Prabumulih",
        "kode": "ID-SS-74",
        "is_pilot": False,
        "coords": [[(104.15, -3.50), (104.32, -3.50), (104.32, -3.36), (104.15, -3.36), (104.15, -3.50)]],
    },
    # Wilayah Kalimantan (Kalbar, Kalteng, Kalsel, Kaltim)
    {
        "nama": "Kota Palangka Raya",
        "kode": "ID-KT-71",
        "is_pilot": True,
        "coords": [[(113.70, -2.40), (114.15, -2.40), (114.15, -1.85), (113.70, -1.85), (113.70, -2.40)]],
    },
    {
        "nama": "Kabupaten Pulang Pisau",
        "kode": "ID-KT-11",
        "is_pilot": True,
        "coords": [[(113.60, -3.45), (114.45, -3.45), (114.45, -2.40), (113.60, -2.40), (113.60, -3.45)]],
    },
    {
        "nama": "Kabupaten Kapuas",
        "kode": "ID-KT-03",
        "is_pilot": False,
        "coords": [[(114.15, -3.45), (114.85, -3.45), (114.85, -1.50), (114.15, -1.50), (114.15, -3.45)]],
    },
    {
        "nama": "Kota Pontianak",
        "kode": "ID-KB-71",
        "is_pilot": True,
        "coords": [[(109.25, -0.15), (109.42, -0.15), (109.42, 0.05), (109.25, 0.05), (109.25, -0.15)]],
    },
    {
        "nama": "Kabupaten Kubu Raya",
        "kode": "ID-KB-12",
        "is_pilot": True,
        "coords": [[(109.05, -0.85), (109.95, -0.85), (109.95, 0.15), (109.05, 0.15), (109.05, -0.85)]],
    },
    {
        "nama": "Kota Banjarmasin",
        "kode": "ID-KS-71",
        "is_pilot": False,
        "coords": [[(114.52, -3.40), (114.66, -3.40), (114.66, -3.26), (114.52, -3.26), (114.52, -3.40)]],
    },
    {
        "nama": "Kabupaten Banjar",
        "kode": "ID-KS-03",
        "is_pilot": False,
        "coords": [[(114.66, -3.65), (115.40, -3.65), (115.40, -2.90), (114.66, -2.90), (114.66, -3.65)]],
    },
    {
        "nama": "Kota Samarinda",
        "kode": "ID-KI-72",
        "is_pilot": False,
        "coords": [[(117.05, -0.62), (117.30, -0.62), (117.30, -0.35), (117.05, -0.35), (117.05, -0.62)]],
    },
    {
        "nama": "Kabupaten Kutai Kartanegara",
        "kode": "ID-KI-02",
        "is_pilot": False,
        "coords": [[(116.10, -1.20), (117.50, -1.20), (117.50, 0.40), (116.10, 0.40), (116.10, -1.20)]],
    },
]


def load_admin_boundaries() -> int:
    mode = get_backend_mode()
    count = 0
    for item in KABUPATEN_DATA:
        poly = MultiPolygon([Polygon(ring) for ring in item["coords"]])
        gj_str = json.dumps(mapping(poly))
        if mode == "postgis":
            sql = """
                INSERT INTO kabupaten (nama, kode, is_pilot, geom)
                VALUES (%s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                ON CONFLICT (kode) DO UPDATE
                SET nama = EXCLUDED.nama,
                    is_pilot = EXCLUDED.is_pilot,
                    geom = EXCLUDED.geom
            """
            with get_pg_conn() as conn:
                conn.execute(sql, (item["nama"], item["kode"], item["is_pilot"], gj_str))
        else:
            sql = """
                INSERT INTO kabupaten (nama, kode, is_pilot, geojson)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (kode) DO UPDATE
                SET nama = excluded.nama,
                    is_pilot = excluded.is_pilot,
                    geojson = excluded.geojson
            """
            with get_sqlite_conn() as conn:
                conn.execute(sql, (item["nama"], item["kode"], 1 if item["is_pilot"] else 0, gj_str))
        count += 1
    return count


if __name__ == "__main__":
    n = load_admin_boundaries()
    print(f"Berhasil memuat {n} wilayah kabupaten/kota Sumatera Selatan.")
