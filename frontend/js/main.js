import {
  fetchAnalisisAkses,
  fetchHotspotsGeoJSON,
  fetchKabupatenGeoJSON,
  fetchMeta,
  fetchNearestFaskes,
  fetchOsrmRoute,
} from "./api.js";
import { bindFilterControls, syncFilterInputsFromState } from "./filters.js";
import { renderAnalysisTables, renderFacilityList } from "./list.js";
import {
  clearRouteLine,
  drawRouteLine,
  focusFacilityMarker,
  initMap,
  invalidateMapSize,
  panMapTo,
  renderFacilitiesOnMap,
  renderH3CellsLayer,
  renderHotspotsLayer,
  renderKabupatenLayer,
  renderUserConcentricRings,
} from "./map.js";
import { appState } from "./state.js";

let cachedHotspotsGeoJSON = null;
let cachedKabupatenGeoJSON = null;

function setUiState(mode, errorMessage = "") {
  const elLoading = document.getElementById("state-loading");
  const elError = document.getElementById("state-error");
  const elEmpty = document.getElementById("state-empty");
  const elList = document.getElementById("daftar-faskes");

  elLoading.classList.toggle("hidden", mode !== "loading");
  elError.classList.toggle("hidden", mode !== "error");
  elEmpty.classList.toggle("hidden", mode !== "empty");
  elList.classList.toggle("hidden", mode !== "ready");

  if (mode === "error" && errorMessage) {
    document.getElementById("teks-error-api").textContent = errorMessage;
  }
}

function updateLocationHeaderUI(privacyInfo = null) {
  const coordsSpan = document.getElementById("teks-koordinat");
  const roundNote = privacyInfo ? ` (dibulatkan \u00b1${privacyInfo.dibulatkan_m} m)` : "";
  coordsSpan.textContent = `${appState.userLabel} (${appState.userLat.toFixed(3)}, ${appState.userLon.toFixed(3)})${roundNote}`;

  const alertBox = document.getElementById("kotak-peringatan-lokasi");
  const warnings = [];
  if (privacyInfo?.peringatan_akurasi) warnings.push(privacyInfo.peringatan_akurasi);
  if (privacyInfo?.peringatan_plausibilitas) warnings.push(privacyInfo.peringatan_plausibilitas);

  if (warnings.length > 0) {
    alertBox.textContent = warnings.join(" ");
    alertBox.classList.remove("hidden");
  } else {
    alertBox.textContent = "";
    alertBox.classList.add("hidden");
  }
}

function updateSmokeContextStrip(hsCount5Km) {
  const strip = document.getElementById("kotak-konteks-asap");
  if (hsCount5Km > 0) {
    strip.classList.add("has-hotspot");
    strip.textContent = `Perhatian: Terdeteksi ${hsCount5Km} titik panas (hotspot) dalam radius 5 km dari titik acuan selama 7 hari terakhir. Prioritaskan faskes dengan oksigen aktif.`;
  } else {
    strip.classList.remove("has-hotspot");
    strip.textContent = "Tidak ada titik panas dalam radius 5 km dari titik acuan (7 hari terakhir).";
  }
}

function getFilteredFacilitiesForDisplay() {
  const q = appState.filters.q.toLowerCase();
  if (!q) return appState.facilities;
  return appState.facilities.filter((f) => {
    const hay = `${f.nama} ${f.alamat || ""} ${f.kabupaten || ""}`.toLowerCase();
    return hay.includes(q);
  });
}

function refreshDisplayedListAndMarkers() {
  const list = getFilteredFacilitiesForDisplay();
  document.getElementById("badge-count-faskes").textContent = String(list.length);

  renderFacilitiesOnMap(
    list,
    appState.selectedFacilityId,
    handleSelectFacility,
    handleOpenRoute
  );

  if (list.length === 0) {
    setUiState("empty");
    return;
  }

  setUiState("ready");
  renderFacilityList(
    list,
    appState.selectedFacilityId,
    handleSelectFacility,
    handleOpenRoute
  );
}

async function reloadNearestFacilities() {
  setUiState("loading");
  renderUserConcentricRings(
    appState.userLat,
    appState.userLon,
    appState.filters.radiusKm,
    appState.accuracyM
  );

  try {
    const data = await fetchNearestFaskes(appState);
    appState.facilities = (data.hasil || []).map((f) => ({
      ...f,
      _userLat: appState.userLat,
      _userLon: appState.userLon,
    }));
    updateLocationHeaderUI(data.privasi);
    updateSmokeContextStrip(data.hotspot_sekitar_5km);
    refreshDisplayedListAndMarkers();
  } catch (err) {
    setUiState("error", err.message || "Gagal memuat data fasilitas terdekat.");
  }
}

function handleSelectFacility(faskesId, shouldFly = true) {
  appState.selectedFacilityId = faskesId;
  const target = appState.facilities.find((f) => f.id === faskesId);
  refreshDisplayedListAndMarkers();
  if (target && shouldFly) {
    focusFacilityMarker(target, true);
  }
}

