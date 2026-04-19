# Driving Heatmap — Implementation Plan

## Overview

Build a personal driving heatmap web app that fetches GPS trip data from the Connected Cars
GraphQL API, stores it in PostgreSQL with PostGIS, and renders a Strava-style heatmap
(overlapping polylines with additive brightness). The app runs in Docker on a TrueNAS home
server. It is single-user with no authentication UI.

The plan is split into four phases that build directly on each other. Each phase produces
something independently useful and testable before the next begins.

---

## What we know about the Connected Cars API

This section documents everything discovered through direct testing. Any agent implementing
this should treat it as ground truth — do not assume standard GraphQL conventions hold.
This API has several quirks that will cause silent failures if not respected.

### Endpoints

| Purpose | URL |
|---|---|
| Auth (login) | `https://auth-api.connectedcars.io/auth/login/email/password` |
| GraphQL API | `https://api.connectedcars.io/graphql` |
| GraphiQL explorer | `https://api.connectedcars.io/graphql/graphiql/` |

### Authentication

The login endpoint is a plain HTTP POST — not GraphQL. It returns a short-lived JWT.

```http
POST https://auth-api.connectedcars.io/auth/login/email/password
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password"
}
```

Response body:
```json
{ "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." }
```

Every subsequent GraphQL request requires two headers:

```
Authorization: Bearer <jwt_token>
X-Organization-Namespace: semler:minvolkswagen
```

The namespace `semler:minvolkswagen` is specific to the Danish Min Volkswagen app.
Other Connected Cars apps (MyŠKODA, etc.) use different namespaces.

Tokens expire after approximately one hour. The sync service must re-authenticate
at the start of every sync run — do not attempt to cache or reuse tokens across runs.

### Vehicle discovery

The `viewer.vehicles` field returns an array of wrapper objects. There is an extra
`vehicle` level inside each item — it is not a flat array:

```graphql
query {
  viewer {
    vehicles {
      vehicle {          # <-- this wrapper always exists
        id               # e.g. "34881" — use this string ID everywhere
        make
        model
        year
        licensePlate
      }
    }
  }
}
```

### Fetching trips

Trips are accessed via `vehicle.trips(last: N)`. The pagination model is cursor-based
and uses `items` (not the Relay-standard `edges`/`node`).

**Critical pagination quirks — read carefully:**

- `trips(first: N)` without a cursor starts from approximately 2018 regardless of when
  the car was bought. It returns pages of empty `items` for a long time before reaching
  real data. Never use `first:` for the initial load — use `last:` to start from the
  most recent trips and page backwards.
- To page further back in time: take `pageInfo.endCursor` from the current response
  and pass it as `before: $cursor` in the next request, still using `last: N`.
- `hasNextPage` refers to whether there are more pages in the direction you are
  paginating. When paginating backwards with `last:`, this means "are there older trips?"

**Full query for incremental sync:**

```graphql
query GetTrips($before: Cursor) {
  viewer {
    vehicles {
      vehicle {
        trips(last: 50, before: $before) {
          items {
            id
            startTime
            endTime
            duration
            mileage
            gpsMileage
            startLatitude
            startLongitude
            endLatitude
            endLongitude
            startAddressString
            endAddressString
            startOdometer
            endOdometer
            fuelUsed
            electricityUsed
            idleTime
            accelerationHigh
            accelerationMedium
            accelerationLow
            brakeHigh
            brakeMedium
            brakeLow
            turnHigh
            turnMedium
            positions {
              latitude
              longitude
              time
              speed
              direction
              eph
            }
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
  }
}
```

**Date-range query via `vehicleActivityFeed`:**

Useful for targeted backfills. Note: `first` and `last` here are `Date` scalars
(ISO strings), completely unlike the `Int` paginators on `trips`. They are date
filters, not page-size arguments.

```graphql
query {
  vehicleActivityFeed(
    vehicleId: "34881"
    types: [TRIP]
    first: "2023-01-01T00:00:00.000Z"
    last: "2023-01-31T23:59:59.000Z"
    limit: 50
  ) {
    ... on VehicleTrip {
      id
      startTime
      mileage
    }
  }
}
```

**Fetching a single trip by ID:**

