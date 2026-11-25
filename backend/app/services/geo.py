import math
from pyproj import Geod
from app.config import settings

R_EARTH_M = 6_371_008.8
_geod = Geod(ellps="WGS84")

COMPASS_DIRS = (
    "Utara",
    "Timur Laut",
    "Timur",
    "Tenggara",
    "Selatan",
    "Barat Daya",
    "Barat",
    "Barat Laut",
)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = phi2 - phi1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2.0) ** 2
    return 2.0 * R_EARTH_M * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def geodesic_inverse(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    # pyproj.Geod.inv menerima (lon1, lat1, lon2, lat2) dan mengembalikan azimuth [-180, 180]
    fwd_az, _, dist_m = _geod.inv(lon1, lat1, lon2, lat2)
    az_360 = (fwd_az + 360.0) % 360.0
    return float(dist_m), float(az_360)


def azimuth_to_compass(azimuth_deg: float) -> str:
    idx = int(round((azimuth_deg % 360.0) / 45.0)) % 8
    return COMPASS_DIRS[idx]


def is_within_supported_bbox(lat: float, lon: float) -> bool:
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return False
    in_indonesia_bbox = (
        settings.bbox_min_lat <= lat <= settings.bbox_max_lat
        and settings.bbox_min_lon <= lon <= settings.bbox_max_lon
    )
    if not in_indonesia_bbox:
        return False
    # Kecualikan wilayah daratan Singapura yang ikut tercakup di dalam persegi bbox Indonesia
    in_singapore = 1.22 <= lat <= 1.48 and 103.60 <= lon <= 104.04
    return not in_singapore


def is_within_sumsel_bbox(lat: float, lon: float) -> bool:
    """Alias kompatibilitas untuk pengecekan cakupan wilayah Indonesia."""
    return is_within_supported_bbox(lat, lon)


def parse_bbox_param(bbox: str) -> tuple[float, float, float, float]:
    """Parse string 'min_lon,min_lat,max_lon,max_lat' menjadi tuple float tervalidasi."""
    parts = [p.strip() for p in bbox.split(",")]
    if len(parts) != 4:
        raise ValueError("Format bbox tidak valid.")
    try:
        min_lon, min_lat, max_lon, max_lat = (float(x) for x in parts)
    except ValueError as exc:
        raise ValueError("Nilai bbox bukan angka.") from exc
    if not all(math.isfinite(v) for v in (min_lon, min_lat, max_lon, max_lat)):
        raise ValueError("Nilai bbox tidak valid.")
    if min_lon > max_lon or min_lat > max_lat:
        raise ValueError("Urutan koordinat bbox tidak valid.")
    return (min_lon, min_lat, max_lon, max_lat)
