import random
from datetime import datetime, timezone
from app.db import get_backend_mode, get_pg_conn, get_sqlite_conn

SEED = 20261118


def generate_simulated_statuses() -> int:
    rng = random.Random(SEED)
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    mode = get_backend_mode()

    if mode == "postgis":
        with get_pg_conn() as conn:
            faskes_rows = conn.execute("SELECT id, nama, jenis FROM faskes ORDER BY id ASC").fetchall()
    else:
        with get_sqlite_conn() as conn:
            faskes_rows = [dict(r) for r in conn.execute("SELECT id, nama, jenis FROM faskes ORDER BY id ASC").fetchall()]

    updated = 0
    for f in faskes_rows:
        fid = int(f["id"])
        jenis = f["jenis"]
        nama_low = f["nama"].lower()

        if jenis == "rumah_sakit":
            buka = True
            igd_24jam = True
            dokter_jaga = True
            oksigen = True if ("rsup" in nama_low or "paru" in nama_low or rng.random() < 0.90) else False
            tt_total = rng.randint(90, 320)
            tt_tersedia = rng.randint(6, max(12, tt_total // 6))
            catatan = "IGD 24 jam, nebulizer & terapi oksigen ISPA tersedia (Data simulasi)"
        elif jenis == "puskesmas":
            buka = True
            igd_24jam = rng.random() < 0.55
            dokter_jaga = True if igd_24jam else (rng.random() < 0.75)
            oksigen = rng.random() < 0.70
            tt_total = rng.randint(8, 24) if igd_24jam else rng.randint(0, 6)
            tt_tersedia = rng.randint(1, max(2, tt_total // 2)) if tt_total > 0 else 0
            catatan = (
                "Puskesmas rawat inap & posko oksigen darurat asap (Data simulasi)"
                if igd_24jam
                else "Puskesmas rawat jalan & triase awal ISPA (Data simulasi)"
            )
        else:
            buka = rng.random() < 0.85
            igd_24jam = False
            dokter_jaga = buka
            oksigen = rng.random() < 0.45
            tt_total = rng.randint(0, 8)
            tt_tersedia = rng.randint(0, min(3, tt_total)) if tt_total > 0 else 0
            catatan = "Layanan pemeriksaan pernapasan dasar (Data simulasi)"

        if mode == "postgis":
            sql = """
                INSERT INTO faskes_status
                (faskes_id, buka, igd_24jam, dokter_jaga, oksigen, tempat_tidur_tersedia, tempat_tidur_total, catatan_layanan, sumber, diperbarui_pada)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'simulasi', %s)
                ON CONFLICT (faskes_id) DO UPDATE
                SET buka = EXCLUDED.buka,
                    igd_24jam = EXCLUDED.igd_24jam,
                    dokter_jaga = EXCLUDED.dokter_jaga,
                    oksigen = EXCLUDED.oksigen,
                    tempat_tidur_tersedia = EXCLUDED.tempat_tidur_tersedia,
                    tempat_tidur_total = EXCLUDED.tempat_tidur_total,
                    catatan_layanan = EXCLUDED.catatan_layanan,
                    diperbarui_pada = EXCLUDED.diperbarui_pada
                WHERE faskes_status.sumber = 'simulasi'
            """
            with get_pg_conn() as conn:
                conn.execute(
                    sql,
                    (fid, buka, igd_24jam, dokter_jaga, oksigen, tt_tersedia, tt_total, catatan, now_iso),
                )
        else:
            sql = """
                INSERT INTO faskes_status
                (faskes_id, buka, igd_24jam, dokter_jaga, oksigen, tempat_tidur_tersedia, tempat_tidur_total, catatan_layanan, sumber, diperbarui_pada)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'simulasi', ?)
                ON CONFLICT (faskes_id) DO UPDATE
                SET buka = excluded.buka,
                    igd_24jam = excluded.igd_24jam,
                    dokter_jaga = excluded.dokter_jaga,
                    oksigen = excluded.oksigen,
                    tempat_tidur_tersedia = excluded.tempat_tidur_tersedia,
                    tempat_tidur_total = excluded.tempat_tidur_total,
                    catatan_layanan = excluded.catatan_layanan,
                    diperbarui_pada = excluded.diperbarui_pada
                WHERE faskes_status.sumber = 'simulasi'
            """
            with get_sqlite_conn() as conn:
                conn.execute(
                    sql,
                    (
                        fid,
                        1 if buka else 0,
                        1 if igd_24jam else 0,
                        1 if dokter_jaga else 0,
                        1 if oksigen else 0,
                        tt_tersedia,
                        tt_total,
                        catatan,
                        now_iso,
                    ),
                )
        updated += 1

    return updated


if __name__ == "__main__":
    n = generate_simulated_statuses()
    print(f"Status simulasi deterministik diperbarui untuk {n} faskes.")