```graphql
query {
  vehicleTrip(id: "MzQ4ODEtODg2NjIyODAw") {
    id
    startTime
    mileage
    positions {
      latitude
      longitude
      time
      speed
      direction
      eph
    }
  }
}
```

### The `positions` field

Confirmed working on trips dating back to at least January 2023 (over 3 years). Each
position in the array has the following fields:

| Field | API name | Type | Notes |
|---|---|---|---|
| Latitude | `latitude` | Float | WGS84 |
| Longitude | `longitude` | Float | WGS84 |
| Timestamp | `time` | String (ISO 8601) | UTC |
| Speed | `speed` | Int | km/h |
| Heading | `direction` | Int | Degrees 0–360 |
| GPS accuracy | `eph` | Int | Estimated horizontal error in metres |

Point density: roughly one point every 5–6 seconds at motorway speed, more frequent in
urban/stop-start conditions. A 237 km motorway trip produces ~500–600 points. Full history
of 80,000 km across ~2,000 trips is estimated at 2–3 million points total.

Requires `can_see_position` or `can_see_position_updated` permission. As the vehicle
owner this is granted automatically.

### What does NOT exist in this API

- There is no `vehicle(id: ...)` root field. Vehicles are only reachable via
  `viewer.vehicles`.
- `Vehicle.trip` (singular) does not accept an `id` argument. Use root-level
  `vehicleTrip(id:)` to fetch a single trip by ID.
- `TripsResult` only has `items` and `pageInfo` — there is no `totalCount`.
- Rate limits are not documented. Implement exponential backoff on HTTP 429 responses.

---

## Technology stack

### Why Python for the sync service

The sync service needs to make HTTP requests, write to PostgreSQL, and run on a schedule.
Python is the most ergonomic choice for all three:

- **GraphQL is plain HTTP.** No dedicated GraphQL client library is needed. GraphQL
  requests are just `POST /graphql` with a JSON body. A 10-line helper using `httpx`
  covers everything needed.
- **`psycopg[binary]` (psycopg3)** is the modern, async-capable PostgreSQL driver with
  native support for upserts, typed parameters, and context managers.
- **APScheduler** runs the sync on a schedule inside the same long-running process.
  No separate cron daemon, no shell scripts — just Python. The sync function is called
  once on startup (for the initial backfill) and then every N hours via the scheduler.
- The sync logic is sequential, I/O-bound ETL work that Python was made for. The code
  reads almost identically to the algorithm description in plain English.

### Why FastAPI for the API server

- Async-first: uses `asyncpg` for non-blocking Postgres queries
- PostGIS returns GeoJSON-formatted strings directly from SQL; FastAPI passes them
  through with zero transformation
- Automatic OpenAPI docs at `/docs` with no extra work — useful for debugging
- Thin and fast for I/O-bound database query workloads

### Why Svelte 5 for the frontend

- `svelte-maplibre-gl` is a Svelte 5-native MapLibre GL JS wrapper with a built-in
  `<DeckGLOverlay>` component — exactly the integration needed here
- Compiles to vanilla JS with ~1.6 KB runtime; no virtual DOM
- Runes (`$state`, `$derived`, `$effect`) resemble C# computed properties
- Vite is the default bundler; Bun handles package management
- Tailwind CSS v4 for styling

### Full stack summary

| Layer | Technology |
|---|---|
| Database | PostgreSQL 16 + PostGIS 3.4 |
| Sync service | Python 3.12, httpx, psycopg3, APScheduler, tenacity |
| API server | Python 3.12, FastAPI, asyncpg |
| Frontend | Svelte 5, MapLibre GL JS, deck.gl, Tailwind CSS v4, Vite, Bun |
| DB admin | pgAdmin 4 (optional, included in Compose) |
| Container runtime | Docker Compose on TrueNAS SCALE |

---

## Database schema

Designed to serve all current needs and leave room for expansion without structural
changes. Place this file at `db/init/001_schema.sql` — PostgreSQL runs it automatically
on first container start via `docker-entrypoint-initdb.d`.

```sql
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
```

---

## Phase 1 — Sync service

**Goal:** A Python service that authenticates with the Connected Cars API, pages through
all trips, and writes everything to PostgreSQL. No web server, no frontend — just the
data pipeline. This is the most time-sensitive piece; start here.

### Project structure

