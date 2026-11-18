import h3
from app.services.geo import haversine_m

H3_RESOLUTION = 6


def compute_h3_access_scores(
    hotspots: list[dict],
    ready_faskes: list[dict],
) -> list[dict]:
    """
    Hitung skor keterbatasan akses faskes per sel H3 resolusi 6 (~36 km2).
    hotspots: [{"lat": float, "lon": float, "kabupaten": str | None}, ...]
    ready_faskes: [{"id": int, "nama": str, "lat": float, "lon": float}, ...] (IGD 24 jam + oksigen)
    """
    if not hotspots:
        return []

    cell_counts: dict[str, int] = {}
    cell_kab: dict[str, str | None] = {}
    for hs in hotspots:
        cell = h3.latlng_to_cell(hs["lat"], hs["lon"], H3_RESOLUTION)
        cell_counts[cell] = cell_counts.get(cell, 0) + 1
        if cell not in cell_kab and hs.get("kabupaten"):
            cell_kab[cell] = hs["kabupaten"]

    raw_cells: list[dict] = []
    for cell, count in cell_counts.items():
        c_lat, c_lon = h3.cell_to_latlng(cell)
        boundary_tuples = h3.cell_to_boundary(cell)
        boundary = [[float(lat), float(lon)] for lat, lon in boundary_tuples]

        best_dist_m = 999_999.0
        best_name = None
        for fk in ready_faskes:
            d = haversine_m(c_lat, c_lon, fk["lat"], fk["lon"])
            if d < best_dist_m:
                best_dist_m = d
                best_name = fk["nama"]

        dist_km = round(best_dist_m / 1000.0, 2) if ready_faskes else 100.0
        raw_cells.append(
            {
                "h3_index": cell,
                "kabupaten": cell_kab.get(cell),
                "boundary": boundary,
                "centroid_lat": round(float(c_lat), 5),
                "centroid_lon": round(float(c_lon), 5),
                "n_hotspot": count,
                "jarak_faskes_siap_km": dist_km,
                "faskes_terdekat_nama": best_name,
            }
        )

    max_hs = max(c["n_hotspot"] for c in raw_cells) or 1
    max_dist = max(c["jarak_faskes_siap_km"] for c in raw_cells) or 1.0

    for c in raw_cells:
        norm_hs = c["n_hotspot"] / max_hs
        norm_dist = min(c["jarak_faskes_siap_km"] / max(max_dist, 25.0), 1.0)
        # Bobot 55% jarak ke faskes siap (IGD+oksigen) dan 45% kepadatan titik panas
        skor = round((0.55 * norm_dist + 0.45 * norm_hs) * 100.0, 1)
        c["skor"] = skor
        if skor >= 60.0:
            c["kategori"] = "tinggi"
        elif skor >= 35.0:
            c["kategori"] = "sedang"
        else:
            c["kategori"] = "rendah"

    raw_cells.sort(key=lambda x: x["skor"], reverse=True)
    return raw_cells
