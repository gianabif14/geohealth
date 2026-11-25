import json
from pathlib import Path
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from app.db import get_backend_mode, get_pg_conn, get_sqlite_conn

ADMIN_GEOJSON_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "admin" / "kabupaten_indonesia.geojson"
)

# Fallback minimal jika file GeoJSON nasional belum tersedia
FALLBACK_KABUPATEN_DATA = [
    {
        "nama": "Kota Palembang",
        "kode": "ID-1671",
        "provinsi": "Sumatera Selatan",
        "is_pilot": True,
        "coords": [[(104.64, -3.06), (104.83, -3.06), (104.83, -2.87), (104.64, -2.87), (104.64, -3.06)]],
    },
    {
        "nama": "Kabupaten Ogan Komering Ilir",
        "kode": "ID-1602",
        "provinsi": "Sumatera Selatan",
        "is_pilot": True,
        "coords": [[
            (104.72, -4.15), (106.05, -4.15), (106.05, -2.65),
            (105.10, -2.65), (105.00, -3.06), (104.72, -3.06), (104.72, -4.15)
        ]],
    },
    {
        "nama": "Kabupaten Banyuasin",
        "kode": "ID-1607",
        "provinsi": "Sumatera Selatan",
        "is_pilot": True,
        "coords": [[
            (104.20, -2.95), (104.64, -2.95), (104.64, -2.87), (104.83, -2.87),
            (104.83, -3.02), (105.00, -3.02), (105.10, -2.65), (105.45, -2.65),
            (105.45, -1.75), (104.20, -1.75), (104.20, -2.95)
        ]],
    },
    {
        "nama": "Kabupaten Musi Banyuasin",
        "kode": "ID-1606",
        "provinsi": "Sumatera Selatan",
        "is_pilot": True,
        "coords": [[(103.20, -3.05), (104.20, -3.05), (104.20, -1.70), (103.20, -1.70), (103.20, -3.05)]],
    },
]


def _ensure_multipolygon_geojson(geom_dict: dict) -> str:
    geom = shape(geom_dict)
    if isinstance(geom, Polygon):
        geom = MultiPolygon([geom])
    elif not isinstance(geom, MultiPolygon):
        polys = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]
        geom = MultiPolygon(polys)
    return json.dumps(mapping(geom), separators=(",", ":"))


def _ensure_provinsi_column(mode: str) -> None:
    if mode == "postgis":
        with get_pg_conn() as conn:
            conn.execute("ALTER TABLE kabupaten ADD COLUMN IF NOT EXISTS provinsi TEXT")
    else:
        with get_sqlite_conn() as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(kabupaten)").fetchall()]
            if "provinsi" not in cols:
                conn.execute("ALTER TABLE kabupaten ADD COLUMN provinsi TEXT")


def _iter_admin_records() -> list[dict]:
    if ADMIN_GEOJSON_PATH.exists():
        raw = json.loads(ADMIN_GEOJSON_PATH.read_text(encoding="utf-8"))
        records = []
        for feat in raw.get("features", []):
            props = feat.get("properties") or {}
            geom = feat.get("geometry")
            if not geom or not props.get("nama") or not props.get("kode"):
                continue
            records.append(
                {
                    "nama": str(props["nama"]).strip(),
                    "kode": str(props["kode"]).strip(),
                    "provinsi": str(props.get("provinsi") or "").strip() or None,
                    "is_pilot": bool(props.get("is_pilot", False)),
                    "gj_str": _ensure_multipolygon_geojson(geom),
                }
            )
        if records:
            return records

    fallback_records = []
    for item in FALLBACK_KABUPATEN_DATA:
        poly = MultiPolygon([Polygon(ring) for ring in item["coords"]])
        fallback_records.append(
            {
                "nama": item["nama"],
                "kode": item["kode"],
                "provinsi": item.get("provinsi"),
                "is_pilot": bool(item["is_pilot"]),
                "gj_str": json.dumps(mapping(poly), separators=(",", ":")),
            }
        )
    return fallback_records


def load_admin_boundaries(clear_legacy: bool = True) -> int:
    mode = get_backend_mode()
    _ensure_provinsi_column(mode)
    records = _iter_admin_records()
    active_codes = {r["kode"] for r in records}

    if mode == "postgis":
        sql = """
            INSERT INTO kabupaten (nama, kode, provinsi, is_pilot, geom)
            VALUES (%s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
            ON CONFLICT (kode) DO UPDATE
            SET nama = EXCLUDED.nama,
                provinsi = EXCLUDED.provinsi,
                is_pilot = EXCLUDED.is_pilot,
                geom = EXCLUDED.geom
        """
        with get_pg_conn() as conn:
            for rec in records:
                conn.execute(
                    sql,
                    (rec["nama"], rec["kode"], rec["provinsi"], rec["is_pilot"], rec["gj_str"]),
                )
            if clear_legacy and len(active_codes) > 20:
                conn.execute(
                    "DELETE FROM kabupaten WHERE kode LIKE 'ID-SS-%' OR kode LIKE 'ID-KT-%' OR kode LIKE 'ID-KB-%' OR kode LIKE 'ID-KS-%' OR kode LIKE 'ID-KI-%'"
                )
    else:
        sql = """
            INSERT INTO kabupaten (nama, kode, provinsi, is_pilot, geojson)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (kode) DO UPDATE
            SET nama = excluded.nama,
                provinsi = excluded.provinsi,
                is_pilot = excluded.is_pilot,
                geojson = excluded.geojson
        """
        with get_sqlite_conn() as conn:
            for rec in records:
                conn.execute(
                    sql,
                    (
                        rec["nama"],
                        rec["kode"],
                        rec["provinsi"],
                        1 if rec["is_pilot"] else 0,
                        rec["gj_str"],
                    ),
                )
            if clear_legacy and len(active_codes) > 20:
                conn.execute(
                    "DELETE FROM kabupaten WHERE kode LIKE 'ID-SS-%' OR kode LIKE 'ID-KT-%' OR kode LIKE 'ID-KB-%' OR kode LIKE 'ID-KS-%' OR kode LIKE 'ID-KI-%'"
                )

    return len(records)


if __name__ == "__main__":
    n = load_admin_boundaries()
    print(f"Berhasil memuat {n} wilayah kabupaten/kota Indonesia.")