```
sync/
├── Dockerfile
├── requirements.txt
└── main.py
```

### requirements.txt

```
httpx==0.27.*
psycopg[binary]==3.2.*
apscheduler==3.10.*
tenacity==9.*
```

### main.py

```python
import os
import logging
from datetime import datetime, timezone
import httpx
import psycopg
from psycopg.types.json import Jsonb
from apscheduler.schedulers.blocking import BlockingScheduler
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

log = logging.getLogger(__name__)

CC_AUTH_URL    = "https://auth-api.connectedcars.io/auth/login/email/password"
CC_GRAPHQL_URL = "https://api.connectedcars.io/graphql"


# ─────────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────────────────────────────────────

def authenticate(email: str, password: str) -> str:
    """Returns a JWT token. Call at the start of every sync run — tokens last ~1 hour."""
    r = httpx.post(CC_AUTH_URL, json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def graphql(token: str, namespace: str, query: str, variables: dict = None) -> dict:
    """Execute a GraphQL query. Raises on HTTP error or GraphQL-level errors."""
    r = httpx.post(
        CC_GRAPHQL_URL,
        json={"query": query, "variables": variables or {}},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Organization-Namespace": namespace,
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    if "errors" in body:
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    return body["data"]


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception(
        lambda e: isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429
    ),
    reraise=True,
)
def graphql_with_retry(token, namespace, query, variables=None):
    return graphql(token, namespace, query, variables)


# ─────────────────────────────────────────────────────────────────────────────
# GraphQL queries
# ─────────────────────────────────────────────────────────────────────────────

GET_VEHICLES_QUERY = """
query {
  viewer {
    vehicles {
      vehicle { id make model year licensePlate }
    }
  }
}
"""

GET_TRIPS_QUERY = """
query GetTrips($before: Cursor) {
  viewer {
    vehicles {
      vehicle {
        trips(last: 50, before: $before) {
          items {
            id startTime endTime duration
            mileage gpsMileage
            startLatitude startLongitude endLatitude endLongitude
            startAddressString endAddressString
            startOdometer endOdometer
            fuelUsed electricityUsed idleTime
            accelerationHigh accelerationMedium accelerationLow
            brakeHigh brakeMedium brakeLow
            turnHigh turnMedium
            positions { latitude longitude time speed direction eph }
          }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
  }
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Geometry helpers
# ─────────────────────────────────────────────────────────────────────────────

def build_linestring(positions: list[dict]) -> str | None:
    if len(positions) < 2:
        return None
    coords = ", ".join(f"{p['longitude']} {p['latitude']}" for p in positions)
    return f"LINESTRING({coords})"


# ─────────────────────────────────────────────────────────────────────────────
# Sync logic
# ─────────────────────────────────────────────────────────────────────────────

def upsert_vehicle(conn, vehicle: dict, namespace: str):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO vehicles (id, make, model, year, license_plate, namespace, first_seen_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE SET
                make           = EXCLUDED.make,
                model          = EXCLUDED.model,
                year           = EXCLUDED.year,
                license_plate  = EXCLUDED.license_plate,
                last_synced_at = NOW()
        """, (vehicle["id"], vehicle["make"], vehicle["model"],
              vehicle["year"], vehicle.get("licensePlate"), namespace))


def get_last_synced(conn, vehicle_id: str) -> datetime | None:
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(started_at) FROM trips WHERE vehicle_id = %s", (vehicle_id,))
        row = cur.fetchone()
        return row[0]  # None if no trips yet


def sync_vehicle(conn, token: str, namespace: str, vehicle: dict):
    upsert_vehicle(conn, vehicle, namespace)
    last_synced = get_last_synced(conn, vehicle["id"])

    log.info(
        f"Syncing {vehicle['make']} {vehicle['model']} (id={vehicle['id']}), "
        f"last synced: {last_synced or 'never — full backfill'}"
    )

    cursor = None
    trips_written = 0
    positions_written = 0

    while True:
        data = graphql_with_retry(
            token, namespace, GET_TRIPS_QUERY,
            {"before": cursor} if cursor else {}
        )
        vehicles_data = data["viewer"]["vehicles"]
        if not vehicles_data:
            break

        page      = vehicles_data[0]["vehicle"]["trips"]
        items     = page["items"]
        page_info = page["pageInfo"]

        if not items:
            break

        with conn.cursor() as cur:
            for trip in items:
                trip_start = datetime.fromisoformat(trip["startTime"].replace("Z", "+00:00"))

                # On incremental runs, stop when we reach trips already in the database
                if last_synced and trip_start <= last_synced:
                    log.info(f"Reached already-synced trip at {trip_start}, stopping.")
                    conn.commit()
                    return

                positions = trip.get("positions") or []
                linestring = build_linestring(positions)

                cur.execute("""
                    INSERT INTO trips (
                        id, vehicle_id, started_at, ended_at, duration_min,
                        mileage_km, gps_mileage_km,
                        start_address, end_address,
                        start_odometer_km, end_odometer_km,
                        fuel_used_l, electricity_used_kwh, idle_time_s,
                        accel_high, accel_medium, accel_low,
                        brake_high, brake_medium, brake_low,
                        turn_high, turn_medium,
                        start_point, end_point, route,
                        raw_data
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                        ST_GeomFromText(%s, 4326),
                        %s
                    )
                    ON CONFLICT (id) DO NOTHING
                """, (
                    trip["id"], vehicle["id"],
                    trip["startTime"], trip.get("endTime"), trip.get("duration"),
                    trip.get("mileage"), trip.get("gpsMileage"),
                    trip.get("startAddressString"), trip.get("endAddressString"),
                    trip.get("startOdometer"), trip.get("endOdometer"),
                    trip.get("fuelUsed"), trip.get("electricityUsed"), trip.get("idleTime"),
                    trip.get("accelerationHigh"), trip.get("accelerationMedium"),
                    trip.get("accelerationLow"),
                    trip.get("brakeHigh"), trip.get("brakeMedium"), trip.get("brakeLow"),
                    trip.get("turnHigh"), trip.get("turnMedium"),
                    trip.get("startLongitude"), trip.get("startLatitude"),
                    trip.get("endLongitude"),  trip.get("endLatitude"),
                    linestring,
                    Jsonb(trip),
                ))
                trips_written += 1

                if positions:
                    cur.executemany("""
                        INSERT INTO positions
                            (trip_id, recorded_at, point, speed_kmh, direction_deg, accuracy_m)
                        VALUES (
                            %s, %s,
                            ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                            %s, %s, %s
                        )
                        ON CONFLICT (trip_id, recorded_at) DO NOTHING
                    """, [
                        (trip["id"], p["time"],
                         p["longitude"], p["latitude"],
                         p.get("speed"), p.get("direction"), p.get("eph"))
                        for p in positions
                    ])
                    positions_written += len(positions)

        conn.commit()
        log.info(f"  {trips_written} trips, {positions_written} positions synced so far.")

        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

    log.info(f"Vehicle sync done: {trips_written} trips, {positions_written} positions.")


def run_sync():
    """Single sync run. Called on startup and by APScheduler every N hours."""
    log.info("─── Sync run starting ───")
    started_at = datetime.now(timezone.utc)

    email     = os.environ["CC_EMAIL"]
    password  = os.environ["CC_PASSWORD"]
    namespace = os.environ.get("CC_NAMESPACE", "semler:minvolkswagen")
    db_url    = os.environ["DATABASE_URL"]

    try:
        token = authenticate(email, password)
        log.info("Authenticated.")

        data     = graphql(token, namespace, GET_VEHICLES_QUERY)
        vehicles = [v["vehicle"] for v in data["viewer"]["vehicles"]]
        log.info(f"Found {len(vehicles)} vehicle(s).")

        with psycopg.connect(db_url) as conn:
            for vehicle in vehicles:
                sync_vehicle(conn, token, namespace, vehicle)

        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        log.info(f"─── Sync run complete in {elapsed:.1f}s ───")

    except Exception:
        log.exception("Sync run failed.")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    interval_hours = int(os.environ.get("SYNC_INTERVAL_HOURS", "6"))

    # Run immediately on startup (catches up any missed data or does first backfill)
    run_sync()

    # Then run on a schedule. max_instances=1 prevents overlap if a run takes longer
    # than the interval (relevant during the initial full backfill).
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_sync, "interval",
        hours=interval_hours,
        id="cc_sync",
        max_instances=1,
    )
    log.info(f"Scheduler started — will sync every {interval_hours} hours.")
    scheduler.start()
```

