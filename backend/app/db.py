import atexit
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from app.config import settings
from app.services.geo import azimuth_to_compass, geodesic_inverse, haversine_m

_pg_pool: ConnectionPool | None = None
_backend_mode: str | None = None  # "postgis" | "sqlite_spatial"
SQLITE_PATH = Path(__file__).resolve().parents[2] / "data" / "geohealth_local.sqlite"


def close_pools() -> None:
    global _pg_pool
    if _pg_pool is not None:
        try:
            _pg_pool.close()
        except Exception:
            pass
        _pg_pool = None


atexit.register(close_pools)


def get_backend_mode() -> str:
    global _backend_mode, _pg_pool
    if _backend_mode is not None:
        return _backend_mode
    try:
        conn = psycopg.connect(settings.database_url, connect_timeout=2, row_factory=dict_row)
        conn.close()
        _pg_pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row, "autocommit": True},
            open=True,
        )
        _backend_mode = "postgis"
    except Exception:
        init_sqlite_schema()
        _backend_mode = "sqlite_spatial"
    return _backend_mode


def reset_backend_mode(force_mode: str | None = None) -> str:
    global _backend_mode, _pg_pool
    if _pg_pool is not None:
        _pg_pool.close()
        _pg_pool = None
    _backend_mode = force_mode
    if force_mode == "sqlite_spatial":
        init_sqlite_schema()
        return "sqlite_spatial"
    return get_backend_mode()


