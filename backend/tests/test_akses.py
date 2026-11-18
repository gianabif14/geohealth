from app.services.akses import compute_h3_access_scores


def test_h3_access_score_ranking():
    # Titik A di pedalaman OKI (banyak hotspot, jauh dari RS siap) vs Titik B di dekat Palembang
    hotspots = [
        {"lat": -3.551, "lon": 105.420, "kabupaten": "Kabupaten Ogan Komering Ilir"},
        {"lat": -3.553, "lon": 105.422, "kabupaten": "Kabupaten Ogan Komering Ilir"},
        {"lat": -3.555, "lon": 105.419, "kabupaten": "Kabupaten Ogan Komering Ilir"},
        {"lat": -2.970, "lon": 104.750, "kabupaten": "Kota Palembang"},
    ]
    ready_faskes = [
        {"id": 1, "nama": "RSUP Dr. Mohammad Hoesin Palembang", "lat": -2.96639, "lon": 104.74972},
    ]

    cells = compute_h3_access_scores(hotspots=hotspots, ready_faskes=ready_faskes)
    assert len(cells) == 2
    # Sel pertama haruslah sel di OKI karena jauh dari faskes siap DAN hotspot lebih padat
    assert cells[0]["kabupaten"] == "Kabupaten Ogan Komering Ilir"
    assert cells[0]["skor"] > cells[1]["skor"]
    assert cells[0]["jarak_faskes_siap_km"] > 80.0
    assert cells[1]["jarak_faskes_siap_km"] < 5.0
