import time
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_meta_endpoint():
    r = client.get("/api/meta")
    assert r.status_code == 200
    data = r.json()
    assert data["wilayah_cakupan"] == "Indonesia"
    assert data["total_faskes"] >= 28
    assert data["total_hotspot"] >= 20
    assert len(data["kabupaten_pilot"]) >= 4


def test_terdekat_indonesia_coverage_and_privacy():
    # Koordinat di luar Indonesia (Singapura & Darwin, Australia) harus mengembalikan 422
    for out_lat, out_lon in [(1.3521, 103.8198), (-12.4634, 130.8456)]:
        r_out = client.get(f"/api/terdekat?lat={out_lat}&lon={out_lon}")
        assert r_out.status_code == 422
        assert "Indonesia" in r_out.json()["detail"]

    # Koordinat valid di berbagai pulau Indonesia tidak boleh ditolak dan tidak memantulkan koordinat mentah
    pulau_coords = [
        ("3.59521234", "98.67221234"),    # Medan (Sumatera)
        ("-2.21611234", "113.91391234"), # Palangka Raya (Kalimantan)
        ("-5.14771234", "119.43271234"), # Makassar (Sulawesi)
        ("-2.53371234", "140.71811234"), # Jayapura (Papua)
    ]
    for raw_lat, raw_lon in pulau_coords:
        r_ok = client.get(f"/api/terdekat?lat={raw_lat}&lon={raw_lon}&radius_km=30")
        assert r_ok.status_code == 200
        assert r_ok.headers.get("Cache-Control") == "no-store"
        assert r_ok.headers.get("X-Privacy-Policy") == "no-location-retention"
        assert raw_lat not in r_ok.text
        assert raw_lon not in r_ok.text

    # Uji spesifik di Palembang untuk akurasi rendah & hasil faskes terdekat
    raw_lat = "-2.96639123"
    raw_lon = "104.74972199"
    r_plg = client.get(f"/api/terdekat?lat={raw_lat}&lon={raw_lon}&radius_km=30&accuracy=650")
    assert r_plg.status_code == 200
    payload = r_plg.json()
    assert payload["privasi"]["dibulatkan_m"] == 110
    assert payload["privasi"]["peringatan_akurasi"] is not None
    assert payload["jumlah_ditemukan"] > 0


def test_kabupaten_and_hotspot_bbox_filtering():
    r_kab = client.get("/api/kabupaten?bbox=104.5,-3.2,105.0,-2.8")
    assert r_kab.status_code == 200
    assert r_kab.json()["type"] == "FeatureCollection"

    r_kab_bad = client.get("/api/kabupaten?bbox=invalid")
    assert r_kab_bad.status_code == 422

    r_hs = client.get("/api/hotspot?hari=7&bbox=101.8,-5.2,106.4,-1.4&limit=5")
    assert r_hs.status_code == 200
    assert len(r_hs.json()["features"]) <= 5


def test_analisis_akses_endpoint_and_performance():
    t0 = time.perf_counter()
    r = client.get("/api/analisis/akses")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert r.status_code == 200
    assert elapsed_ms < 500.0
    data = r.json()
    assert len(data["kabupaten_ranking"]) >= 4
    assert 0 < len(data["sel_h3"]) <= 50

    r_lim = client.get("/api/analisis/akses?limit=2")
    assert r_lim.status_code == 200
    assert len(r_lim.json()["sel_h3"]) <= 2