def init_sqlite_schema() -> None:
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(SQLITE_PATH) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS kabupaten (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              nama TEXT NOT NULL,
              kode TEXT UNIQUE NOT NULL,
              is_pilot INTEGER NOT NULL DEFAULT 0,
              geojson TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS faskes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              osm_id INTEGER UNIQUE,
              nama TEXT NOT NULL,
              jenis TEXT NOT NULL CHECK (jenis IN ('rumah_sakit', 'puskesmas', 'klinik', 'lainnya')),
              alamat TEXT,
              telepon TEXT,
              kabupaten_id INTEGER REFERENCES kabupaten(id) ON DELETE SET NULL,
              sumber TEXT NOT NULL CHECK (sumber IN ('osm', 'csv', 'sampel')),
              lat REAL NOT NULL,
              lon REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sqlite_faskes_jenis ON faskes (jenis);

            CREATE TABLE IF NOT EXISTS faskes_status (
              faskes_id INTEGER PRIMARY KEY REFERENCES faskes(id) ON DELETE CASCADE,
              buka INTEGER NOT NULL DEFAULT 1,
              igd_24jam INTEGER NOT NULL DEFAULT 0,
              dokter_jaga INTEGER NOT NULL DEFAULT 0,
              oksigen INTEGER NOT NULL DEFAULT 0,
              tempat_tidur_tersedia INTEGER NOT NULL DEFAULT 0,
              tempat_tidur_total INTEGER NOT NULL DEFAULT 0,
              catatan_layanan TEXT,
              sumber TEXT NOT NULL CHECK (sumber IN ('osm', 'manual', 'simulasi')),
              diperbarui_pada TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS hotspot (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              waktu_akuisisi TEXT NOT NULL,
              confidence TEXT NOT NULL,
              frp REAL NOT NULL DEFAULT 0,
              satelit TEXT NOT NULL,
              kabupaten_id INTEGER REFERENCES kabupaten(id) ON DELETE SET NULL,
              sumber TEXT NOT NULL CHECK (sumber IN ('firms', 'sampel')),
              lat REAL NOT NULL,
              lon REAL NOT NULL,
              UNIQUE (waktu_akuisisi, lat, lon)
            );
            CREATE INDEX IF NOT EXISTS idx_sqlite_hotspot_waktu ON hotspot (waktu_akuisisi);
            """
        )


@contextmanager
def get_pg_conn() -> Iterator[psycopg.Connection]:
    get_backend_mode()
    assert _pg_pool is not None
    with _pg_pool.connection() as conn:
        yield conn


@contextmanager
def get_sqlite_conn() -> Iterator[sqlite3.Connection]:
    init_sqlite_schema()
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_to_faskes_dict(r: dict[str, Any], jarak_m: float | None = None, az_deg: float | None = None) -> dict[str, Any]:
    dt_val = r["diperbarui_pada"]
    if isinstance(dt_val, str):
        dt_val = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
    return {
        "id": int(r["id"]),
        "osm_id": int(r["osm_id"]) if r.get("osm_id") is not None else None,
        "nama": r["nama"],
        "jenis": r["jenis"],
        "alamat": r.get("alamat"),
        "telepon": r.get("telepon"),
        "kabupaten": r.get("kabupaten"),
        "sumber": r["sumber"],
        "lat": round(float(r["lat"]), 6),
        "lon": round(float(r["lon"]), 6),
        "status": {
            "buka": bool(r["buka"]),
            "igd_24jam": bool(r["igd_24jam"]),
            "dokter_jaga": bool(r["dokter_jaga"]),
            "oksigen": bool(r["oksigen"]),
            "tempat_tidur_tersedia": int(r["tempat_tidur_tersedia"]),
            "tempat_tidur_total": int(r["tempat_tidur_total"]),
            "catatan_layanan": r.get("catatan_layanan"),
            "sumber": r["status_sumber"],
            "diperbarui_pada": dt_val,
        },
        "jarak_m": round(jarak_m, 1) if jarak_m is not None else None,
        "azimuth_deg": round(az_deg, 1) if az_deg is not None else None,
        "arah_kompas": azimuth_to_compass(az_deg) if az_deg is not None else None,
    }


def query_faskes_list(
    bbox: tuple[float, float, float, float] | None = None,
    jenis: str | None = None,
    oksigen: bool | None = None,
    igd24: bool | None = None,
    dokter: bool | None = None,
    tt_min: int | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    mode = get_backend_mode()
    if mode == "postgis":
        clauses = ["1=1"]
        params: list[Any] = []
        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            clauses.append("f.geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)")
            params.extend([min_lon, min_lat, max_lon, max_lat])
        if jenis:
            clauses.append("f.jenis = %s")
            params.append(jenis)
        if oksigen is True:
            clauses.append("s.oksigen = TRUE")
        if igd24 is True:
            clauses.append("s.igd_24jam = TRUE")
        if dokter is True:
            clauses.append("s.dokter_jaga = TRUE")
        if tt_min is not None and tt_min > 0:
            clauses.append("s.tempat_tidur_tersedia >= %s")
            params.append(tt_min)
        if q:
            clauses.append("(f.nama ILIKE %s OR COALESCE(f.alamat, '') ILIKE %s OR COALESCE(k.nama, '') ILIKE %s)")
            like_q = f"%{q.strip()}%"
            params.extend([like_q, like_q, like_q])

        sql = f"""
            SELECT f.id, f.osm_id, f.nama, f.jenis, f.alamat, f.telepon, f.sumber,
                   ST_Y(f.geom) AS lat, ST_X(f.geom) AS lon,
                   k.nama AS kabupaten,
                   s.buka, s.igd_24jam, s.dokter_jaga, s.oksigen,
                   s.tempat_tidur_tersedia, s.tempat_tidur_total, s.catatan_layanan,
                   s.sumber AS status_sumber, s.diperbarui_pada
            FROM faskes f
            JOIN faskes_status s ON s.faskes_id = f.id
            LEFT JOIN kabupaten k ON k.id = f.kabupaten_id
            WHERE {' AND '.join(clauses)}
            ORDER BY f.nama ASC
        """
        with get_pg_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_faskes_dict(r) for r in rows]

    clauses = ["1=1"]
    params = []
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        clauses.append("f.lon BETWEEN ? AND ? AND f.lat BETWEEN ? AND ?")
        params.extend([min_lon, max_lon, min_lat, max_lat])
    if jenis:
        clauses.append("f.jenis = ?")
        params.append(jenis)
    if oksigen is True:
        clauses.append("s.oksigen = 1")
    if igd24 is True:
        clauses.append("s.igd_24jam = 1")
    if dokter is True:
        clauses.append("s.dokter_jaga = 1")
    if tt_min is not None and tt_min > 0:
        clauses.append("s.tempat_tidur_tersedia >= ?")
        params.append(tt_min)
    if q:
        clauses.append("(f.nama LIKE ? OR COALESCE(f.alamat, '') LIKE ? OR COALESCE(k.nama, '') LIKE ?)")
        like_q = f"%{q.strip()}%"
        params.extend([like_q, like_q, like_q])

    sql = f"""
        SELECT f.id, f.osm_id, f.nama, f.jenis, f.alamat, f.telepon, f.sumber,
               f.lat, f.lon, k.nama AS kabupaten,
               s.buka, s.igd_24jam, s.dokter_jaga, s.oksigen,
               s.tempat_tidur_tersedia, s.tempat_tidur_total, s.catatan_layanan,
               s.sumber AS status_sumber, s.diperbarui_pada
        FROM faskes f
        JOIN faskes_status s ON s.faskes_id = f.id
        LEFT JOIN kabupaten k ON k.id = f.kabupaten_id
        WHERE {' AND '.join(clauses)}
        ORDER BY f.nama ASC
    """
    with get_sqlite_conn() as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    return [_row_to_faskes_dict(r) for r in rows]


def query_faskes_by_id(faskes_id: int) -> dict[str, Any] | None:
    mode = get_backend_mode()
    if mode == "postgis":
        sql = """
            SELECT f.id, f.osm_id, f.nama, f.jenis, f.alamat, f.telepon, f.sumber,
                   ST_Y(f.geom) AS lat, ST_X(f.geom) AS lon,
                   k.nama AS kabupaten,
                   s.buka, s.igd_24jam, s.dokter_jaga, s.oksigen,
                   s.tempat_tidur_tersedia, s.tempat_tidur_total, s.catatan_layanan,
                   s.sumber AS status_sumber, s.diperbarui_pada
            FROM faskes f
            JOIN faskes_status s ON s.faskes_id = f.id
            LEFT JOIN kabupaten k ON k.id = f.kabupaten_id
            WHERE f.id = %s
        """
        with get_pg_conn() as conn:
            row = conn.execute(sql, (faskes_id,)).fetchone()
        return _row_to_faskes_dict(row) if row else None

    sql = """
        SELECT f.id, f.osm_id, f.nama, f.jenis, f.alamat, f.telepon, f.sumber,
               f.lat, f.lon, k.nama AS kabupaten,
               s.buka, s.igd_24jam, s.dokter_jaga, s.oksigen,
               s.tempat_tidur_tersedia, s.tempat_tidur_total, s.catatan_layanan,
               s.sumber AS status_sumber, s.diperbarui_pada
        FROM faskes f
        JOIN faskes_status s ON s.faskes_id = f.id
        LEFT JOIN kabupaten k ON k.id = f.kabupaten_id
        WHERE f.id = ?
    """
    with get_sqlite_conn() as conn:
        row = conn.execute(sql, (faskes_id,)).fetchone()
    return _row_to_faskes_dict(dict(row)) if row else None


def query_nearest_faskes(
    lat: float,
    lon: float,
    k: int = 15,
    radius_km: float = 25.0,
    jenis: str | None = None,
    oksigen: bool | None = None,
    igd24: bool | None = None,
    dokter: bool | None = None,
    tt_min: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    radius_m = radius_km * 1000.0
    mode = get_backend_mode()
    if mode == "postgis":
        clauses = ["ST_DWithin(f.geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)"]
        params: list[Any] = [lon, lat, radius_m]
        if jenis:
            clauses.append("f.jenis = %s")
            params.append(jenis)
        if oksigen is True:
            clauses.append("s.oksigen = TRUE")
        if igd24 is True:
            clauses.append("s.igd_24jam = TRUE")
        if dokter is True:
            clauses.append("s.dokter_jaga = TRUE")
        if tt_min is not None and tt_min > 0:
            clauses.append("s.tempat_tidur_tersedia >= %s")
            params.append(tt_min)

        sql = f"""
            SELECT f.id, f.osm_id, f.nama, f.jenis, f.alamat, f.telepon, f.sumber,
                   ST_Y(f.geom) AS lat, ST_X(f.geom) AS lon,
                   k.nama AS kabupaten,
                   s.buka, s.igd_24jam, s.dokter_jaga, s.oksigen,
                   s.tempat_tidur_tersedia, s.tempat_tidur_total, s.catatan_layanan,
                   s.sumber AS status_sumber, s.diperbarui_pada,
                   ST_Distance(f.geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) AS jarak_m,
                   COALESCE(DEGREES(ST_Azimuth(ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, f.geom::geography)), 0.0) AS azimuth_deg
            FROM faskes f
            JOIN faskes_status s ON s.faskes_id = f.id
            LEFT JOIN kabupaten k ON k.id = f.kabupaten_id
            WHERE {' AND '.join(clauses)}
            ORDER BY f.geom::geography <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
            LIMIT %s
        """
        full_params = [lon, lat, lon, lat] + params + [lon, lat, k]
        hs_sql = """
            SELECT COUNT(*) AS cnt
            FROM hotspot
            WHERE waktu_akuisisi >= NOW() - INTERVAL '7 days'
              AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 5000)
        """
        with get_pg_conn() as conn:
            rows = conn.execute(sql, full_params).fetchall()
            hs_row = conn.execute(hs_sql, (lon, lat)).fetchone()
        hs_5km = int(hs_row["cnt"]) if hs_row else 0
        out = [
            _row_to_faskes_dict(r, float(r["jarak_m"]), (float(r["azimuth_deg"] or 0.0) + 360.0) % 360.0)
            for r in rows
        ]
        return out, hs_5km

    candidates = query_faskes_list(jenis=jenis, oksigen=oksigen, igd24=igd24, dokter=dokter, tt_min=tt_min)
    if not candidates:
        return [], 0

    # Gunakan STRtree sebagai spatial pre-filter di sekitar titik kueri, lalu geodesic/Haversine eksak
    deg_margin = (radius_km / 110.0) + 0.15
    pts = [Point(c["lon"], c["lat"]) for c in candidates]
    tree = STRtree(pts)
    near_idxs = tree.query(Point(lon, lat).buffer(deg_margin))

    scored: list[tuple[float, dict[str, Any]]] = []
    for idx in near_idxs:
        c = candidates[int(idx)]
        dist_m = haversine_m(lat, lon, c["lat"], c["lon"])
        if dist_m <= radius_m:
            _, az_deg = geodesic_inverse(lat, lon, c["lat"], c["lon"])
            c["jarak_m"] = round(dist_m, 1)
            c["azimuth_deg"] = round(az_deg, 1)
            c["arah_kompas"] = azimuth_to_compass(az_deg)
            scored.append((dist_m, c))

    scored.sort(key=lambda x: x[0])
    results = [item[1] for item in scored[:k]]

    hs_list = query_hotspots(days=7)
    hs_5km = sum(1 for h in hs_list if haversine_m(lat, lon, h["lat"], h["lon"]) <= 5000.0)
    return results, hs_5km


def query_hotspots(
    days: int = 7,
    bbox: tuple[float, float, float, float] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=days)
    mode = get_backend_mode()
    if mode == "postgis":
        clauses = ["h.waktu_akuisisi >= %s", "h.waktu_akuisisi <= %s"]
        params: list[Any] = [cutoff, now_utc]
        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            clauses.append("h.geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)")
            params.extend([min_lon, min_lat, max_lon, max_lat])
        limit_clause = ""
        if limit is not None and limit > 0:
            limit_clause = "LIMIT %s"
            params.append(limit)
        sql = f"""
            SELECT h.id, h.waktu_akuisisi, h.confidence, h.frp, h.satelit, h.sumber,
                   ST_Y(h.geom) AS lat, ST_X(h.geom) AS lon,
                   k.nama AS kabupaten
            FROM hotspot h
            LEFT JOIN kabupaten k ON k.id = h.kabupaten_id
            WHERE {' AND '.join(clauses)}
            ORDER BY h.waktu_akuisisi DESC
            {limit_clause}
        """
        with get_pg_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "id": int(r["id"]),
                "waktu_akuisisi": r["waktu_akuisisi"].isoformat(),
                "confidence": r["confidence"],
                "frp": round(float(r["frp"]), 2),
                "satelit": r["satelit"],
                "sumber": r["sumber"],
                "kabupaten": r.get("kabupaten"),
                "lat": round(float(r["lat"]), 5),
                "lon": round(float(r["lon"]), 5),
            }
            for r in rows
        ]

    clauses = ["1=1"]
    params = []
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        clauses.append("h.lon BETWEEN ? AND ? AND h.lat BETWEEN ? AND ?")
        params.extend([min_lon, max_lon, min_lat, max_lat])
    sql = f"""
        SELECT h.id, h.waktu_akuisisi, h.confidence, h.frp, h.satelit, h.sumber,
               h.lat, h.lon, k.nama AS kabupaten
        FROM hotspot h
        LEFT JOIN kabupaten k ON k.id = h.kabupaten_id
        WHERE {' AND '.join(clauses)}
        ORDER BY h.waktu_akuisisi DESC
    """
    with get_sqlite_conn() as conn:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    filtered = []
    for r in rows:
        raw_dt = str(r["waktu_akuisisi"]).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw_dt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if cutoff <= dt <= now_utc:
                filtered.append(r)
        except ValueError:
            continue
    return [
        {
            "id": int(r["id"]),
            "waktu_akuisisi": r["waktu_akuisisi"],
            "confidence": r["confidence"],
            "frp": round(float(r["frp"]), 2),
            "satelit": r["satelit"],
            "sumber": r["sumber"],
            "kabupaten": r.get("kabupaten"),
            "lat": round(float(r["lat"]), 5),
            "lon": round(float(r["lon"]), 5),
        }
        for r in (filtered[:limit] if (limit is not None and limit > 0) else filtered)
    ]


def _geom_intersects_bbox(geom_dict: dict[str, Any], bbox: tuple[float, float, float, float]) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    g_min_lon, g_min_lat, g_max_lon, g_max_lat = shape(geom_dict).bounds
    return not (
        g_max_lon < min_lon
        or g_min_lon > max_lon
        or g_max_lat < min_lat
        or g_min_lat > max_lat
    )


def query_kabupaten_geojson(
    bbox: tuple[float, float, float, float] | None = None,
    simplify_tolerance: float = 0.005,
) -> dict[str, Any]:
    mode = get_backend_mode()
    features = []
    if mode == "postgis":
        clauses = ["1=1"]
        params: list[Any] = []
        geom_expr = "ST_AsGeoJSON(geom)"
        if simplify_tolerance > 0:
            geom_expr = "ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, %s))"
            params.append(simplify_tolerance)
        if bbox:
            min_lon, min_lat, max_lon, max_lat = bbox
            clauses.append("geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)")
            params.extend([min_lon, min_lat, max_lon, max_lat])
        sql = f"""
            SELECT id, nama, kode, is_pilot, {geom_expr} AS gj
            FROM kabupaten
            WHERE {' AND '.join(clauses)}
            ORDER BY nama ASC
        """
        with get_pg_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        for r in rows:
            features.append(
                {
                    "type": "Feature",
                    "geometry": json.loads(r["gj"]),
                    "properties": {
                        "id": int(r["id"]),
                        "nama": r["nama"],
                        "kode": r["kode"],
                        "is_pilot": bool(r["is_pilot"]),
                    },
                }
            )
    else:
        with get_sqlite_conn() as conn:
            rows = [dict(r) for r in conn.execute("SELECT id, nama, kode, is_pilot, geojson FROM kabupaten ORDER BY nama ASC").fetchall()]
        for r in rows:
            geom_dict = json.loads(r["geojson"])
            if bbox and not _geom_intersects_bbox(geom_dict, bbox):
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": geom_dict,
                    "properties": {
                        "id": int(r["id"]),
                        "nama": r["nama"],
                        "kode": r["kode"],
                        "is_pilot": bool(r["is_pilot"]),
                    },
                }
            )
    return {"type": "FeatureCollection", "features": features}


def query_meta_summary() -> dict[str, Any]:
    mode = get_backend_mode()
    if mode == "postgis":
        with get_pg_conn() as conn:
            pilots = [r["nama"] for r in conn.execute("SELECT nama FROM kabupaten WHERE is_pilot = TRUE ORDER BY nama").fetchall()]
            f_src = {r["sumber"]: int(r["c"]) for r in conn.execute("SELECT sumber, COUNT(*) AS c FROM faskes GROUP BY sumber").fetchall()}
            s_src = {r["sumber"]: int(r["c"]) for r in conn.execute("SELECT sumber, COUNT(*) AS c FROM faskes_status GROUP BY sumber").fetchall()}
            h_src = {r["sumber"]: int(r["c"]) for r in conn.execute("SELECT sumber, COUNT(*) AS c FROM hotspot GROUP BY sumber").fetchall()}
            last_hs = conn.execute("SELECT MAX(waktu_akuisisi) AS m FROM hotspot").fetchone()
            max_dt = last_hs["m"] if last_hs else None
    else:
        with get_sqlite_conn() as conn:
            pilots = [r["nama"] for r in conn.execute("SELECT nama FROM kabupaten WHERE is_pilot = 1 ORDER BY nama").fetchall()]
            f_src = {r["sumber"]: int(r["c"]) for r in conn.execute("SELECT sumber, COUNT(*) AS c FROM faskes GROUP BY sumber").fetchall()}
            s_src = {r["sumber"]: int(r["c"]) for r in conn.execute("SELECT sumber, COUNT(*) AS c FROM faskes_status GROUP BY sumber").fetchall()}
            h_src = {r["sumber"]: int(r["c"]) for r in conn.execute("SELECT sumber, COUNT(*) AS c FROM hotspot GROUP BY sumber").fetchall()}
            last_hs = conn.execute("SELECT MAX(waktu_akuisisi) AS m FROM hotspot").fetchone()
            max_dt = datetime.fromisoformat(last_hs["m"].replace("Z", "+00:00")) if (last_hs and last_hs["m"]) else None

    return {
        "wilayah_cakupan": "Indonesia",
        "kabupaten_pilot": pilots,
        "total_faskes": sum(f_src.values()),
        "faskes_per_sumber": f_src,
        "status_per_sumber": s_src,
        "total_hotspot": sum(h_src.values()),
        "hotspot_per_sumber": h_src,
        "hotspot_terakhir_diperbarui": max_dt,
        "catatan_transparansi": [
            "Lokasi dan identitas fasilitas kesehatan berasal dari OpenStreetMap atau impor CSV berlabel.",
            "Ketersediaan tempat tidur, oksigen, dan dokter jaga menggunakan data simulasi deterministik (berlabel 'simulasi') apabila integrasi real-time rumah sakit belum tersedia.",
            "Titik panas (hotspot) satelit VIIRS/MODIS merupakan indikator anomali termal kontekstual, bukan bukti langsung kebakaran aktif atau kepekatan asap di permukaan.",
            "Koordinat pengguna dibulatkan (~110 m) untuk pencarian terdekat dan tidak pernah disimpan di server (minimisasi data sesuai UU PDP No. 27/2022).",
        ],
    }
