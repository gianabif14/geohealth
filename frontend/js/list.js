import { escapeHtml } from "./map.js";

const JENIS_LABEL = {
  rumah_sakit: "Rumah Sakit (Lingkaran)",
  puskesmas: "Puskesmas (Persegi)",
  klinik: "Klinik Pratama (Segitiga)",
  lainnya: "Fasilitas Kesehatan",
};

export function renderFacilityList(facilities, selectedId, onSelectFacility, onRouteRequest) {
  const ul = document.getElementById("daftar-faskes");
  ul.innerHTML = "";

  facilities.forEach((f, idx) => {
    const li = document.createElement("li");
    li.className = "facility-card";
    if (idx === 0) li.classList.add("is-nearest-primary");
    if (f.id === selectedId) li.classList.add("is-selected");
    li.dataset.faskesId = String(f.id);

    const distKm = f.jarak_m !== null && f.jarak_m !== undefined ? (f.jarak_m / 1000).toFixed(2) : "-";
    const st = f.status;
    const dtStr = new Date(st.diperbarui_pada).toLocaleString("id-ID", {
      dateStyle: "short",
      timeStyle: "short",
    });

    const rankText = idx === 0
      ? "TERDEKAT #1 (Kandidat Rujukan Utama)"
      : `Urutan jarak #${idx + 1}`;

    const osmRouteUrl = `https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${encodeURIComponent(
      `${f._userLat || -2.976},${f._userLon || 104.752};${f.lat},${f.lon}`
    )}`;

    li.innerHTML = `
      <div class="card-top">
        <div class="card-title-group">
          <span class="card-rank-tag">${escapeHtml(rankText)}</span>
          <h3 class="card-name">${escapeHtml(f.nama)}</h3>
          <span class="card-meta-line">
            ${escapeHtml(JENIS_LABEL[f.jenis] || f.jenis)} &middot; ${escapeHtml(f.kabupaten || "Sumatera Selatan")}
          </span>
          <span class="card-meta-line">${escapeHtml(f.alamat || "Alamat jalan sesuai titik peta")}</span>
        </div>
        <div class="distance-box" aria-label="Jarak dan arah kompas">
          <span class="distance-value">${distKm} km</span>
          <span class="distance-dir">${escapeHtml(f.arah_kompas || "-")} (${f.azimuth_deg ?? 0}&deg;)</span>
        </div>
      </div>

      <div class="service-tags" aria-label="Status ketersediaan layanan">
        <span class="srv-tag ${st.igd_24jam ? "ready" : "unavailable"}">
          IGD 24 Jam: ${st.igd_24jam ? "Aktif" : "Tidak"}
        </span>
        <span class="srv-tag ${st.oksigen ? "ready" : "unavailable"}">
          Oksigen: ${st.oksigen ? "Tersedia" : "Terbatas"}
        </span>
        <span class="srv-tag ${st.dokter_jaga ? "ready" : "unavailable"}">
          Dokter Jaga: ${st.dokter_jaga ? "Siaga" : "Tidak"}
        </span>
        <span class="srv-tag ${st.tempat_tidur_tersedia > 0 ? "ready" : "unavailable"}">
          Tempat Tidur: ${st.tempat_tidur_tersedia} / ${st.tempat_tidur_total}
        </span>
      </div>

      <div class="source-stamp">
        <span>Status layanan: <strong>Data ${escapeHtml(st.sumber)}</strong> (${escapeHtml(dtStr)})</span>
        <span>Lokasi: <strong>${escapeHtml(f.sumber.toUpperCase())}</strong></span>
      </div>
    `;

    const actionsDiv = document.createElement("div");
    actionsDiv.className = "card-actions";

    const btnFocus = document.createElement("button");
    btnFocus.type = "button";
    btnFocus.className = "btn btn-outline btn-small";
    btnFocus.textContent = "Lihat di peta";
    btnFocus.addEventListener("click", () => onSelectFacility(f.id, true));
    actionsDiv.appendChild(btnFocus);

    const btnRoute = document.createElement("button");
    btnRoute.type = "button";
    btnRoute.className = "btn btn-primary btn-small";
    btnRoute.textContent = "Buka rute";
    btnRoute.addEventListener("click", () => onRouteRequest(f));
    actionsDiv.appendChild(btnRoute);

    if (f.telepon) {
      const telClean = f.telepon.replace(/[^0-9+]/g, "");
      const linkTel = document.createElement("a");
      linkTel.href = `tel:${telClean}`;
      linkTel.className = "btn btn-outline btn-small";
      linkTel.textContent = `Telepon ${f.telepon}`;
      actionsDiv.appendChild(linkTel);
    }

    const linkExt = document.createElement("a");
    linkExt.href = osmRouteUrl;
    linkExt.target = "_blank";
    linkExt.rel = "noopener noreferrer";
    linkExt.className = "btn btn-outline btn-small";
    linkExt.textContent = "Navigasi OSM";
    actionsDiv.appendChild(linkExt);

    li.appendChild(actionsDiv);
    ul.appendChild(li);
  });
}

export function renderAnalysisTables(analysisData, onFocusH3Cell) {
  const tbody = document.getElementById("tbody-ranking-kab");
  const h3List = document.getElementById("daftar-sel-h3");
  const metP = document.getElementById("teks-metodologi-h3");

  if (analysisData.metodologi) {
    metP.textContent = `${analysisData.metodologi} ${analysisData.catatan_sumber}`;
  }

  tbody.innerHTML = "";
  (analysisData.kabupaten_ranking || []).forEach((k) => {
    const tr = document.createElement("tr");
    const prioClass = `prio-${k.prioritas_posko}`;
    tr.innerHTML = `
      <td>
        <strong>${escapeHtml(k.nama)}</strong>
        ${k.is_pilot ? '<br><small style="color:#0F5C59;font-weight:700;">Wilayah Pilot</small>' : ""}
      </td>
      <td><strong>${k.skor_akses_terbatas}</strong> / 100</td>
      <td>${k.rerata_jarak_faskes_siap_km} km<br><small>${k.jumlah_faskes_siap_igd_oksigen}/${k.jumlah_faskes} faskes siap</small></td>
      <td>${k.jumlah_hotspot_7hari} titik</td>
      <td><span class="prio-label ${prioClass}">${escapeHtml(k.prioritas_posko.toUpperCase())}</span></td>
    `;
    tbody.appendChild(tr);
  });

  h3List.innerHTML = "";
  (analysisData.sel_h3 || []).slice(0, 12).forEach((c) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "h3-item-btn";
    const prioClass = `prio-${c.kategori}`;
    btn.innerHTML = `
      <div>
        <strong>${escapeHtml(c.kabupaten || "Sumatera Selatan")}</strong> (H3: <code>${escapeHtml(c.h3_index)}</code>)<br>
        <span style="font-size:0.82rem;color:#4A524D;">
          Hotspot: ${c.n_hotspot} titik &middot; Jarak faskes siap: ${c.jarak_faskes_siap_km} km (${escapeHtml(c.faskes_terdekat_nama || "-")})
        </span>
      </div>
      <span class="prio-label ${prioClass}">Skor ${c.skor}</span>
    `;
    btn.addEventListener("click", () => onFocusH3Cell(c));
    li.appendChild(btn);
    h3List.appendChild(li);
  });
}
