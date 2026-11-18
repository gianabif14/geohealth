from typing import Any
from fastapi import APIRouter, HTTPException, Query
from app.db import query_faskes_by_id, query_faskes_list, query_nearest_faskes
from app.schemas import FaskesDetailOut, PrivacyCheckOut, TerdekatResponseOut
from app.services.privacy import validate_and_cloak_location

router = APIRouter(prefix="/api", tags=["faskes"])


def _parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if not bbox:
        return None
    parts = [p.strip() for p in bbox.split(",")]
    if len(parts) != 4:
        raise HTTPException(status_code=422, detail="Parameter bbox harus berisi 4 angka: min_lon,min_lat,max_lon,max_lat")
    try:
        vals = tuple(float(x) for x in parts)
        return (vals[0], vals[1], vals[2], vals[3])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Nilai bbox bukan angka valid") from exc


@router.get("/faskes")
def list_faskes_geojson(
    bbox: str | None = Query(default=None, description="min_lon,min_lat,max_lon,max_lat"),
    jenis: str | None = Query(default=None),
    oksigen: bool | None = Query(default=None),
    igd24: bool | None = Query(default=None),
    dokter: bool | None = Query(default=None),
    tt_min: int | None = Query(default=None, ge=0),
    q: str | None = Query(default=None),
) -> dict[str, Any]:
    parsed_bbox = _parse_bbox(bbox)
    items = query_faskes_list(
        bbox=parsed_bbox,
        jenis=jenis,
        oksigen=oksigen,
        igd24=igd24,
        dokter=dokter,
        tt_min=tt_min,
        q=q,
    )
    features = []
    for item in items:
        props = {k: v for k, v in item.items() if k not in ("lat", "lon")}
        props["lat"] = item["lat"]
        props["lon"] = item["lon"]
        if isinstance(props["status"]["diperbarui_pada"], object) and hasattr(props["status"]["diperbarui_pada"], "isoformat"):
            props["status"] = {
                **props["status"],
                "diperbarui_pada": props["status"]["diperbarui_pada"].isoformat(),
            }
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [item["lon"], item["lat"]]},
                "properties": props,
            }
        )
    return {
        "type": "FeatureCollection",
        "count": len(features),
        "features": features,
    }


@router.get("/faskes/{faskes_id}", response_model=FaskesDetailOut)
def get_faskes_detail(faskes_id: int) -> dict[str, Any]:
    item = query_faskes_by_id(faskes_id)
    if not item:
        raise HTTPException(status_code=404, detail="Fasilitas kesehatan tidak ditemukan.")
    return item


@router.get("/terdekat", response_model=TerdekatResponseOut)
def get_nearest_faskes(
    lat: float = Query(..., description="Latitude posisi pengguna"),
    lon: float = Query(..., description="Longitude posisi pengguna"),
    accuracy: float | None = Query(default=None, description="Akurasi fix GPS dalam meter"),
    exact: bool = Query(default=False, description="Gunakan koordinat presisi tinggi tanpa pembulatan 110 m"),
    prev_lat: float | None = Query(default=None),
    prev_lon: float | None = Query(default=None),
    dt_seconds: float | None = Query(default=None),
    k: int = Query(default=20, ge=1, le=100),
    radius_km: float = Query(default=25.0, ge=1.0, le=150.0),
    jenis: str | None = Query(default=None),
    oksigen: bool | None = Query(default=None),
    igd24: bool | None = Query(default=None),
    dokter: bool | None = Query(default=None),
    tt_min: int | None = Query(default=None, ge=0),
) -> dict[str, Any]:
    try:
        priv = validate_and_cloak_location(
            lat=lat,
            lon=lon,
            accuracy_m=accuracy,
            exact=exact,
            prev_lat=prev_lat,
            prev_lon=prev_lon,
            dt_seconds=dt_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    q_lat = priv["query_lat"]
    q_lon = priv["query_lon"]
    results, hs_5km = query_nearest_faskes(
        lat=q_lat,
        lon=q_lon,
        k=k,
        radius_km=radius_km,
        jenis=jenis,
        oksigen=oksigen,
        igd24=igd24,
        dokter=dokter,
        tt_min=tt_min,
    )

    return {
        "radius_km": radius_km,
        "jumlah_ditemukan": len(results),
        "hotspot_sekitar_5km": hs_5km,
        "privasi": PrivacyCheckOut(
            dibulatkan_m=priv["dibulatkan_m"],
            peringatan_akurasi=priv["peringatan_akurasi"],
            peringatan_plausibilitas=priv["peringatan_plausibilitas"],
        ),
        "hasil": results,
    }
