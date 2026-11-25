let mapInstance = null;
let osmTileLayer = null;
let esriTileLayer = null;
let userLayerGroup = null;
let faskesLayerGroup = null;
let hotspotLayerGroup = null;
let kabupatenLayerGroup = null;
let h3LayerGroup = null;
let routeLayerGroup = null;
const markerById = new Map();

function prefersReducedMotion() {
  return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function createFacilitySvgIcon(jenis, isSelected = false) {
  const strokeW = isSelected ? 3 : 1.8;
  const strokeColor = isSelected ? "#B83A14" : "#FFFFFF";
  let svg = "";
  if (jenis === "rumah_sakit") {
    svg = `<svg width="30" height="30" viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">
      <circle cx="15" cy="15" r="12.5" fill="#14533C" stroke="${strokeColor}" stroke-width="${strokeW}"/>
      <circle cx="15" cy="15" r="9.5" fill="none" stroke="rgba(255,255,255,0.45)" stroke-width="1"/>
      <path d="M15 9.5v11M9.5 15h11" stroke="#FFFFFF" stroke-width="2.4" stroke-linecap="round"/>
    </svg>`;
  } else if (jenis === "puskesmas") {
    svg = `<svg width="26" height="26" viewBox="0 0 26 26" xmlns="http://www.w3.org/2000/svg">
      <rect x="3" y="3" width="20" height="20" rx="4" fill="#1F6F50" stroke="${strokeColor}" stroke-width="${strokeW}"/>
      <path d="M13 8v10M8 13h10" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round"/>
    </svg>`;
  } else {
    svg = `<svg width="26" height="26" viewBox="0 0 26 26" xmlns="http://www.w3.org/2000/svg">
      <polygon points="13,3 23,21.5 3,21.5" fill="#355670" stroke="${strokeColor}" stroke-width="${strokeW}"/>
    </svg>`;
  }
  const sz = jenis === "rumah_sakit" ? 30 : 26;
  return window.L.divIcon({
    className: "geo-marker-icon",
    html: svg,
    iconSize: [sz, sz],
    iconAnchor: [sz / 2, sz / 2],
    popupAnchor: [0, -sz / 2],
  });
}

function createUserLocationIcon() {
  const svg = `<svg width="26" height="26" viewBox="0 0 26 26" xmlns="http://www.w3.org/2000/svg">
    <circle cx="13" cy="13" r="10" fill="#1F2421" stroke="#FFFFFF" stroke-width="2.5"/>
    <circle cx="13" cy="13" r="4" fill="#F6F3EC"/>
  </svg>`;
  return window.L.divIcon({
    className: "geo-marker-icon",
    html: svg,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}

export function initMap(initialLat, initialLon, onMapPickPoint) {
  const L = window.L;
  mapInstance = L.map("peta-utama", {
    zoomControl: true,
    preferCanvas: true,
  }).setView([initialLat, initialLon], 10);

  // Gunakan basemap OpenStreetMap dan Esri Street dengan atribusi lengkap
  osmTileLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  });
  esriTileLayer = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
    {
      maxZoom: 19,
      attribution: "Tiles &copy; Esri, OpenStreetMap contributors",
    }
  );
  osmTileLayer.addTo(mapInstance);

  kabupatenLayerGroup = L.layerGroup().addTo(mapInstance);
  h3LayerGroup = L.layerGroup().addTo(mapInstance);
  userLayerGroup = L.layerGroup().addTo(mapInstance);
  hotspotLayerGroup = L.layerGroup().addTo(mapInstance);
  routeLayerGroup = L.layerGroup().addTo(mapInstance);
  faskesLayerGroup = L.layerGroup().addTo(mapInstance);

  mapInstance.on("click", (ev) => {
    if (onMapPickPoint) {
      onMapPickPoint(ev.latlng.lat, ev.latlng.lng);
    }
  });

  return mapInstance;
}

