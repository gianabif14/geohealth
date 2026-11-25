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
  getMapViewport,
  initMap,
  invalidateMapSize,
  panMapTo,
  renderFacilitiesOnMap,
  renderH3CellsLayer,
  renderHotspotsLayer,
  renderKabupatenLayer,
  renderUserConcentricRings,
  setBasemap,
} from "./map.js";
import { appState } from "./state.js";

let cachedHotspotsGeoJSON = null;
let cachedKabupatenGeoJSON = null;
let latestFaskesReqId = 0;
let viewportTimer = null;
let latestViewportReqId = 0;

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

  const topbarLocLabel = document.getElementById("topbar-loc-label");
  if (topbarLocLabel) {
    topbarLocLabel.textContent = appState.userLabel;
  }

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
    document.getElementById("daftar-faskes").innerHTML = "";
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
  const reqId = ++latestFaskesReqId;
  setUiState("loading");
  renderUserConcentricRings(
    appState.userLat,
    appState.userLon,
    appState.filters.radiusKm,
    appState.accuracyM
  );

  try {
    const data = await fetchNearestFaskes(appState);
    if (reqId !== latestFaskesReqId) return;
    appState.facilities = (data.hasil || []).map((f) => ({
      ...f,
      _userLat: appState.userLat,
      _userLon: appState.userLon,
    }));
    updateLocationHeaderUI(data.privasi);
    updateSmokeContextStrip(data.hotspot_sekitar_5km);
    refreshDisplayedListAndMarkers();
  } catch (err) {
    if (reqId !== latestFaskesReqId) return;
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

  // Pencarian lokasi nasional melalui Nominatim (OpenStreetMap)
  const inputLokasi = document.getElementById("input-cari-lokasi");
  const btnCariLokasi = document.getElementById("btn-cari-lokasi");
  const statusCari = document.getElementById("status-cari-lokasi");
  const hasilCari = document.getElementById("hasil-cari-lokasi");

  async function searchNationalLocation() {
    const query = inputLokasi.value.trim();
    if (query.length < 3) {
      statusCari.textContent = "Masukkan minimal 3 karakter nama kota atau lokasi.";
      hasilCari.classList.add("hidden");
      return;
    }
    statusCari.textContent = "Mencari lokasi...";
    hasilCari.classList.add("hidden");
    btnCariLokasi.disabled = true;
    try {
      const params = new URLSearchParams({
        q: query,
        format: "jsonv2",
        addressdetails: "1",
        limit: "6",
        countrycodes: "id",
      });
      const response = await fetch(`https://nominatim.openstreetmap.org/search?${params}`);
      if (!response.ok) throw new Error(`Layanan pencarian merespons ${response.status}`);
      const results = await response.json();
      hasilCari.innerHTML = "";
      if (!results.length) {
        statusCari.textContent = "Lokasi tidak ditemukan. Coba nama kota atau kabupaten lain.";
        return;
      }
      results.forEach((place) => {
        const li = document.createElement("li");
        const button = document.createElement("button");
        button.type = "button";
        button.className = "location-result-btn";
        button.textContent = place.display_name;
        button.addEventListener("click", () => {
          const lat = Number(place.lat);
          const lon = Number(place.lon);
          const label = place.name || place.display_name.split(",")[0];
          if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
          document.querySelectorAll(".chip-btn").forEach((b) => b.classList.remove("active"));
          setActiveUserPoint(lat, lon, label, null, true);
          statusCari.textContent = `Lokasi dipilih: ${place.display_name}`;
          hasilCari.classList.add("hidden");
        });
        li.appendChild(button);
        hasilCari.appendChild(li);
      });
      hasilCari.classList.remove("hidden");
      statusCari.textContent = `${results.length} hasil ditemukan. Pilih salah satu lokasi.`;
    } catch (error) {
      statusCari.textContent = `Pencarian gagal: ${error.message}. Periksa koneksi internet.`;
    } finally {
      btnCariLokasi.disabled = false;
    }
  }
  btnCariLokasi.addEventListener("click", searchNationalLocation);
  inputLokasi.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      searchNationalLocation();
    }
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

  // Desktop right drawer hide/show toggle
  const btnDrawer = document.getElementById("btn-toggle-drawer");
  const labelDrawer = document.getElementById("drawer-toggle-label");
  if (btnDrawer && labelDrawer) {
    btnDrawer.addEventListener("click", () => {
      const isCollapsed = panelKontrol.classList.toggle("drawer-collapsed");
      btnDrawer.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
      labelDrawer.textContent = isCollapsed ? "Tampilkan" : "Sembunyikan";
      invalidateMapSize();
    });
  }

  // Segmented basemap switcher (top-left)
  const btnOsm = document.getElementById("btn-basemap-osm");
  const btnEsri = document.getElementById("btn-basemap-esri");
  if (btnOsm && btnEsri) {
    btnOsm.addEventListener("click", () => {
      setBasemap("osm");
      btnOsm.classList.add("active");
      btnOsm.setAttribute("aria-pressed", "true");
      btnEsri.classList.remove("active");
      btnEsri.setAttribute("aria-pressed", "false");
    });
    btnEsri.addEventListener("click", () => {
      setBasemap("esri");
      btnEsri.classList.add("active");
      btnEsri.setAttribute("aria-pressed", "true");
      btnOsm.classList.remove("active");
      btnOsm.setAttribute("aria-pressed", "false");
    });
  }

  // Fullscreen map toggle (top-left)
  const btnFullscreen = document.getElementById("btn-fullscreen-map");
  if (btnFullscreen) {
    btnFullscreen.addEventListener("click", async () => {
      try {
        if (!document.fullscreenElement) {
          await document.documentElement.requestFullscreen();
          btnFullscreen.setAttribute("aria-pressed", "true");
        } else {
          await document.exitFullscreen();
          btnFullscreen.setAttribute("aria-pressed", "false");
        }
      } catch (_err) {
        // Ignore if fullscreen is blocked by browser policy
      }
      invalidateMapSize();
    });
  }

  // Collapsible accordion cards in right drawer
  document.querySelectorAll("[data-accordion]").forEach((card) => {
    const toggle = card.querySelector(".accordion-toggle");
    if (!toggle) return;
    const iconMinus = toggle.querySelector(".icon-minus");
    const iconPlus = toggle.querySelector(".icon-plus");
    toggle.addEventListener("click", () => {
      const collapsed = card.classList.toggle("is-collapsed");
      toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      if (iconMinus && iconPlus) {
        iconMinus.classList.toggle("hidden", collapsed);
        iconPlus.classList.toggle("hidden", !collapsed);
      }
    });
  });
}