async function handleOpenRoute(facility) {
  appState.selectedFacilityId = facility.id;
  const routeBanner = document.getElementById("status-rute-aktif");
  const routeText = document.getElementById("teks-rute-aktif");
  routeBanner.classList.remove("hidden");
  routeText.textContent = `Menghitung rute ke ${facility.nama}...`;

  const straightKm = facility.jarak_m ? (facility.jarak_m / 1000).toFixed(2) : "-";

  try {
    const route = await fetchOsrmRoute(
      appState.userLat,
      appState.userLon,
      facility.lat,
      facility.lon
    );
    const coordsLatLon = route.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
    const roadKm = (route.distance / 1000).toFixed(2);
    const roadMin = Math.max(1, Math.round(route.duration / 60));
    drawRouteLine(coordsLatLon, false);
    routeText.innerHTML = `<strong>Rute jalan OSRM ke ${facility.nama}:</strong> ${roadKm} km (\u00b1${roadMin} menit berkendara; jarak garis lurus ${straightKm} km).`;
  } catch (_err) {
    // Sesuai strategi mitigasi Risiko #5 laporan awal: gunakan garis lurus Haversine bila OSRM gagal/kuota habis
    drawRouteLine(
      [
        [appState.userLat, appState.userLon],
        [facility.lat, facility.lon],
      ],
      true
    );
    routeText.innerHTML = `<strong>Jarak garis lurus (Haversine) ke ${facility.nama}:</strong> ${straightKm} km arah ${facility.arah_kompas || "-"}. (Layanan rute jalan OSRM publik sedang tidak terjangkau, menampilkan garis lurus).`;
  }
}

function setActiveUserPoint(lat, lon, label, accuracyM = null, shouldPan = true) {
  appState.prevLat = appState.userLat;
  appState.prevLon = appState.userLon;
  appState.userLat = lat;
  appState.userLon = lon;
  appState.userLabel = label;
  appState.accuracyM = accuracyM;
  appState.lastFixTimeMs = Date.now();

  clearRouteLine();
  document.getElementById("status-rute-aktif").classList.add("hidden");

  if (shouldPan) {
    panMapTo(lat, lon, 11);
  }
  reloadNearestFacilities();
}

function bindTopbarAndPresetEvents() {
  document.querySelectorAll(".chip-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".chip-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const lat = parseFloat(btn.dataset.lat);
      const lon = parseFloat(btn.dataset.lon);
      const nama = btn.dataset.nama || "Titik Pilihan";
      setActiveUserPoint(lat, lon, nama, null, true);
    });
  });

  // Tombol 1-klik "Cari IGD terdekat" (saran pengembangan dari laporan LBS Hospital App)
  document.getElementById("btn-igd-darurat").addEventListener("click", async () => {
    switchTab("faskes");
    appState.filters.igd24 = true;
    appState.filters.oksigen = true;
    appState.filters.jenis = "";
    appState.filters.q = "";
    if (appState.filters.radiusKm < 60) {
      appState.filters.radiusKm = 60;
    }
    syncFilterInputsFromState(appState);
    await reloadNearestFacilities();
    if (appState.facilities.length > 0) {
      const nearestIgd = appState.facilities[0];
      handleSelectFacility(nearestIgd.id, true);
      handleOpenRoute(nearestIgd);
    }
  });

  document.getElementById("btn-pakai-gps").addEventListener("click", () => {
    const alertBox = document.getElementById("kotak-peringatan-lokasi");
    if (!("geolocation" in navigator)) {
      alertBox.textContent = "Peramban ini tidak mendukung Geolocation API. Silakan klik titik lokasi Anda langsung di peta.";
      alertBox.classList.remove("hidden");
      return;
    }
    alertBox.textContent = "Meminta posisi GPS dari peramban...";
    alertBox.classList.remove("hidden");

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude, accuracy } = pos.coords;
        document.querySelectorAll(".chip-btn").forEach((b) => b.classList.remove("active"));
        setActiveUserPoint(latitude, longitude, "Lokasi GPS Saya", accuracy, true);
      },
      (err) => {
        alertBox.textContent = `Akses GPS ditolak atau gagal (${err.message}). Anda tetap dapat memilih titik lokasi langsung pada peta atau memakai tombol lokasi cepat.`;
        alertBox.classList.remove("hidden");
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  });

  document.getElementById("btn-hapus-rute").addEventListener("click", () => {
    clearRouteLine();
    document.getElementById("status-rute-aktif").classList.add("hidden");
  });

  document.getElementById("btn-coba-lagi").addEventListener("click", () => {
    reloadNearestFacilities();
  });

  document.getElementById("btn-reset-filter").addEventListener("click", () => {
    appState.filters.q = "";
    appState.filters.jenis = "";
    appState.filters.oksigen = false;
    appState.filters.igd24 = false;
    appState.filters.dokter = false;
    appState.filters.ttMin = 0;
    appState.filters.radiusKm = 80;
    syncFilterInputsFromState(appState);
    reloadNearestFacilities();
  });

  // Dialog Metodologi & Privasi (dapat ditutup dengan Escape maupun tombol)
  const dialog = document.getElementById("dialog-info");
  const btnOpenDialog = document.getElementById("btn-buka-metodologi");
  const btnCloseDialog = document.getElementById("btn-tutup-dialog");

  btnOpenDialog.addEventListener("click", () => {
    dialog.showModal();
  });

  btnCloseDialog.addEventListener("click", () => {
    dialog.close();
    btnOpenDialog.focus();
  });

  dialog.addEventListener("click", (ev) => {
    if (ev.target === dialog) {
      dialog.close();
      btnOpenDialog.focus();
    }
  });

  // Mobile bottom sheet toggle
  const btnSheet = document.getElementById("btn-toggle-sheet");
  const panelKontrol = document.getElementById("panel-kontrol");
  const labelSheet = document.getElementById("sheet-toggle-label");
  btnSheet.addEventListener("click", () => {
    const isCollapsed = panelKontrol.classList.toggle("sheet-collapsed");
    btnSheet.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
    labelSheet.textContent = isCollapsed
      ? "Tampilkan daftar & filter faskes"
      : "Sembunyikan panel daftar";
    invalidateMapSize();
  });
}

