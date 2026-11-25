import math
from app.services.geo import haversine_m, is_within_supported_bbox

ACCURACY_WARNING_THRESHOLD_M = 500.0
MAX_PLAUSIBLE_SPEED_KMH = 140.0


def validate_and_cloak_location(
    lat: float,
    lon: float,
    accuracy_m: float | None = None,
    exact: bool = False,
    prev_lat: float | None = None,
    prev_lon: float | None = None,
    dt_seconds: float | None = None,
) -> dict:
    if not is_within_supported_bbox(lat, lon):
        raise ValueError(
            "Lokasi berada di luar cakupan wilayah Indonesia. "
            "Pilih titik pada peta di wilayah Indonesia."
        )

    # 3 desimal derajat setara ~111 m di ekuator untuk minimisasi data sesuai UU PDP
    q_lat = round(lat, 5) if exact else round(lat, 3)
    q_lon = round(lon, 5) if exact else round(lon, 3)
    rounded_m = 1 if exact else 110

    acc_warning = None
    if accuracy_m is not None:
        if not math.isfinite(accuracy_m) or accuracy_m < 0:
            raise ValueError("Nilai akurasi lokasi tidak valid.")
        if accuracy_m > ACCURACY_WARNING_THRESHOLD_M:
            acc_warning = (
                f"Akurasi GPS perangkat saat ini rendah (\u00b1{int(round(accuracy_m))} m, di atas ambang "
                f"{int(ACCURACY_WARNING_THRESHOLD_M)} m). Jika urutan fasilitas kurang tepat, "
                "geser atau klik titik lokasi Anda langsung pada peta."
            )

    plausibility_warning = None
    if prev_lat is not None and prev_lon is not None and dt_seconds is not None and dt_seconds > 0:
        if is_within_supported_bbox(prev_lat, prev_lon):
            dist_m = haversine_m(prev_lat, prev_lon, lat, lon)
            speed_kmh = (dist_m / dt_seconds) * 3.6
            if speed_kmh > MAX_PLAUSIBLE_SPEED_KMH:
                plausibility_warning = (
                    f"Perpindahan lokasi terdeteksi sangat cepat ({speed_kmh:.0f} km/jam). "
                    "Pastikan mock location atau VPN lokasi tidak sedang aktif."
                )

    return {
        "query_lat": q_lat,
        "query_lon": q_lon,
        "dibulatkan_m": rounded_m,
        "peringatan_akurasi": acc_warning,
        "peringatan_plausibilitas": plausibility_warning,
    }