function switchTab(tabName) {
  const btnFaskes = document.getElementById("tab-btn-faskes");
  const btnAnalisis = document.getElementById("tab-btn-analisis");
  const paneFaskes = document.getElementById("pane-faskes");
  const paneAnalisis = document.getElementById("pane-analisis");
  const panelKontrol = document.getElementById("panel-kontrol");
  const scrollBox = document.getElementById("drawer-cards-scroll");

  const isFaskes = tabName === "faskes";
  btnFaskes.classList.toggle("active", isFaskes);
  btnFaskes.setAttribute("aria-selected", isFaskes ? "true" : "false");
  btnAnalisis.classList.toggle("active", !isFaskes);
  btnAnalisis.setAttribute("aria-selected", !isFaskes ? "true" : "false");

  paneFaskes.classList.toggle("hidden", !isFaskes);
  paneAnalisis.classList.toggle("hidden", isFaskes);

  // Pastikan drawer/sheet terbuka saat pengguna mengganti tab
  if (panelKontrol && panelKontrol.classList.contains("drawer-collapsed")) {
    panelKontrol.classList.remove("drawer-collapsed");
    const btnDrawer = document.getElementById("btn-toggle-drawer");
    const labelDrawer = document.getElementById("drawer-toggle-label");
    if (btnDrawer) btnDrawer.setAttribute("aria-expanded", "true");
    if (labelDrawer) labelDrawer.textContent = "Sembunyikan";
    invalidateMapSize();
  }
  if (panelKontrol && panelKontrol.classList.contains("sheet-collapsed")) {
    panelKontrol.classList.remove("sheet-collapsed");
    const btnSheet = document.getElementById("btn-toggle-sheet");
    const labelSheet = document.getElementById("sheet-toggle-label");
    if (btnSheet) btnSheet.setAttribute("aria-expanded", "true");
    if (labelSheet) labelSheet.textContent = "Sembunyikan panel daftar";
    invalidateMapSize();
  }
  if (scrollBox) {
    scrollBox.scrollTop = 0;
  }

  if (!isFaskes) {
    appState.layers.showH3 = document.getElementById("chk-layer-h3").checked;
    if (appState.analysisData) {
      renderH3CellsLayer(appState.analysisData.sel_h3, appState.layers.showH3);
    } else {
      loadAnalysisOnly();
    }
  } else {
    renderH3CellsLayer([], false);
  }
}

