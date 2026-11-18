from typing import Any
from fastapi import APIRouter, HTTPException, Query
from app.db import query_hotspots, query_kabupaten_geojson
from app.services.geo import haversine_m
from app.services.privacy import validate_and_cloak_location

router = APIRouter(prefix="/api", tags=["hotspot"])


@router.get("/hotspot")
def get_hotspots_geojson(
    hari: int = Query(default=7, ge=1, le=30),
    bbox: str | None = Query(default=None),
) -> dict[str, Any]:
    parsed_bbox = None
    if bbox:
        parts = [p.strip() for p in bbox.split(",")]
        if len(parts) != 4:
            raise HTTPException(status_code=422, detail="Format bbox tidak valid.")
        try:
            vals = tuple(float(x) for x in parts)
            parsed_bbox = (vals[0], vals[1], vals[2], vals[3])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Nilai bbox bukan angka.") from exc

    rows = query_hotspots(days=hari, bbox=parsed_bbox)
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
            "properties": {k: v for k, v in r.items() if k not in ("lat", "lon")},
        }
        for r in rows
    ]
    return {
        "type": "FeatureCollection",
        "count": len(features),
        "catatan_batasan": (
            "Titik panas satelit merupakan indikasi anomali suhu permukaan dan bukan bukti langsung "
            "kebakaran aktif atau tingkat polusi udara di lokasi."
        ),
        "features": features,
    }


@router.get("/hotspot/dekat")
def get_nearby_hotspots(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(default=10.0, ge=1.0, le=100.0),
    hari: int = Query(default=7, ge=1, le=30),
) -> dict[str, Any]:
    try:
        priv = validate_and_cloak_location(lat=lat, lon=lon)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    q_lat = priv["query_lat"]
    q_lon = priv["query_lon"]
    radius_m = radius_km * 1000.0
    all_hs = query_hotspots(days=hari)

    nearby = []
    for h in all_hs:
        d = haversine_m(q_lat, q_lon, h["lat"], h["lon"])
        if d <= radius_m:
            nearby.append({**h, "jarak_m": round(d, 1)})
    nearby.sort(key=lambda x: x["jarak_m"])

    return {
        "radius_km": radius_km,
        "jumlah_hotspot": len(nearby),
        "terdekat_m": nearby[0]["jarak_m"] if nearby else None,
        "daftar": nearby[:30],
    }


@router.get("/kabupaten")
def get_kabupaten_layer() -> dict[str, Any]:
    return query_kabupaten_geojson()