export function renderUserConcentricRings(lat, lon, radiusKm, accuracyM = null) {
  const L = window.L;
  userLayerGroup.clearLayers();

  // Motif identitas: lingkaran jangkauan konsentris 5 km, 10 km, dan radius pencarian aktif
  const innerRingsKm = [5, 10].filter((r) => r < radiusKm);
  innerRingsKm.forEach((rk) => {
    L.circle([lat, lon], {
      radius: rk * 1000,
      color: "#14533C",
      weight: 1,
      dashArray: "4 6",
      fill: false,
      interactive: false,
    }).addTo(userLayerGroup);
  });

  L.circle([lat, lon], {
    radius: radiusKm * 1000,
    color: "#14533C",
    weight: 1.8,
    fillColor: "#14533C",
    fillOpacity: 0.06,
    interactive: false,
  }).addTo(userLayerGroup);

  if (accuracyM && accuracyM > 20) {
    L.circle([lat, lon], {
      radius: accuracyM,
      color: "#4A524D",
      weight: 1.2,
      dashArray: "2 4",
      fillColor: "#4A524D",
      fillOpacity: 0.08,
      interactive: false,
    }).addTo(userLayerGroup);
  }

  L.marker([lat, lon], { icon: createUserLocationIcon() })
    .bindPopup(`<strong>Titik Acuan Pencarian</strong><br>Koordinat: ${lat.toFixed(4)}, ${lon.toFixed(4)}`)
    .addTo(userLayerGroup);
}

export function renderFacilitiesOnMap(facilities, selectedId, onSelectFacility, onRouteRequest) {
  const L = window.L;
  faskesLayerGroup.clearLayers();
  markerById.clear();

  facilities.forEach((f) => {
    const isSel = f.id === selectedId;
    const marker = L.marker([f.lat, f.lon], {
      icon: createFacilitySvgIcon(f.jenis, isSel),
      title: f.nama,
    });

    const distKm = f.jarak_m !== null && f.jarak_m !== undefined ? (f.jarak_m / 1000).toFixed(2) : "-";
    const st = f.status;
    const dtUpdated = new Date(st.diperbarui_pada).toLocaleString("id-ID", {
      dateStyle: "medium",
      timeStyle: "short",
    });

    const popupDiv = document.createElement("div");
    popupDiv.className = "map-popup-box";
    popupDiv.innerHTML = `
      <div style="font-weight:800;font-size:0.96rem;margin-bottom:4px;">${escapeHtml(f.nama)}</div>
      <div style="font-size:0.82rem;color:#4A524D;margin-bottom:6px;">
        ${escapeHtml(f.alamat || f.kabupaten || "Sumatera Selatan")}<br>
        <strong>Jarak garis lurus:</strong> ${distKm} km (${escapeHtml(f.arah_kompas || "-")})
      </div>
      <div style="font-size:0.82rem;margin-bottom:6px;">
        <strong>IGD 24 Jam:</strong> ${st.igd_24jam ? "Tersedia" : "Tidak"} |
        <strong>Oksigen:</strong> ${st.oksigen ? "Tersedia" : "Terbatas"}<br>
        <strong>Dokter Jaga:</strong> ${st.dokter_jaga ? "Aktif" : "Tidak"} |
        <strong>Tempat Tidur:</strong> ${st.tempat_tidur_tersedia} / ${st.tempat_tidur_total}
      </div>
      <div style="font-size:0.76rem;color:#4A524D;margin-bottom:8px;">
        Sumber status: <strong>Data ${escapeHtml(st.sumber)}</strong> (diperbarui ${escapeHtml(dtUpdated)})
      </div>
    `;

    const btnRoute = document.createElement("button");
    btnRoute.type = "button";
    btnRoute.className = "btn-primary-sm";
    btnRoute.textContent = "Buka rute ke fasilitas ini";
    btnRoute.addEventListener("click", () => {
      onRouteRequest(f);
    });
    popupDiv.appendChild(btnRoute);

    marker.bindPopup(popupDiv);
    marker.bindTooltip(`Klik untuk detail: ${escapeHtml(f.nama)}`, {
      direction: "top",
      offset: [0, -14],
      className: "geo-dark-tooltip",
    });
    marker.on("click", () => {
      onSelectFacility(f.id, false);
    });

    marker.addTo(faskesLayerGroup);
    markerById.set(f.id, marker);
  });
}

export function focusFacilityMarker(facility, openPopup = true) {
  if (!mapInstance || !facility) return;
  const opts = prefersReducedMotion() ? { animate: false } : { animate: true, duration: 0.45 };
  mapInstance.flyTo([facility.lat, facility.lon], Math.max(mapInstance.getZoom(), 12), opts);
  const mk = markerById.get(facility.id);
  if (mk && openPopup) {
    mk.openPopup();
  }
}

export function panMapTo(lat, lon, zoom = 11) {
  if (!mapInstance) return;
  const opts = prefersReducedMotion() ? { animate: false } : { animate: true, duration: 0.45 };
  mapInstance.flyTo([lat, lon], zoom, opts);
}

