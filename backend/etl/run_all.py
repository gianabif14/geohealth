from app.db import close_pools, get_backend_mode, query_faskes_list, query_meta_summary
from etl.fetch_firms import load_hotspots
from etl.fetch_osm import load_osm_faskes
from etl.import_csv import import_custom_csvs
from etl.load_admin import load_admin_boundaries
from etl.simulate_status import generate_simulated_statuses


def run_all_etl() -> dict:
    try:
        mode = get_backend_mode()
        n_kab = load_admin_boundaries()
        n_faskes, n_live_osm = load_osm_faskes()
        n_csv = import_custom_csvs()
        n_sim = generate_simulated_statuses()
        n_hs, hs_src = load_hotspots()
        meta = query_meta_summary()

        print(f"[ETL] Engine aktif          : {mode}")
        print(f"[ETL] Kabupaten/Kota dimuat : {n_kab}")
        print(f"[ETL] Faskes OSM + acuan    : {n_faskes} (Overpass live: {n_live_osm}, CSV nasional: {n_csv})")
        print(f"[ETL] Status disimulasikan  : {n_sim}")
        print(f"[ETL] Hotspot dimuat        : {n_hs} (sumber: {hs_src})")

        samples = query_faskes_list()[:10]
        print("\n[Verifikasi Sampel 10 Koordinat Faskes Indonesia]")
        for idx, s in enumerate(samples, 1):
            print(
                f"  {idx:2d}. {s['nama']} ({s['jenis']}) -> "
                f"({s['lat']:.5f}, {s['lon']:.5f}) | {s['kabupaten']} | sumber={s['sumber']}"
            )
        return meta
    finally:
        close_pools()


if __name__ == "__main__":
    run_all_etl()