function switchTab(tabName) {
  const btnFaskes = document.getElementById("tab-btn-faskes");
  const btnAnalisis = document.getElementById("tab-btn-analisis");
  const paneFaskes = document.getElementById("pane-faskes");
  const paneAnalisis = document.getElementById("pane-analisis");

  const isFaskes = tabName === "faskes";
  btnFaskes.classList.toggle("active", isFaskes);
  btnFaskes.setAttribute("aria-selected", isFaskes ? "true" : "false");
  btnAnalisis.classList.toggle("active", !isFaskes);
  btnAnalisis.setAttribute("aria-selected", !isFaskes ? "true" : "false");

  paneFaskes.classList.toggle("hidden", !isFaskes);
  paneAnalisis.classList.toggle("hidden", isFaskes);

  if (!isFaskes) {
    appState.layers.showH3 = document.getElementById("chk-layer-h3").checked;
    if (appState.analysisData) {
      renderH3CellsLayer(appState.analysisData.sel_h3, appState.layers.showH3);
    }
  } else {
    renderH3CellsLayer([], false);
  }
}

function bindTabs() {
  document.getElementById("tab-btn-faskes").addEventListener("click", () => switchTab("faskes"));
  document.getElementById("tab-btn-analisis").addEventListener("click", () => switchTab("analisis"));
}

async function initContextualLayersAndAnalysis() {
  try {
    const [meta, hsGeo, kabGeo, analisis] = await Promise.all([
      fetchMeta(),
      fetchHotspotsGeoJSON(7),
      fetchKabupatenGeoJSON(),
      fetchAnalisisAkses(),
    ]);

    cachedHotspotsGeoJSON = hsGeo;
    cachedKabupatenGeoJSON = kabGeo;
    appState.analysisData = analisis;

    renderHotspotsLayer(cachedHotspotsGeoJSON, appState.layers.showHotspot);
    renderKabupatenLayer(cachedKabupatenGeoJSON, appState.layers.showKabupaten);

    renderAnalysisTables(analisis, (cell) => {
      panMapTo(cell.centroid_lat, cell.centroid_lon, 11);
    });

    const footnote = document.getElementById("teks-meta-ringkas");
    footnote.textContent = `${meta.total_faskes} faskes (${Object.keys(meta.faskes_per_sumber).join(", ")}) \u00b7 ${meta.total_hotspot} hotspot 7 hari (sumber: ${Object.keys(meta.hotspot_per_sumber).join(", ")}) \u00b7 Kapasitas: Data simulasi berlabel.`;
  } catch (_err) {
    // Lapisan kontekstual gagal tidak memblokir pencarian utama
  }
}

window.addEventListener("DOMContentLoaded", () => {
  initMap(appState.userLat, appState.userLon, (lat, lon) => {
    document.querySelectorAll(".chip-btn").forEach((b) => b.classList.remove("active"));
    setActiveUserPoint(lat, lon, "Titik Pilihan Peta", null, false);
  });

  bindTabs();
  bindTopbarAndPresetEvents();
  bindFilterControls(appState, {
    onFilterChange: () => reloadNearestFacilities(),
    onLocalSearchChange: () => refreshDisplayedListAndMarkers(),
    onLayerToggle: () => {
      renderHotspotsLayer(cachedHotspotsGeoJSON, appState.layers.showHotspot);
      renderKabupatenLayer(cachedKabupatenGeoJSON, appState.layers.showKabupaten);
      if (appState.analysisData) {
        const isAnalisisTab = !document.getElementById("pane-analisis").classList.contains("hidden");
        renderH3CellsLayer(
          appState.analysisData.sel_h3,
          isAnalisisTab && appState.layers.showH3
        );
      }
    },
  });

  reloadNearestFacilities();
  initContextualLayersAndAnalysis();
});