### Sync Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["python", "main.py"]
```

### Environment variables

```
CC_EMAIL                  Connected Cars login email
CC_PASSWORD               Connected Cars login password
CC_NAMESPACE              Default: semler:minvolkswagen
DATABASE_URL              e.g. postgresql://heatmap:password@db/heatmap
SYNC_INTERVAL_HOURS       Default: 6
```

### Acceptance criteria for Phase 1

- Service starts, authenticates, and begins syncing without errors
- PostgreSQL contains rows in `vehicles`, `trips`, and `positions` after first run
- `trips.route` is a non-null PostGIS LineString for trips that have positions
- Re-running the service does not duplicate any rows
- A second run after new trips exist adds only the new trips
- Logs clearly show page count, trip count, position count, and elapsed time

---

## Phase 2 — API server

**Goal:** A FastAPI service that queries PostgreSQL and serves JSON/GeoJSON to the
frontend. The frontend never touches the database directly.

### Project structure

```
api/
├── Dockerfile
├── requirements.txt
└── main.py
```

### requirements.txt

```
fastapi==0.115.*
uvicorn[standard]==0.30.*
asyncpg==0.29.*
```

### main.py

```python
import os
from contextlib import asynccontextmanager
from typing import Optional
import asyncpg
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

pool: asyncpg.Pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=2, max_size=10)
    yield
    await pool.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/api/stats")