export function renderHotspotsLayer(geojson, visible = true) {
  const L = window.L;
  hotspotLayerGroup.clearLayers();
  if (!visible || !geojson || !geojson.features) return;

  geojson.features.forEach((feat) => {
    const [lon, lat] = feat.geometry.coordinates;
    const p = feat.properties;
    const marker = L.circleMarker([lat, lon], {
      radius: p.confidence === "high" ? 7 : 5.5,
      color: "#FFF3EB",
      weight: 1.5,
      fillColor: "#B83A14",
      fillOpacity: 0.88,
    });
    marker.bindPopup(
      `<strong>Titik Panas Satelit (${escapeHtml(p.satelit)})</strong><br>` +
      `Wilayah: ${escapeHtml(p.kabupaten || "Sumatera Selatan")}<br>` +
      `Confidence: ${escapeHtml(p.confidence)} | FRP: ${p.frp} MW<br>` +
      `Waktu akuisisi: ${escapeHtml(new Date(p.waktu_akuisisi).toLocaleString("id-ID"))}<br>` +
      `<em>Sumber: Data ${escapeHtml(p.sumber)} (indikator termal kontekstual)</em>`
    );
    marker.addTo(hotspotLayerGroup);
  });
}

export function renderKabupatenLayer(geojson, visible = true) {
  const L = window.L;
  kabupatenLayerGroup.clearLayers();
  if (!visible || !geojson || !geojson.features) return;

  L.geoJSON(geojson, {
    style: (feat) => ({
      color: feat.properties.is_pilot ? "#0F5C59" : "#6B726E",
      weight: feat.properties.is_pilot ? 2 : 1.2,
      dashArray: feat.properties.is_pilot ? "" : "4 4",
      fillColor: feat.properties.is_pilot ? "#0F5C59" : "#858C86",
      fillOpacity: feat.properties.is_pilot ? 0.04 : 0.02,
    }),
    onEachFeature: (feat, layer) => {
      const p = feat.properties;
      layer.bindTooltip(
        `${p.nama}${p.is_pilot ? " (Wilayah Pilot Karhutla)" : ""}`,
        { sticky: true }
      );
    },
  }).addTo(kabupatenLayerGroup);
}

export function renderH3CellsLayer(cells, visible = true) {
  const L = window.L;
  h3LayerGroup.clearLayers();
  if (!visible || !cells) return;

  cells.forEach((c) => {
    const fillColor = c.kategori === "tinggi" ? "#B83A14" : c.kategori === "sedang" ? "#C87A19" : "#0F5C59";
    const poly = L.polygon(c.boundary, {
      color: fillColor,
      weight: 2,
      fillColor,
      fillOpacity: 0.28,
    });
    poly.bindPopup(
      `<strong>Sel H3 ${escapeHtml(c.h3_index)}</strong><br>` +
      `Wilayah: ${escapeHtml(c.kabupaten || "Sumatera Selatan")}<br>` +
      `Skor akses terbatas: <strong>${c.skor} / 100 (${escapeHtml(c.kategori.toUpperCase())})</strong><br>` +
      `Hotspot 7 hari: ${c.n_hotspot} titik<br>` +
      `Jarak ke faskes siap (IGD+Oksigen): ${c.jarak_faskes_siap_km} km<br>` +
      `Faskes siap terdekat: ${escapeHtml(c.faskes_terdekat_nama || "-")}`
    );
    poly.addTo(h3LayerGroup);
  });
}

export function drawRouteLine(coordsLatLon, isStraightFallback = false) {
  const L = window.L;
  routeLayerGroup.clearLayers();
  const poly = L.polyline(coordsLatLon, {
    color: isStraightFallback ? "#B83A14" : "#14533C",
    weight: 4.5,
    dashArray: isStraightFallback ? "6 6" : "",
    opacity: 0.9,
  }).addTo(routeLayerGroup);

  if (mapInstance) {
    mapInstance.fitBounds(poly.getBounds(), { padding: [36, 36] });
  }
}

export function clearRouteLine() {
  if (routeLayerGroup) {
    routeLayerGroup.clearLayers();
  }
}

export function setBasemap(provider) {
  if (!mapInstance || !osmTileLayer || !esriTileLayer) return;
  if (provider === "esri") {
    if (mapInstance.hasLayer(osmTileLayer)) mapInstance.removeLayer(osmTileLayer);
    if (!mapInstance.hasLayer(esriTileLayer)) esriTileLayer.addTo(mapInstance);
  } else {
    if (mapInstance.hasLayer(esriTileLayer)) mapInstance.removeLayer(esriTileLayer);
    if (!mapInstance.hasLayer(osmTileLayer)) osmTileLayer.addTo(mapInstance);
  }
}

export function invalidateMapSize() {
  if (mapInstance) {
    setTimeout(() => mapInstance.invalidateSize(), 120);
  }
}

export function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
