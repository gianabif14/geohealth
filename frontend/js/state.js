export const appState = {
  userLat: -2.9760,
  userLon: 104.7520,
  userLabel: "Palembang",
  accuracyM: null,
  prevLat: null,
  prevLon: null,
  lastFixTimeMs: null,

  filters: {
    q: "",
    jenis: "",
    radiusKm: 35,
    oksigen: false,
    igd24: false,
    dokter: false,
    ttMin: 0,
    exactCoords: false,
  },

  layers: {
    showHotspot: true,
    showKabupaten: true,
    showH3: false,
  },

  facilities: [],
  selectedFacilityId: null,
  analysisData: null,
};
