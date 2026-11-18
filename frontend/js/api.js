export async function fetchMeta() {
  const res = await fetch("/api/meta");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchNearestFaskes(state) {
  const params = new URLSearchParams();
  params.set("lat", String(state.userLat));
  params.set("lon", String(state.userLon));
  params.set("radius_km", String(state.filters.radiusKm));
  params.set("k", "40");
  params.set("exact", state.filters.exactCoords ? "true" : "false");

  if (state.accuracyM !== null) {
    params.set("accuracy", String(Math.round(state.accuracyM)));
  }
  if (state.prevLat !== null && state.prevLon !== null && state.lastFixTimeMs !== null) {
    const dtSec = Math.max(1, (Date.now() - state.lastFixTimeMs) / 1000);
    params.set("prev_lat", String(state.prevLat));
    params.set("prev_lon", String(state.prevLon));
    params.set("dt_seconds", String(dtSec.toFixed(1)));
  }
  if (state.filters.jenis) params.set("jenis", state.filters.jenis);
  if (state.filters.oksigen) params.set("oksigen", "true");
  if (state.filters.igd24) params.set("igd24", "true");
  if (state.filters.dokter) params.set("dokter", "true");
  if (state.filters.ttMin > 0) params.set("tt_min", String(state.filters.ttMin));

  const res = await fetch(`/api/terdekat?${params.toString()}`);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.detail || `Permintaan gagal (${res.status})`);
  }
  return body;
}

export async function fetchHotspotsGeoJSON(days = 7) {
  const res = await fetch(`/api/hotspot?hari=${days}`);
  if (!res.ok) throw new Error(`Gagal memuat titik panas (${res.status})`);
  return res.json();
}

export async function fetchKabupatenGeoJSON() {
  const res = await fetch("/api/kabupaten");
  if (!res.ok) throw new Error(`Gagal memuat batas kabupaten (${res.status})`);
  return res.json();
}

export async function fetchAnalisisAkses() {
  const res = await fetch("/api/analisis/akses");
  if (!res.ok) throw new Error(`Gagal memuat analisis akses (${res.status})`);
  return res.json();
}

export async function fetchOsrmRoute(fromLat, fromLon, toLat, toLon) {
  const url = `https://router.project-osrm.org/route/v1/driving/${fromLon},${fromLat};${toLon},${toLat}?overview=full&geometries=geojson`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 6500);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) throw new Error(`OSRM HTTP ${res.status}`);
    const data = await res.json();
    if (!data.routes || data.routes.length === 0) {
      throw new Error("Rute jalan tidak ditemukan");
    }
    return data.routes[0];
  } finally {
    clearTimeout(timer);
  }
}
