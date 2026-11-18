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
        "coords": [[(104.62, -3.08), (104.86, -3.08), (104.86, -2.86), (104.62, -2.86), (104.62, -3.08)]],
    },
    {
        "nama": "Kabupaten Ogan Komering Ilir",
        "kode": "ID-SS-02",
        "is_pilot": True,
        "coords": [[(104.70, -4.15), (106.05, -4.15), (106.05, -2.90), (104.86, -2.90), (104.86, -3.08), (104.70, -3.08), (104.70, -4.15)]],
    },
    {
        "nama": "Kabupaten Banyuasin",
        "kode": "ID-SS-07",
        "is_pilot": True,
        "coords": [[(104.25, -2.86), (105.45, -2.86), (105.45, -1.75), (104.25, -1.75), (104.25, -2.86)]],
    },
    {
        "nama": "Kabupaten Musi Banyuasin",
        "kode": "ID-SS-06",
        "is_pilot": True,
        "coords": [[(103.20, -3.05), (104.25, -3.05), (104.25, -1.70), (103.20, -1.70), (103.20, -3.05)]],
    },
    {
        "nama": "Kabupaten Ogan Ilir",
        "kode": "ID-SS-10",
        "is_pilot": False,
        "coords": [[(104.30, -3.65), (104.70, -3.65), (104.70, -3.08), (104.30, -3.08), (104.30, -3.65)]],
    },
    {
        "nama": "Kabupaten Muara Enim",
        "kode": "ID-SS-03",
        "is_pilot": False,
        "coords": [[(103.45, -4.25), (104.30, -4.25), (104.30, -3.08), (103.45, -3.08), (103.45, -4.25)]],
    },
    {
        "nama": "Kota Prabumulih",
        "kode": "ID-SS-74",
        "is_pilot": False,
        "coords": [[(104.12, -3.52), (104.32, -3.52), (104.32, -3.34), (104.12, -3.34), (104.12, -3.52)]],
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
