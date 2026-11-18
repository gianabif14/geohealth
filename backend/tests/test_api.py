from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_meta_endpoint():
    r = client.get("/api/meta")
    assert r.status_code == 200
    data = r.json()
    assert data["wilayah_cakupan"] == "Provinsi Sumatera Selatan"
    assert data["total_faskes"] >= 28
    assert data["total_hotspot"] >= 20
    assert len(data["kabupaten_pilot"]) == 4


def test_terdekat_rejects_outside_sumsel_and_protects_privacy():
    # Koordinat di luar Sumatera Selatan harus mengembalikan 422
    r_out = client.get("/api/terdekat?lat=-7.795&lon=110.369")
    assert r_out.status_code == 422
    assert "Sumatera Selatan" in r_out.json()["detail"]

    # Koordinat valid di Palembang tidak boleh memantulkan koordinat mentah dan wajib memiliki header no-store
    raw_lat = "-2.96639123"
    raw_lon = "104.74972199"
    r_ok = client.get(f"/api/terdekat?lat={raw_lat}&lon={raw_lon}&radius_km=30&accuracy=650")
    assert r_ok.status_code == 200
    assert r_ok.headers.get("Cache-Control") == "no-store"
    assert r_ok.headers.get("X-Privacy-Policy") == "no-location-retention"
    body_text = r_ok.text
    assert raw_lat not in body_text
    assert raw_lon not in body_text
    payload = r_ok.json()
    assert payload["privasi"]["dibulatkan_m"] == 110
    assert payload["privasi"]["peringatan_akurasi"] is not None
    assert payload["jumlah_ditemukan"] > 0


def test_analisis_akses_endpoint():
    r = client.get("/api/analisis/akses")
    assert r.status_code == 200
    data = r.json()
    assert len(data["kabupaten_ranking"]) >= 4
    assert len(data["sel_h3"]) > 0
