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

def authenticate(email: str, password: str, namespace: str) -> str:
    """Returns a JWT token. Call at the start of every sync run — tokens last ~1 hour.

    The auth endpoint requires the X-Organization-Namespace header; without it the
    server responds 400 {"type":"namespace_not_found"}.
    """
    r = httpx.post(
        CC_AUTH_URL,
        json={"email": email, "password": password},
        headers={"X-Organization-Namespace": namespace},
        timeout=15,
    )
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
          pageInfo { hasPreviousPage startCursor }
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

        # Paging backwards through history: hasPreviousPage tells us if older
        # trips exist; startCursor points at the oldest trip in the current
        # window. Passing it as `before:` fetches the page that precedes it.
        if not page_info["hasPreviousPage"]:
            break
        cursor = page_info["startCursor"]

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
        token = authenticate(email, password, namespace)
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
