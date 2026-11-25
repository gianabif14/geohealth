import pytest
from app.services.geo import azimuth_to_compass, geodesic_inverse, haversine_m, is_within_supported_bbox
from app.services.privacy import validate_and_cloak_location


def test_haversine_vs_geodesic_palembang_kayuagung():
    # Palembang (RSMH) ke Kayuagung (RSUD Kayuagung) ~48 km
    lat1, lon1 = -2.96639, 104.74972
    lat2, lon2 = -3.39120, 104.83050
    d_hav = haversine_m(lat1, lon1, lat2, lon2)
    d_geo, az = geodesic_inverse(lat1, lon1, lat2, lon2)

    assert 47_000 <= d_hav <= 49_000
    # Di dekat ekuator arah meridional, jari-jari kelengkungan ellipsoid WGS84 ~0.53% lebih kecil dari R rata-rata bola
    assert abs(d_hav - d_geo) / d_geo < 0.006
    assert 160.0 <= az <= 175.0
    assert azimuth_to_compass(az) == "Selatan"


def test_bbox_validation_and_cloaking():
    # Titik di berbagai pulau Indonesia harus valid
    assert is_within_supported_bbox(-2.976, 104.752) is True  # Palembang (Sumatera)
    assert is_within_supported_bbox(-6.200, 106.816) is True  # Jakarta (Jawa)
    assert is_within_supported_bbox(-5.147, 119.432) is True  # Makassar (Sulawesi)
    assert is_within_supported_bbox(-2.533, 140.718) is True  # Jayapura (Papua)

    # Titik di luar Indonesia harus ditolak
    assert is_within_supported_bbox(1.352, 103.819) is False  # Singapura
    assert is_within_supported_bbox(-12.463, 130.845) is False  # Darwin, Australia

    priv = validate_and_cloak_location(-2.96639, 104.74972, accuracy_m=25.0, exact=False)
    assert priv["query_lat"] == -2.966
    assert priv["query_lon"] == 104.75
    assert priv["dibulatkan_m"] == 110
    assert priv["peringatan_akurasi"] is None


def test_accuracy_gating_and_plausibility_check():
    priv_low_acc = validate_and_cloak_location(-2.96639, 104.74972, accuracy_m=850.0)
    assert priv_low_acc["peringatan_akurasi"] is not None
    assert "850 m" in priv_low_acc["peringatan_akurasi"]

    # Teleportasi dari Kayuagung ke Palembang (~48 km) dalam 10 detik (> 17.000 km/jam)
    priv_teleport = validate_and_cloak_location(
        lat=-2.96639,
        lon=104.74972,
        prev_lat=-3.39120,
        prev_lon=104.83050,
        dt_seconds=10.0,
    )
    assert priv_teleport["peringatan_plausibilitas"] is not None

    with pytest.raises(ValueError):
        validate_and_cloak_location(1.3521, 103.8198)  # Singapura di luar Indonesia ditolak
