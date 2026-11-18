import csv
from datetime import datetime, timezone
from pathlib import Path
from app.db import get_backend_mode, get_pg_conn, get_sqlite_conn
from app.services.geo import is_within_sumsel_bbox
from etl.fetch_osm import _load_kabupaten_polygons, match_kabupaten_id

CUSTOM_DIR = Path(__file__).resolve().parents[2] / "data" / "custom"


def _parse_bool(val: str | None, default: bool = False) -> bool:
    if val is None or val.strip() == "":
        return default
    return val.strip().lower() in ("1", "true", "ya", "yes", "y")


def import_custom_csvs() -> int:
    if not CUSTOM_DIR.exists():
        return 0
    csv_files = sorted(CUSTOM_DIR.glob("*.csv"))
    if not csv_files:
        return 0

    kabs = _load_kabupaten_polygons()
    mode = get_backend_mode()
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    imported = 0

    for fp in csv_files:
        with open(fp, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                nama = (row.get("nama") or "").strip()
                if not nama:
                    continue
                lat = float(row["lat"])
                lon = float(row["lon"])
                if not is_within_sumsel_bbox(lat, lon):
                    continue
                jenis = (row.get("jenis") or "lainnya").strip().lower()
                if jenis not in ("rumah_sakit", "puskesmas", "klinik", "lainnya"):
                    jenis = "lainnya"
                alamat = (row.get("alamat") or "").strip() or None
                telepon = (row.get("telepon") or "").strip() or None
                kid = match_kabupaten_id(lat, lon, kabs)

                igd = _parse_bool(row.get("igd_24jam"), False)
                oks = _parse_bool(row.get("oksigen"), False)
                dok = _parse_bool(row.get("dokter_jaga"), True)
                tt_tot = int(row.get("tt_total") or 0)
                tt_avl = int(row.get("tt_tersedia") or 0)
                catatan = (row.get("catatan_layanan") or "Diimpor dari CSV dataset kustom").strip()

                if mode == "postgis":
                    with get_pg_conn() as conn:
                        cur = conn.execute(
                            """
                            INSERT INTO faskes (nama, jenis, alamat, telepon, kabupaten_id, sumber, geom)
                            VALUES (%s, %s, %s, %s, %s, 'csv', ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                            RETURNING id
                            """,
                            (nama, jenis, alamat, telepon, kid, lon, lat),
                        ).fetchone()
                        fid = int(cur["id"])
                        conn.execute(
                            """
                            INSERT INTO faskes_status
                            (faskes_id, buka, igd_24jam, dokter_jaga, oksigen, tempat_tidur_tersedia, tempat_tidur_total, catatan_layanan, sumber, diperbarui_pada)
                            VALUES (%s, TRUE, %s, %s, %s, %s, %s, %s, 'manual', %s)
                            """,
                            (fid, igd, dok, oks, tt_avl, tt_tot, catatan, now_iso),
                        )
                else:
                    with get_sqlite_conn() as conn:
                        cur = conn.execute(
                            """
                            INSERT INTO faskes (nama, jenis, alamat, telepon, kabupaten_id, sumber, lat, lon)
                            VALUES (?, ?, ?, ?, ?, 'csv', ?, ?)
                            """,
                            (nama, jenis, alamat, telepon, kid, lat, lon),
                        )
                        fid = int(cur.lastrowid)
                        conn.execute(
                            """
                            INSERT INTO faskes_status
                            (faskes_id, buka, igd_24jam, dokter_jaga, oksigen, tempat_tidur_tersedia, tempat_tidur_total, catatan_layanan, sumber, diperbarui_pada)
                            VALUES (?, 1, ?, ?, ?, ?, ?, ?, 'manual', ?)
                            """,
                            (
                                fid,
                                1 if igd else 0,
                                1 if dok else 0,
                                1 if oks else 0,
                                tt_avl,
                                tt_tot,
                                catatan,
                                now_iso,
                            ),
                        )
                imported += 1

    return imported


if __name__ == "__main__":
    n = import_custom_csvs()
    print(f"Berhasil mengimpor {n} baris faskes dari CSV kustom.")