async def get_stats():
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                COUNT(*)                            AS trip_count,
                ROUND(SUM(mileage_km)::numeric, 1)  AS total_km,
                ROUND(SUM(COALESCE(fuel_used_l, 0))::numeric, 1) AS total_fuel_l,
                MIN(started_at)                     AS oldest_trip,
                MAX(started_at)                     AS newest_trip,
                (SELECT COUNT(*) FROM positions)    AS position_count
            FROM trips
        """)
    return dict(row)


@app.get("/api/trips")
async def list_trips(
    from_:  Optional[str] = Query(None, alias="from"),
    to:     Optional[str] = Query(None),
    limit:  int           = Query(50, le=500),
    offset: int           = Query(0),
):
    conditions, params = ["1=1"], []

    if from_:
        params.append(from_)
        conditions.append(f"started_at >= ${len(params)}")
    if to:
        params.append(to)
        conditions.append(f"started_at <= ${len(params)}")

    params.extend([limit, offset])
    where = " AND ".join(conditions)

    async with pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT id, started_at, ended_at, duration_min,
                   mileage_km, gps_mileage_km,
                   start_address, end_address,
                   start_odometer_km, end_odometer_km,
                   fuel_used_l, electricity_used_kwh, idle_time_s,
                   accel_high, brake_high, turn_high
            FROM trips
            WHERE {where}
            ORDER BY started_at DESC
            LIMIT ${len(params)-1} OFFSET ${len(params)}
        """, *params)
    return [dict(r) for r in rows]


@app.get("/api/trips/{trip_id}")
async def get_trip(trip_id: str):
    async with pool.acquire() as conn:
        trip = await conn.fetchrow("""
            SELECT
                id, started_at, ended_at, duration_min,
                mileage_km, gps_mileage_km,
                start_address, end_address,
                start_odometer_km, end_odometer_km,
                fuel_used_l, electricity_used_kwh, idle_time_s,
                accel_high, accel_medium, accel_low,
                brake_high, brake_medium, brake_low,
                turn_high, turn_medium,
                ST_AsGeoJSON(start_point)::json AS start_point,
                ST_AsGeoJSON(end_point)::json   AS end_point,
                ST_AsGeoJSON(route)::json        AS route
            FROM trips WHERE id = $1
        """, trip_id)

        if not trip:
            return JSONResponse({"error": "Trip not found"}, status_code=404)

        positions = await conn.fetch("""
            SELECT recorded_at, speed_kmh, direction_deg, accuracy_m,
                   ST_AsGeoJSON(point)::json AS point
            FROM positions
            WHERE trip_id = $1
            ORDER BY recorded_at
        """, trip_id)

    result = dict(trip)
    result["positions"] = [dict(p) for p in positions]
    return result


