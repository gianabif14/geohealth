from app.db import query_faskes_list, query_nearest_faskes
from app.services.geo import haversine_m


def test_knn_matches_pure_haversine_order():
    user_lat, user_lon = -2.975, 104.750  # Pusat Kota Palembang
    nearest, hs_5km = query_nearest_faskes(lat=user_lat, lon=user_lon, k=10, radius_km=60.0)
    assert len(nearest) >= 5
    assert isinstance(hs_5km, int)

    distances = [item["jarak_m"] for item in nearest]
    assert distances == sorted(distances)

    all_faskes = query_faskes_list()
    manual = sorted(
        (
            (round(haversine_m(user_lat, user_lon, f["lat"], f["lon"]), 1), f["id"])
            for f in all_faskes
            if haversine_m(user_lat, user_lon, f["lat"], f["lon"]) <= 60_000.0
        ),
        key=lambda x: x[0],
    )[:10]

    assert [item["id"] for item in nearest] == [m[1] for m in manual]


def test_filter_combinations_igd_and_oksigen():
    user_lat, user_lon = -3.390, 104.830  # Kayuagung OKI
    nearest_ready, _ = query_nearest_faskes(
        lat=user_lat,
        lon=user_lon,
        k=15,
        radius_km=80.0,
        igd24=True,
        oksigen=True,
    )
    assert len(nearest_ready) > 0
    for f in nearest_ready:
        assert f["status"]["igd_24jam"] is True
        assert f["status"]["oksigen"] is True
        assert f["status"]["sumber"] in ("simulasi", "manual", "osm")
