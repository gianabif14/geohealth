import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
import httpx
from app.config import settings
from app.db import get_backend_mode, get_pg_conn, get_sqlite_conn
from etl.fetch_osm import _load_kabupaten_polygons, match_kabupaten_id

SAMPLE_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "sample" / "hotspot_sampel.csv"

# Bounding box seluruh Indonesia sesuai spesifikasi Tugas Orang 1
FIRMS_AREAS = [
    ("Indonesia", "95.0,-11.0,141.0,6.0"),
]

FIRMS_SOURCES = ["VIIRS_NOAA20_NRT", "MODIS_NRT", "VIIRS_SNPP_NRT"]


def _fetch_firms_live() -> tuple[list[dict], bool]:
    if not settings.firms_map_key:
        return [], False
    # NASA FIRMS API area/csv menerima rentang 1..5 hari
    rows: list[dict] = []
    any_ok = False
    for source_name in FIRMS_SOURCES:
        for area_name, bbox in FIRMS_AREAS:
            url = (
                f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
                f"{settings.firms_map_key}/{source_name}/{bbox}/5"
            )
            try:
                resp = httpx.get(url, timeout=25.0)
                resp.raise_for_status()
                any_ok = True
                reader = csv.DictReader(StringIO(resp.text))
                for r in reader:
                    acq_date = r.get("acq_date", "")
                    acq_time = r.get("acq_time", "0000").zfill(4)
                    dt_str = f"{acq_date}T{acq_time[:2]}:{acq_time[2:]}:00Z"
                    conf_raw = str(r.get("confidence", "nominal")).strip().lower()
                    if conf_raw.isdigit():
                        conf = "high" if int(conf_raw) >= 80 else ("nominal" if int(conf_raw) >= 40 else "low")
                    else:
                        conf = conf_raw or "nominal"
                    rows.append(
                        {
                            "waktu_akuisisi": dt_str,
                            "lat": float(r["latitude"]),
                            "lon": float(r["longitude"]),
                            "confidence": conf,
                            "frp": float(r.get("frp") or 0.0),
                            "satelit": source_name.replace("_NRT", ""),
                            "sumber": "firms",
                        }
                    )
            except Exception as exc:
                print(f"Peringatan: gagal mengambil NASA FIRMS {source_name} {area_name} ({exc}).")
    return rows, any_ok


def _load_sample_hotspots() -> list[dict]:
    rows = []
    now = datetime.now(timezone.utc)
    with open(SAMPLE_CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, r in enumerate(reader):
            # Geser timestamp sampel agar selalu berada dalam jendela 6 hari terakhir dari saat dijalankan
            hours_ago = (idx * 3) % (6 * 24)
            dt_iso = (now - timedelta(hours=hours_ago)).replace(microsecond=0).isoformat()
            rows.append(
                {
                    "waktu_akuisisi": dt_iso,
                    "lat": float(r["lat"]),
                    "lon": float(r["lon"]),
                    "confidence": r["confidence"].strip(),
                    "frp": float(r["frp"]),
                    "satelit": r["satelit"].strip(),
                    "sumber": "sampel",
                }
            )
    return rows


def load_hotspots() -> tuple[int, str]:
    live_rows, firms_ok = _fetch_firms_live()
    if live_rows:
        rows = live_rows
        source_used = "firms"
    else:
        if firms_ok:
            print("Info: NASA FIRMS mengembalikan 0 titik panas aktif dalam 5 hari terakhir di Indonesia; memakai data sampel.")
        rows = _load_sample_hotspots()
        source_used = "sampel"

    kabs = _load_kabupaten_polygons()
    mode = get_backend_mode()

    if mode == "postgis":
        with get_pg_conn() as conn:
            conn.execute("DELETE FROM hotspot WHERE sumber = 'sampel'")
            if source_used == "firms":
                conn.execute("DELETE FROM hotspot WHERE sumber = 'firms'")
            for r in rows:
                kid = match_kabupaten_id(r["lat"], r["lon"], kabs)
                conn.execute(
                    """
                    INSERT INTO hotspot (waktu_akuisisi, confidence, frp, satelit, kabupaten_id, sumber, geom)
                    VALUES (%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                    ON CONFLICT (waktu_akuisisi, geom) DO NOTHING
                    """,
                    (
                        r["waktu_akuisisi"],
                        r["confidence"],
                        r["frp"],
                        r["satelit"],
                        kid,
                        r["sumber"],
                        r["lon"],
                        r["lat"],
                    ),
                )
    else:
        with get_sqlite_conn() as conn:
            conn.execute("DELETE FROM hotspot WHERE sumber = 'sampel'")
            if source_used == "firms":
                conn.execute("DELETE FROM hotspot WHERE sumber = 'firms'")
            for r in rows:
                kid = match_kabupaten_id(r["lat"], r["lon"], kabs)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO hotspot
                    (waktu_akuisisi, confidence, frp, satelit, kabupaten_id, sumber, lat, lon)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r["waktu_akuisisi"],
                        r["confidence"],
                        r["frp"],
                        r["satelit"],
                        kid,
                        r["sumber"],
                        r["lat"],
                        r["lon"],
                    ),
                )

    return len(rows), source_used


if __name__ == "__main__":
    n, src = load_hotspots()
    print(f"Hotspot dimuat: {n} titik (sumber: {src})")