async function loadAnalysisOnly() {
  const box = document.getElementById("analisis-state-box");
  const title = document.getElementById("analisis-state-title");
  const desc = document.getElementById("analisis-state-desc");
  if (box) {
    box.classList.remove("hidden", "state-error");
    title.textContent = "Memuat analisis akses H3...";
    desc.textContent = "Menghitung skor keterbatasan akses dan peringkat wilayah Indonesia.";
  }
  try {
    const analisis = await fetchAnalisisAkses();
    appState.analysisData = analisis;
    renderAnalysisTables(analisis, (cell) => {
      panMapTo(cell.centroid_lat, cell.centroid_lon, 11);
    });
    const isAnalisisTab = !document.getElementById("pane-analisis").classList.contains("hidden");
    if (isAnalisisTab) {
      renderH3CellsLayer(analisis.sel_h3, appState.layers.showH3);
    }
    if (box) box.classList.add("hidden");
  } catch (err) {
    if (box) {
      box.classList.remove("hidden");
      box.classList.add("state-error");
      title.textContent = "Gagal memuat analisis akses";
      desc.textContent = err.message || "Pastikan layanan backend sedang berjalan di http://127.0.0.1:8000.";
    }
  }
}

function bindTabs() {
  document.getElementById("tab-btn-faskes").addEventListener("click", () => switchTab("faskes"));
  document.getElementById("tab-btn-analisis").addEventListener("click", () => switchTab("analisis"));
}

async function initContextualLayersAndAnalysis() {
  try {
    const [meta, analisis] = await Promise.all([
      fetchMeta(),
      fetchAnalisisAkses(),
    ]);
    appState.analysisData = analisis;
    renderAnalysisTables(analisis, (cell) => {
      panMapTo(cell.centroid_lat, cell.centroid_lon, 11);
    });
    const footnote = document.getElementById("teks-meta-ringkas");
    footnote.textContent = `${meta.total_faskes} faskes (${Object.keys(meta.faskes_per_sumber).join(", ")}) · ${meta.total_hotspot} hotspot 7 hari (sumber: ${Object.keys(meta.hotspot_per_sumber).join(", ")}) · Cakupan: Indonesia · Kapasitas: Data simulasi berlabel.`;
  } catch (_err) {
    // Lapisan kontekstual gagal tidak memblokir pencarian utama
  }
}

function scheduleViewportLayers({ bbox, zoom }) {
  window.clearTimeout(viewportTimer);
  viewportTimer = window.setTimeout(async () => {
    const requestId = ++latestViewportReqId;
    try {
      const hsGeo = await fetchHotspotsGeoJSON(appState.layers.hotspotDays, bbox);
      if (requestId !== latestViewportReqId) return;
      cachedHotspotsGeoJSON = hsGeo;
      renderHotspotsLayer(cachedHotspotsGeoJSON, appState.layers.showHotspot);
    } catch (_err) {
      // Pertahankan layer terakhir bila jaringan sedang bermasalah.
    }

    if (zoom >= 7) {
      try {
        const kabGeo = await fetchKabupatenGeoJSON();
        if (requestId !== latestViewportReqId) return;
        cachedKabupatenGeoJSON = kabGeo;
        const viewport = getMapViewport();
      renderKabupatenLayer(
        cachedKabupatenGeoJSON,
        appState.layers.showKabupaten && (viewport?.zoom ?? 0) >= 7
      );
      } catch (_err) {
        // Batas administrasi bersifat kontekstual dan tidak memblokir peta.
      }
    } else {
      renderKabupatenLayer(null, false);
    }
  }, 400);
}

window.addEventListener("DOMContentLoaded", () => {
  initMap(appState.userLat, appState.userLon, (lat, lon) => {
    document.querySelectorAll(".chip-btn").forEach((b) => b.classList.remove("active"));
    setActiveUserPoint(lat, lon, "Titik Pilihan Peta", null, false);
  }, scheduleViewportLayers);

  bindTabs();
  bindTopbarAndPresetEvents();
  bindFilterControls(appState, {
    onFilterChange: () => reloadNearestFacilities(),
    onLocalSearchChange: () => refreshDisplayedListAndMarkers(),
    onLayerToggle: () => {
      renderHotspotsLayer(cachedHotspotsGeoJSON, appState.layers.showHotspot);
      const viewport = getMapViewport();
      renderKabupatenLayer(
        cachedKabupatenGeoJSON,
        appState.layers.showKabupaten && (viewport?.zoom ?? 0) >= 7
      );
      if (appState.analysisData) {
        const isAnalisisTab = !document.getElementById("pane-analisis").classList.contains("hidden");
        renderH3CellsLayer(
          appState.analysisData.sel_h3,
          isAnalisisTab && appState.layers.showH3
        );
      }
    },
    onHotspotDaysChange: async () => {
      try {
        const viewport = getMapViewport();
        cachedHotspotsGeoJSON = await fetchHotspotsGeoJSON(
          appState.layers.hotspotDays,
          viewport?.bbox || null
        );
        renderHotspotsLayer(cachedHotspotsGeoJSON, appState.layers.showHotspot);
      } catch (_err) {
        // Ignore transient network error
      }
    },
  });

  reloadNearestFacilities();
  initContextualLayersAndAnalysis();
});
