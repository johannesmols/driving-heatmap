CREATE EXTENSION IF NOT EXISTS postgis;

-- ─────────────────────────────────────────────
-- Vehicles
-- ─────────────────────────────────────────────
CREATE TABLE vehicles (
  id               TEXT PRIMARY KEY,         -- Connected Cars vehicle ID, e.g. "34881"
  make             TEXT,
  model            TEXT,
  year             INT,
  license_plate    TEXT,
  namespace        TEXT,                      -- e.g. 'semler:minvolkswagen'
  first_seen_at    TIMESTAMPTZ,
  last_synced_at   TIMESTAMPTZ                -- updated after every successful sync run
);

-- ─────────────────────────────────────────────
-- Trips
-- ─────────────────────────────────────────────
CREATE TABLE trips (
  id                    TEXT PRIMARY KEY,     -- Connected Cars trip ID (opaque base64 string)
  vehicle_id            TEXT NOT NULL REFERENCES vehicles(id),

  -- Timing
  started_at            TIMESTAMPTZ NOT NULL,
  ended_at              TIMESTAMPTZ,
  duration_min          INT,

  -- Distance
  mileage_km            REAL,                 -- odometer-based
  gps_mileage_km        REAL,                 -- GPS-calculated

  -- Addresses
  start_address         TEXT,
  end_address           TEXT,

  -- Odometer (enables historical charts without joining positions)
  start_odometer_km     REAL,
  end_odometer_km       REAL,

  -- Energy
  fuel_used_l           REAL,
  electricity_used_kwh  REAL,
  idle_time_s           INT,

  -- Driving style events
  accel_high            INT,
  accel_medium          INT,
  accel_low             INT,
  brake_high            INT,
  brake_medium          INT,
  brake_low             INT,
  turn_high             INT,
  turn_medium           INT,

  -- PostGIS geometry
  start_point           GEOMETRY(Point, 4326),
  end_point             GEOMETRY(Point, 4326),
  route                 GEOMETRY(LineString, 4326),  -- materialised from positions at sync time

  -- Metadata
  synced_at             TIMESTAMPTZ DEFAULT NOW(),
  raw_data              JSONB
  -- raw_data stores the complete API response. If a field exists in the API but not yet
  -- in this schema, it can be extracted later without re-syncing:
  -- UPDATE trips SET new_col = (raw_data->>'fieldName')::type
);

-- ─────────────────────────────────────────────
-- Positions (individual GPS track points)
-- ─────────────────────────────────────────────
CREATE TABLE positions (
  trip_id        TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  recorded_at    TIMESTAMPTZ NOT NULL,
  point          GEOMETRY(Point, 4326) NOT NULL,
  speed_kmh      INT,
  direction_deg  INT,
  accuracy_m     INT,     -- 'eph' field from API: estimated horizontal error in metres
  PRIMARY KEY (trip_id, recorded_at)
);

-- ─────────────────────────────────────────────
-- Expansion tables (schema defined now, populated later as features are added)
-- ─────────────────────────────────────────────

CREATE TABLE odometer_readings (
  id           BIGSERIAL PRIMARY KEY,
  vehicle_id   TEXT NOT NULL REFERENCES vehicles(id),
  recorded_at  TIMESTAMPTZ NOT NULL,
  value_km     REAL NOT NULL,
  source       TEXT   -- 'can_bus', 'gps', 'trip_end', 'manual'
);

CREATE TABLE fuel_events (
  id             BIGSERIAL PRIMARY KEY,
  vehicle_id     TEXT NOT NULL REFERENCES vehicles(id),
  occurred_at    TIMESTAMPTZ NOT NULL,
  liters         REAL,
  fuel_level_pct REAL,
  event_type     TEXT   -- 'refuel', 'charge'
);

-- ─────────────────────────────────────────────
-- Indexes
-- ─────────────────────────────────────────────

-- Spatial indexes — make bounding-box queries for the heatmap fast
CREATE INDEX ON trips USING GIST(route);
CREATE INDEX ON trips USING GIST(start_point);
CREATE INDEX ON trips USING GIST(end_point);

-- Time-based indexes for date filtering and stats
CREATE INDEX ON trips(started_at DESC);
CREATE INDEX ON trips(vehicle_id, started_at DESC);

-- Position indexes for trip detail view
CREATE INDEX ON positions USING GIST(point);
CREATE INDEX ON positions(trip_id, recorded_at);

-- Odometer chart queries
CREATE INDEX ON odometer_readings(vehicle_id, recorded_at DESC);
