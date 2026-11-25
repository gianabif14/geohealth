from typing import Any
from fastapi import APIRouter, Query
from app.db import query_faskes_list, query_hotspots, query_kabupaten_geojson
from app.schemas import AnalisisAksesResponseOut
from app.services.akses import compute_h3_access_scores

router = APIRouter(prefix="/api/analisis", tags=["analisis"])


@router.get("/akses", response_model=AnalisisAksesResponseOut)
def get_analisis_akses_terbatas(
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    all_faskes = query_faskes_list()
    ready_faskes = [
        f for f in all_faskes if f["status"]["igd_24jam"] and f["status"]["oksigen"]
    ]
    hotspots = query_hotspots(days=7)
    kab_fc = query_kabupaten_geojson()

    h3_cells = compute_h3_access_scores(hotspots=hotspots, ready_faskes=ready_faskes)

    kab_map: dict[str, dict[str, Any]] = {}
    for feat in kab_fc["features"]:
        p = feat["properties"]
        kab_map[p["nama"]] = {
            "id": p["id"],
            "nama": p["nama"],
            "kode": p["kode"],
            "is_pilot": p["is_pilot"],
            "jumlah_faskes": 0,
            "jumlah_faskes_siap_igd_oksigen": 0,
            "jumlah_hotspot_7hari": 0,
            "dists": [],
            "scores": [],
        }

    for f in all_faskes:
        kn = f.get("kabupaten")
        if kn in kab_map:
            kab_map[kn]["jumlah_faskes"] += 1
            if f["status"]["igd_24jam"] and f["status"]["oksigen"]:
                kab_map[kn]["jumlah_faskes_siap_igd_oksigen"] += 1

    for h in hotspots:
        kn = h.get("kabupaten")
        if kn in kab_map:
            kab_map[kn]["jumlah_hotspot_7hari"] += 1

    for cell in h3_cells:
        kn = cell.get("kabupaten")
        if kn in kab_map:
            kab_map[kn]["dists"].append(cell["jarak_faskes_siap_km"])
            kab_map[kn]["scores"].append(cell["skor"])

    kab_ranking = []
    for k, v in kab_map.items():
        avg_dist = round(sum(v["dists"]) / len(v["dists"]), 2) if v["dists"] else 0.0
        avg_score = round(sum(v["scores"]) / len(v["scores"]), 1) if v["scores"] else 0.0
        if avg_score >= 55.0:
            prio = "tinggi"
        elif avg_score >= 30.0:
            prio = "sedang"
        else:
            prio = "rendah"
        kab_ranking.append(
            {
                "id": v["id"],
                "nama": v["nama"],
                "kode": v["kode"],
                "is_pilot": v["is_pilot"],
                "jumlah_faskes": v["jumlah_faskes"],
                "jumlah_faskes_siap_igd_oksigen": v["jumlah_faskes_siap_igd_oksigen"],
                "jumlah_hotspot_7hari": v["jumlah_hotspot_7hari"],
                "rerata_jarak_faskes_siap_km": avg_dist,
                "skor_akses_terbatas": avg_score,
                "prioritas_posko": prio,
            }
        )

    kab_ranking.sort(key=lambda x: (x["skor_akses_terbatas"], x["jumlah_hotspot_7hari"]), reverse=True)

    return {
        "metodologi": (
            "Agregasi heksagonal H3 resolusi 6 (~36 km\u00b2). Skor per sel (0-100) menggabungkan "
            "bobot 55% jarak garis lurus (Haversine) ke fasilitas kesehatan terdekat yang memiliki "
            "layanan IGD 24 jam dan oksigen aktif, serta 45% kepadatan titik panas 7 hari terakhir."
        ),
        "catatan_sumber": (
            "Berbasis data ketersediaan layanan yang mencakup atribut simulasi berlabel. "
            "Digunakan sebagai alat bantu penentuan kandidat posko kesehatan darurat."
        ),
        "kabupaten_ranking": kab_ranking,
        "sel_h3": h3_cells[:limit],
    }
