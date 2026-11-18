CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS kabupaten (
  id SERIAL PRIMARY KEY,
  nama TEXT NOT NULL,
  kode TEXT UNIQUE NOT NULL,
  is_pilot BOOLEAN NOT NULL DEFAULT FALSE,
  geom geometry(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kabupaten_geom ON kabupaten USING GIST (geom);

CREATE TABLE IF NOT EXISTS faskes (
  id SERIAL PRIMARY KEY,
  osm_id BIGINT UNIQUE,
  nama TEXT NOT NULL,
  jenis TEXT NOT NULL CHECK (jenis IN ('rumah_sakit', 'puskesmas', 'klinik', 'lainnya')),
  alamat TEXT,
  telepon TEXT,
  kabupaten_id INT REFERENCES kabupaten(id) ON DELETE SET NULL,
  sumber TEXT NOT NULL CHECK (sumber IN ('osm', 'csv', 'sampel')),
  geom geometry(Point, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_faskes_geom ON faskes USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_faskes_geog ON faskes USING GIST ((geom::geography));
CREATE INDEX IF NOT EXISTS idx_faskes_jenis ON faskes (jenis);

CREATE TABLE IF NOT EXISTS faskes_status (
  faskes_id INT PRIMARY KEY REFERENCES faskes(id) ON DELETE CASCADE,
  buka BOOLEAN NOT NULL DEFAULT TRUE,
  igd_24jam BOOLEAN NOT NULL DEFAULT FALSE,
  dokter_jaga BOOLEAN NOT NULL DEFAULT FALSE,
  oksigen BOOLEAN NOT NULL DEFAULT FALSE,
  tempat_tidur_tersedia INT NOT NULL DEFAULT 0,
  tempat_tidur_total INT NOT NULL DEFAULT 0,
  catatan_layanan TEXT,
  sumber TEXT NOT NULL CHECK (sumber IN ('osm', 'manual', 'simulasi')),
  diperbarui_pada TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hotspot (
  id BIGSERIAL PRIMARY KEY,
  waktu_akuisisi TIMESTAMPTZ NOT NULL,
  confidence TEXT NOT NULL,
  frp REAL NOT NULL DEFAULT 0,
  satelit TEXT NOT NULL,
  kabupaten_id INT REFERENCES kabupaten(id) ON DELETE SET NULL,
  sumber TEXT NOT NULL CHECK (sumber IN ('firms', 'sampel')),
  geom geometry(Point, 4326) NOT NULL,
  UNIQUE (waktu_akuisisi, geom)
);
CREATE INDEX IF NOT EXISTS idx_hotspot_geom ON hotspot USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_hotspot_geog ON hotspot USING GIST ((geom::geography));
CREATE INDEX IF NOT EXISTS idx_hotspot_waktu ON hotspot (waktu_akuisisi);
