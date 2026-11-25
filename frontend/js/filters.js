export function bindFilterControls(state, callbacks) {
  const inputCari = document.getElementById("input-cari");
  const selectJenis = document.getElementById("select-jenis");
  const sliderRadius = document.getElementById("slider-radius");
  const nilaiRadius = document.getElementById("nilai-radius");
  const chkOksigen = document.getElementById("chk-oksigen");
  const chkIgd = document.getElementById("chk-igd");
  const chkDokter = document.getElementById("chk-dokter");
  const chkTt = document.getElementById("chk-tt");
  const chkHotspot = document.getElementById("chk-layer-hotspot");
  const chkKabupaten = document.getElementById("chk-layer-kabupaten");
  const chkPresisi = document.getElementById("chk-presisi-tinggi");
  const chkH3 = document.getElementById("chk-layer-h3");
  const selectHotspotHari = document.getElementById("select-hotspot-hari");
  const formFilter = document.getElementById("form-filter");

  formFilter.addEventListener("submit", (ev) => {
    ev.preventDefault();
    callbacks.onFilterChange();
  });

  inputCari.addEventListener("input", () => {
    state.filters.q = inputCari.value.trim();
    callbacks.onLocalSearchChange();
  });

  selectJenis.addEventListener("change", () => {
    state.filters.jenis = selectJenis.value;
    callbacks.onFilterChange();
  });

  sliderRadius.addEventListener("input", () => {
    nilaiRadius.textContent = sliderRadius.value;
  });

  sliderRadius.addEventListener("change", () => {
    state.filters.radiusKm = Number(sliderRadius.value);
    nilaiRadius.textContent = sliderRadius.value;
    callbacks.onFilterChange();
  });

  chkOksigen.addEventListener("change", () => {
    state.filters.oksigen = chkOksigen.checked;
    callbacks.onFilterChange();
  });

  chkIgd.addEventListener("change", () => {
    state.filters.igd24 = chkIgd.checked;
    callbacks.onFilterChange();
  });

  chkDokter.addEventListener("change", () => {
    state.filters.dokter = chkDokter.checked;
    callbacks.onFilterChange();
  });

  chkTt.addEventListener("change", () => {
    state.filters.ttMin = chkTt.checked ? 2 : 0;
    callbacks.onFilterChange();
  });

  chkPresisi.addEventListener("change", () => {
    state.filters.exactCoords = chkPresisi.checked;
    callbacks.onFilterChange();
  });

  chkHotspot.addEventListener("change", () => {
    state.layers.showHotspot = chkHotspot.checked;
    callbacks.onLayerToggle();
  });

  chkKabupaten.addEventListener("change", () => {
    state.layers.showKabupaten = chkKabupaten.checked;
    callbacks.onLayerToggle();
  });

  chkH3.addEventListener("change", () => {
    state.layers.showH3 = chkH3.checked;
    callbacks.onLayerToggle();
  });

  if (selectHotspotHari) {
    selectHotspotHari.addEventListener("change", () => {
      state.layers.hotspotDays = Number(selectHotspotHari.value) || 7;
      if (callbacks.onHotspotDaysChange) {
        callbacks.onHotspotDaysChange();
      }
    });
  }
}

export function syncFilterInputsFromState(state) {
  document.getElementById("input-cari").value = state.filters.q;
  document.getElementById("select-jenis").value = state.filters.jenis;
  document.getElementById("slider-radius").value = String(state.filters.radiusKm);
  document.getElementById("nilai-radius").textContent = String(state.filters.radiusKm);
  document.getElementById("chk-oksigen").checked = state.filters.oksigen;
  document.getElementById("chk-igd").checked = state.filters.igd24;
  document.getElementById("chk-dokter").checked = state.filters.dokter;
  document.getElementById("chk-tt").checked = state.filters.ttMin > 0;
  document.getElementById("chk-presisi-tinggi").checked = state.filters.exactCoords;
}