@app.get("/api/tracks")
async def get_tracks(
    from_:    Optional[str]   = Query(None, alias="from"),
    to:       Optional[str]   = Query(None),
    bbox:     Optional[str]   = Query(None, description="minLng,minLat,maxLng,maxLat"),
    simplify: Optional[float] = Query(None, description="Simplification tolerance in degrees. "
                                      "0.001 = zoom ~10, 0.01 = zoom ~8, omit for full detail"),
):
    """
    Returns all trip routes as a GeoJSON FeatureCollection.
    This is the primary endpoint consumed by the heatmap frontend.
    PostGIS does all geometry work server-side; the frontend receives ready-to-render GeoJSON.
    """
    conditions, params = ["route IS NOT NULL"], []

    if from_:
        params.append(from_)
        conditions.append(f"started_at >= ${len(params)}")
    if to:
        params.append(to)
        conditions.append(f"started_at <= ${len(params)}")
    if bbox:
        min_lng, min_lat, max_lng, max_lat = map(float, bbox.split(","))
        params.extend([min_lng, min_lat, max_lng, max_lat])
        n = len(params)
        conditions.append(
            f"ST_Intersects(route, "
            f"ST_MakeEnvelope(${n-3}, ${n-2}, ${n-1}, ${n}, 4326))"
        )

    geom = (f"ST_SimplifyPreserveTopology(route, {float(simplify)})"
            if simplify else "route")
    where = " AND ".join(conditions)

    async with pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT id, started_at, mileage_km,
                   ST_AsGeoJSON({geom})::json AS geometry
            FROM trips
            WHERE {where}
            ORDER BY started_at
        """, *params)

    features = [
        {
            "type": "Feature",
            "id": row["id"],
            "geometry": row["geometry"],
            "properties": {
                "started_at": row["started_at"].isoformat(),
                "mileage_km": row["mileage_km"],
            },
        }
        for row in rows
        if row["geometry"] is not None
    ]

    return {"type": "FeatureCollection", "features": features}
```

### API Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Acceptance criteria for Phase 2

- `GET /api/stats` returns non-zero counts after Phase 1 has run
- `GET /api/tracks` returns valid GeoJSON with `LineString` geometries
- `GET /api/tracks?bbox=8,54,13,58` returns only routes intersecting Jutland
- `GET /api/tracks?simplify=0.001` returns noticeably fewer coordinates per route
- `GET /api/trips/{id}` returns positions in chronological order
- Auto-generated docs accessible at `http://localhost:8000/docs`

---

## Phase 3 — Heatmap frontend

**Goal:** A Svelte 5 single-page app that fetches route GeoJSON from the API and renders
it as a Strava-style heatmap.

### How the Strava heatmap effect works

The effect is thousands of semi-transparent polylines on a dark background with
**additive blending** — each line adds its colour to the canvas rather than compositing.
Where routes overlap, brightness accumulates. Standard alpha blending makes every road
look equally bright no matter how many times it has been driven; additive blending makes
heavily-driven roads glow.

The key line in deck.gl:

```js
parameters: {
  depthWriteEnabled: false,
  blendColorSrcFactor: 'src-alpha',
  blendColorDstFactor: 'one',       // additive, not 'one-minus-src-alpha'
  blendColorOperation: 'add',
}
```

### Map provider

**OpenFreeMap** — free, no API key, no registration, no request limits:
```
https://tiles.openfreemap.org/styles/liberty
```

### Getting started

```bash
bun create svelte@latest frontend
cd frontend
bun add maplibre-gl @deck.gl/core @deck.gl/layers @deck.gl/mapbox svelte-maplibre-gl
bun add -d @tailwindcss/vite tailwindcss
```

### Core heatmap component

```svelte
<!-- src/lib/Heatmap.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import maplibregl from 'maplibre-gl';
  import { PathLayer } from '@deck.gl/layers';
  import { MapboxOverlay } from '@deck.gl/mapbox';
  import 'maplibre-gl/dist/maplibre-gl.css';

  let { from = $bindable(), to = $bindable() } = $props();

  let mapContainer: HTMLDivElement;
  let overlay: MapboxOverlay;
  let map: maplibregl.Map;

  async function loadTracks() {
    const params = new URLSearchParams({ simplify: '0.0005' });
    if (from) params.set('from', from);
    if (to)   params.set('to', to);

    const res   = await fetch(`/api/tracks?${params}`);
    const fc    = await res.json();
    const paths = fc.features
      .filter((f: any) => f.geometry?.coordinates?.length >= 2)
      .map((f: any) => ({ path: f.geometry.coordinates }));

    overlay.setProps({
      layers: [
        new PathLayer({
          id: 'heatmap',
          data: paths,
          getPath: (d: any) => d.path,
          getColor: [255, 80, 20, 12],   // low alpha = more glow contrast between roads
          getWidth: 2,
          widthMinPixels: 1.5,
          parameters: {
            depthWriteEnabled: false,
            blendColorSrcFactor: 'src-alpha',
            blendColorDstFactor: 'one',
            blendColorOperation: 'add',
          },
        }),
      ],
    });
  }

  onMount(() => {
    map = new maplibregl.Map({
      container: mapContainer,
      style: 'https://tiles.openfreemap.org/styles/liberty',
      center: [10.5, 56.0],
      zoom: 7,
    });

    overlay = new MapboxOverlay({ layers: [] });
    map.addControl(overlay);
    map.on('load', loadTracks);

    $effect(() => {
      // Re-fetch when date filters change
      void from; void to;
      if (map.loaded()) loadTracks();
    });

    return () => map.remove();
  });
</script>

<div bind:this={mapContainer} class="w-full h-full" />
```

### Data loading

The `/api/tracks` endpoint returns PostGIS-simplified GeoJSON. Full history (~2,000 trips)
at `simplify=0.0005` is roughly 5–10 MB — loads in under a second on a local network.
When zoomed into a city, pass the current map viewport as `bbox` to get full-resolution
local tracks: `?bbox=12.4,55.6,12.7,55.8&simplify=0`.

### Minimal UI (Phase 3)

- Full-screen dark map
- Year selector or from/to date pickers → triggers re-fetch
- Stats bar: total trips, total km, date range
- Loading indicator during fetch

### Acceptance criteria for Phase 3

- Map loads and displays the dark base map
- GPS tracks are visible as glowing lines
- Heavily-driven roads glow significantly brighter than rarely-driven roads
- Date filter updates the display without a full page reload
- Works in Chrome, Firefox, and Safari on desktop

---

## Phase 4 — Docker Compose and TrueNAS deployment

**Goal:** Package all services into a Docker Compose stack that runs permanently on
TrueNAS SCALE, with automatic data sync and persistent ZFS storage.

### Repository structure

```
project/
├── docker-compose.yml
├── .env                           # credentials — never commit this
├── db/
│   └── init/
│       └── 001_schema.sql
├── sync/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    └── src/
```

### docker-compose.yml

```yaml
services:

  db:
    image: postgis/postgis:16-3.4-alpine
    environment:
      POSTGRES_DB: heatmap
      POSTGRES_USER: heatmap
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - db_data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d   # schema runs on first start only
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U heatmap -d heatmap"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  sync:
    build: ./sync
    environment:
      DATABASE_URL: postgresql://heatmap:${DB_PASSWORD}@db/heatmap
      CC_EMAIL: ${CC_EMAIL}
      CC_PASSWORD: ${CC_PASSWORD}
      CC_NAMESPACE: semler:minvolkswagen
      SYNC_INTERVAL_HOURS: "6"
    depends_on:
      db:
        condition: service_healthy   # waits for Postgres to be genuinely ready
    restart: unless-stopped

  api:
    build: ./api
    environment:
      DATABASE_URL: postgresql://heatmap:${DB_PASSWORD}@db/heatmap
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - api
    restart: unless-stopped

  pgadmin:
    image: dpage/pgadmin4:latest
    ports:
      - "5050:80"
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@local.dev
      PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD}
    volumes:
      - pgadmin_data:/var/lib/pgadmin
    restart: unless-stopped

volumes:
  db_data:
  pgadmin_data:
```

The `condition: service_healthy` on `depends_on` blocks is important. Without it, the
sync and API containers start before PostgreSQL is ready to accept connections, fail
immediately, and restart in a loop until the database catches up.

### .env

```bash
DB_PASSWORD=choose_a_strong_password
CC_EMAIL=your@email.com
CC_PASSWORD=your_connected_cars_password
PGADMIN_PASSWORD=choose_a_pgadmin_password
```

Never commit this file to version control.

### Frontend Dockerfile

```dockerfile
FROM oven/bun:1-alpine AS builder
WORKDIR /app
COPY package.json bun.lockb ./
RUN bun install --frozen-lockfile
COPY . .
RUN bun run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

```nginx
# nginx.conf — proxies /api/* to the api container
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://api:8000;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

The Nginx proxy means the frontend uses relative `/api/` paths and never needs to know
the API container's address. It also eliminates CORS issues in production.

### TrueNAS SCALE deployment

```bash
# On the TrueNAS shell:
mkdir -p /mnt/pool/apps/heatmap
cd /mnt/pool/apps/heatmap
# Copy all project files here, then:
docker compose up -d

# Monitor the initial backfill:
docker compose logs -f sync

# Check API is up:
curl http://localhost:8000/api/stats
```

ZFS automatically snapshots `db_data` as part of the pool schedule, giving versioned
database backups at no extra cost.

**Service URLs:**
```
http://<truenas-ip>:3000    Heatmap frontend
http://<truenas-ip>:5050    pgAdmin database browser
```

### Acceptance criteria for Phase 4

- `docker compose up -d` starts all five services without errors
- Heatmap is accessible and shows trip data
- Sync logs show a successful run on startup and every 6 hours thereafter
- pgAdmin connects and shows populated `trips` and `positions` tables
- All services restart cleanly after a TrueNAS reboot

---

## Appendix A: GraphQL quick reference

### Login (REST, not GraphQL)

```
POST https://auth-api.connectedcars.io/auth/login/email/password
Content-Type: application/json
Body: { "email": "...", "password": "..." }
→ { "token": "eyJ..." }
```

### Required headers for all GraphQL requests

```
Content-Type: application/json
Authorization: Bearer <token>
X-Organization-Namespace: semler:minvolkswagen
```

### Known quirks

| Quirk | Detail |
|---|---|
| `trips(first: N)` without cursor | Starts from ~2018, returns empty items. Always use `last:` |
| Paging backwards | `trips(last: 50, before: $endCursor)` — never use `after:` going backwards |
| `vehicleActivityFeed` `first`/`last` | These are Date scalars (ISO strings), not integers |
| `Vehicle.trip(id:)` | Does not exist. Use root-level `vehicleTrip(id:)` |
| `vehicles` response shape | Items are `{ vehicle: { ... } }`, not flat objects |
| Token lifetime | ~1 hour. Re-authenticate at the start of every sync run |
| Rate limits | Undocumented. Retry with exponential backoff on HTTP 429 |
| `positions` availability | Confirmed available back to at least January 2023 (3+ years) |

---

## Appendix B: Useful PostGIS queries

Once data is in PostgreSQL, these queries are useful for exploration, debugging, and
building additional features.

```sql
-- Total trips and km by year
SELECT
    EXTRACT(YEAR FROM started_at) AS year,
    COUNT(*) AS trips,
    ROUND(SUM(mileage_km)::numeric, 0) AS total_km
FROM trips
GROUP BY year ORDER BY year;

-- All trips that passed within 5 km of Copenhagen city centre
SELECT id, started_at, start_address, end_address, mileage_km
FROM trips
WHERE ST_DWithin(
    route::geography,
    ST_MakePoint(12.5683, 55.6761)::geography,
    5000
)
ORDER BY started_at DESC;

-- Historical odometer development (for a chart)
SELECT
    DATE_TRUNC('month', started_at) AS month,
    MAX(end_odometer_km)             AS odometer_km
FROM trips
WHERE end_odometer_km IS NOT NULL
GROUP BY month ORDER BY month;

-- Trips with the most hard braking events
SELECT id, started_at, start_address, end_address, brake_high
FROM trips
WHERE brake_high > 0
ORDER BY brake_high DESC LIMIT 20;

-- Bounding box of all driving (useful for setting initial map view)
SELECT ST_AsText(ST_Extent(route)) AS extent FROM trips;

-- Extract a field not yet in the relational schema from raw_data JSONB
-- (demonstrates forward-compatibility of storing the full API response)
SELECT id, started_at, (raw_data->>'co2Emissions')::real AS co2_g_per_km
FROM trips
WHERE raw_data ? 'co2Emissions'
ORDER BY started_at DESC;
```
