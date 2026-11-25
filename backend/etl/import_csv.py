import csv
import math
from datetime import datetime, timezone
from pathlib import Path
from app.db import get_backend_mode, get_pg_conn, get_sqlite_conn
from etl.fetch_osm import _load_kabupaten_polygons, match_kabupaten_id

CUSTOM_DIR = Path(__file__).resolve().parents[2] / "data" / "custom"

# Kontrak Tahap 0: Bounding Box Nasional Indonesia
INDONESIA_MIN_LAT = -11.10
INDONESIA_MAX_LAT = 6.10
INDONESIA_MIN_LON = 94.90
INDONESIA_MAX_LON = 141.10


def is_within_indonesia_bbox(lat: float, lon: float) -> bool:
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return False
    return (
        INDONESIA_MIN_LAT <= lat <= INDONESIA_MAX_LAT
        and INDONESIA_MIN_LON <= lon <= INDONESIA_MAX_LON
    )


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
                try:
                    lat = float(row["lat"])
                    lon = float(row["lon"])
                except (KeyError, TypeError, ValueError):
                    continue
                if not is_within_indonesia_bbox(lat, lon):
                    continue
                jenis = (row.get("jenis") or "lainnya").strip().lower()
                if jenis not in ("rumah_sakit", "puskesmas", "klinik", "lainnya"):
                    jenis = "lainnya"
                alamat = (row.get("alamat") or "").strip() or None
                telepon = (row.get("telepon") or "").strip() or None
                hint = f"{alamat or ''} {nama}"
                kid = match_kabupaten_id(lat, lon, kabs, text_hint=hint)

                igd = _parse_bool(row.get("igd_24jam"), False)
                oks = _parse_bool(row.get("oksigen"), False)
                dok = _parse_bool(row.get("dokter_jaga"), True)
                try:
                    tt_tot = int(row.get("tt_total") or 0)
                    tt_avl = int(row.get("tt_tersedia") or 0)
                except ValueError:
                    tt_tot, tt_avl = 0, 0
                catatan = (row.get("catatan_layanan") or "Diimpor dari CSV dataset nasional").strip()

                if mode == "postgis":
                    with get_pg_conn() as conn:
                        existing = conn.execute(
                            "SELECT id FROM faskes WHERE LOWER(nama) = LOWER(%s) LIMIT 1",
                            (nama,),
                        ).fetchone()
                        if existing:
                            fid = int(existing["id"])
                            conn.execute(
                                """
                                UPDATE faskes
                                SET jenis = %s,
                                    alamat = COALESCE(%s, alamat),
                                    telepon = COALESCE(%s, telepon),
                                    kabupaten_id = COALESCE(%s, kabupaten_id),
                                    geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                                WHERE id = %s
                                """,
                                (jenis, alamat, telepon, kid, lon, lat, fid),
                            )
                        else:
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
                            ON CONFLICT (faskes_id) DO UPDATE
                            SET buka = TRUE,
                                igd_24jam = EXCLUDED.igd_24jam,
                                dokter_jaga = EXCLUDED.dokter_jaga,
                                oksigen = EXCLUDED.oksigen,
                                tempat_tidur_tersedia = EXCLUDED.tempat_tidur_tersedia,
                                tempat_tidur_total = EXCLUDED.tempat_tidur_total,
                                catatan_layanan = EXCLUDED.catatan_layanan,
                                sumber = 'manual',
                                diperbarui_pada = EXCLUDED.diperbarui_pada
                            """,
                            (fid, igd, dok, oks, tt_avl, tt_tot, catatan, now_iso),
                        )
                else:
                    with get_sqlite_conn() as conn:
                        existing = conn.execute(
                            "SELECT id FROM faskes WHERE LOWER(nama) = LOWER(?) LIMIT 1",
                            (nama,),
                        ).fetchone()
                        if existing:
                            fid = int(existing["id"])
                            conn.execute(
                                """
                                UPDATE faskes
                                SET jenis = ?,
                                    alamat = COALESCE(?, alamat),
                                    telepon = COALESCE(?, telepon),
                                    kabupaten_id = COALESCE(?, kabupaten_id),
                                    lat = ?,
                                    lon = ?
                                WHERE id = ?
                                """,
                                (jenis, alamat, telepon, kid, lat, lon, fid),
                            )
                        else:
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
                            ON CONFLICT (faskes_id) DO UPDATE
                            SET buka = 1,
                                igd_24jam = excluded.igd_24jam,
                                dokter_jaga = excluded.dokter_jaga,
                                oksigen = excluded.oksigen,
                                tempat_tidur_tersedia = excluded.tempat_tidur_tersedia,
                                tempat_tidur_total = excluded.tempat_tidur_total,
                                catatan_layanan = excluded.catatan_layanan,
                                sumber = 'manual',
                                diperbarui_pada = excluded.diperbarui_pada
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
    print(f"Berhasil mengimpor/memperbarui {n} baris faskes dari CSV nasional.")
