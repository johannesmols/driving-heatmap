import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, date
from typing import Optional

import asyncpg
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

pool: asyncpg.Pool = None


def parse_dt(s: str) -> datetime:
    """Parse an ISO 8601 string into a datetime for asyncpg."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


async def _init_connection(conn: asyncpg.Connection) -> None:
    # asyncpg returns PG json/jsonb as str by default; decode to dict/list so
    # ST_AsGeoJSON(...)::json values embed as real GeoJSON objects, not escaped strings.
    for typename in ("json", "jsonb"):
        await conn.set_type_codec(
            typename,
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(
        os.environ["DATABASE_URL"],
        min_size=2,
        max_size=10,
        init=_init_connection,
    )
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)
# No CORS middleware needed — nginx proxies /api/ as same-origin.
# During local dev, vite.config.ts proxies /api to localhost:8000.


@app.get("/api/health")
async def health():
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok"}


@app.get("/api/stats")
async def get_stats(
    vehicle_id: Optional[str] = Query(None),
    from_:      Optional[str] = Query(None, alias="from"),
    to:         Optional[str] = Query(None),
):
    conditions, params = ["1=1"], []
    if vehicle_id:
        params.append(vehicle_id)
        conditions.append(f"vehicle_id = ${len(params)}")
    if from_:
        params.append(parse_dt(from_))
        conditions.append(f"started_at >= ${len(params)}")
    if to:
        params.append(parse_dt(to))
        conditions.append(f"started_at <= ${len(params)}")
    where = " AND ".join(conditions)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(f"""
            SELECT
                COUNT(*)                            AS trip_count,
                ROUND(SUM(mileage_km)::numeric, 1)  AS total_km,
                ROUND(SUM(COALESCE(fuel_used_l, 0))::numeric, 1) AS total_fuel_l,
                MIN(started_at)                     AS oldest_trip,
                MAX(started_at)                     AS newest_trip,
                (SELECT COUNT(*) FROM positions p
                 JOIN trips t2 ON p.trip_id = t2.id
                 WHERE {where.replace('vehicle_id', 't2.vehicle_id').replace('started_at', 't2.started_at')}) AS position_count
            FROM trips
            WHERE {where}
        """, *params)
    return dict(row)


@app.get("/api/vehicles")
async def list_vehicles():
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT v.id, v.make, v.model, v.year, v.license_plate,
                   COUNT(t.id) AS trip_count,
                   ROUND(COALESCE(SUM(t.mileage_km), 0)::numeric, 1) AS total_km
            FROM vehicles v
            LEFT JOIN trips t ON t.vehicle_id = v.id
            GROUP BY v.id
            ORDER BY v.license_plate
        """)
    return [dict(r) for r in rows]


@app.get("/api/trips")
async def list_trips(
    from_:      Optional[str] = Query(None, alias="from"),
    to:         Optional[str] = Query(None),
    search:     Optional[str] = Query(None),
    sort:       Optional[str] = Query("date_desc"),
    vehicle_id: Optional[str] = Query(None),
    limit:      int           = Query(50, le=500),
    offset:     int           = Query(0),
):
    conditions, params = ["1=1"], []

    if vehicle_id:
        params.append(vehicle_id)
        conditions.append(f"vehicle_id = ${len(params)}")

    if from_:
        params.append(parse_dt(from_))
        conditions.append(f"started_at >= ${len(params)}")
    if to:
        params.append(parse_dt(to))
        conditions.append(f"started_at <= ${len(params)}")
    if search:
        params.append(f"%{search}%")
        idx = len(params)
        conditions.append(f"(start_address ILIKE ${idx} OR end_address ILIKE ${idx})")

    sort_clauses = {
        "date_desc": "started_at DESC",
        "date_asc": "started_at ASC",
        "distance_desc": "mileage_km DESC NULLS LAST",
        "duration_desc": "duration_min DESC NULLS LAST",
    }
    order_by = sort_clauses.get(sort, "started_at DESC")

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
            ORDER BY {order_by}
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
    from_:      Optional[str]   = Query(None, alias="from"),
    to:         Optional[str]   = Query(None),
    vehicle_id: Optional[str]   = Query(None),
    bbox:       Optional[str]   = Query(None, description="minLng,minLat,maxLng,maxLat"),
    simplify:   Optional[float] = Query(None, description="Simplification tolerance in degrees. "
                                        "0.001 = zoom ~10, 0.01 = zoom ~8, omit for full detail"),
):
    """
    Returns all trip routes as a GeoJSON FeatureCollection.
    This is the primary endpoint consumed by the heatmap frontend.
    PostGIS does all geometry work server-side; the frontend receives ready-to-render GeoJSON.
    """
    conditions, params = ["route IS NOT NULL"], []

    if vehicle_id:
        params.append(vehicle_id)
        conditions.append(f"vehicle_id = ${len(params)}")

    if from_:
        params.append(parse_dt(from_))
        conditions.append(f"started_at >= ${len(params)}")
    if to:
        params.append(parse_dt(to))
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
            SELECT id, started_at, mileage_km, duration_min,
                   start_address, end_address,
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
                "duration_min": row["duration_min"],
                "start_address": row["start_address"],
                "end_address": row["end_address"],
            },
        }
        for row in rows
        if row["geometry"] is not None
    ]

    return {"type": "FeatureCollection", "features": features}


@app.get("/api/insights")
async def get_insights(
    vehicle_id: Optional[str] = Query(None),
    period:     str           = Query("year", description="30d, month, or year"),
    year:       Optional[int] = Query(None),
    month:      Optional[int] = Query(None),
):
    now = datetime.now()
    if period == "30d":
        dt_from = now - timedelta(days=30)
        dt_to = now
        trunc = "day"
    elif period == "month":
        y = year or now.year
        m = month or now.month
        dt_from = datetime(y, m, 1)
        if m == 12:
            dt_to = datetime(y + 1, 1, 1)
        else:
            dt_to = datetime(y, m + 1, 1)
        trunc = "week"
    else:  # year
        y = year or now.year
        dt_from = datetime(y, 1, 1)
        dt_to = datetime(y + 1, 1, 1)
        trunc = "month"

    total_period_hours = (dt_to - dt_from).total_seconds() / 3600

    conditions, params = ["1=1"], []
    if vehicle_id:
        params.append(vehicle_id)
        conditions.append(f"vehicle_id = ${len(params)}")
    params.append(dt_from)
    conditions.append(f"started_at >= ${len(params)}")
    params.append(dt_to)
    conditions.append(f"started_at < ${len(params)}")
    where = " AND ".join(conditions)

    async with pool.acquire() as conn:
        summary = await conn.fetchrow(f"""
            SELECT
                COALESCE(SUM(duration_min), 0)::int         AS total_driving_time_min,
                ROUND(COALESCE(SUM(mileage_km), 0)::numeric, 1) AS total_distance_km,
                ROUND(COALESCE(MAX(mileage_km), 0)::numeric, 1) AS longest_trip_km,
                COUNT(*)::int                                AS trip_count,
                ROUND(COALESCE(SUM(fuel_used_l), 0)::numeric, 1) AS total_fuel_l,
                COALESCE(SUM(idle_time_s), 0)::int           AS total_idle_time_s
            FROM trips
            WHERE {where}
        """, *params)

        buckets = await conn.fetch(f"""
            SELECT
                date_trunc('{trunc}', started_at) AS bucket,
                ROUND(COALESCE(SUM(mileage_km), 0)::numeric, 1) AS distance_km,
                COALESCE(SUM(duration_min), 0)::int AS driving_time_min,
                COUNT(*)::int AS trip_count
            FROM trips
            WHERE {where}
            GROUP BY bucket
            ORDER BY bucket
        """, *params)

    driving_hours = (summary["total_driving_time_min"] or 0) / 60
    driving_pct = round(driving_hours / total_period_hours * 100, 1) if total_period_hours > 0 else 0

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def bucket_label(dt_val, trunc_mode):
        if trunc_mode == "month":
            return month_names[dt_val.month - 1]
        elif trunc_mode == "week":
            return f"W{dt_val.isocalendar()[1]}"
        else:
            return dt_val.strftime("%d %b")

    return {
        "period": {"type": period, "year": year or now.year, "month": month},
        "summary": dict(summary),
        "parked_vs_driving": {
            "driving_pct": driving_pct,
            "parked_pct": round(100 - driving_pct, 1),
            "total_period_hours": round(total_period_hours, 1),
        },
        "buckets": [
            {
                "label": bucket_label(row["bucket"], trunc),
                "distance_km": float(row["distance_km"]),
                "driving_time_min": row["driving_time_min"],
                "trip_count": row["trip_count"],
            }
            for row in buckets
        ],
    }


@app.get("/api/odometer")
async def get_odometer(vehicle_id: Optional[str] = Query(None)):
    conditions, params = ["end_odometer_km IS NOT NULL"], []
    if vehicle_id:
        params.append(vehicle_id)
        conditions.append(f"vehicle_id = ${len(params)}")
    where = " AND ".join(conditions)

    async with pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT started_at::date AS date, MAX(end_odometer_km) AS km
            FROM trips
            WHERE {where}
            GROUP BY started_at::date
            ORDER BY date
        """, *params)

    history = [{"date": row["date"].isoformat(), "km": float(row["km"])} for row in rows]

    current_km = history[-1]["km"] if history else 0
    last_updated = history[-1]["date"] if history else None

    # Prediction: linear extrapolation from last 90 days
    daily_avg_km = 0.0
    year_end_km = current_km
    if len(history) >= 2:
        recent = [h for h in history if h["date"] >= (date.today() - timedelta(days=90)).isoformat()]
        if len(recent) >= 2:
            km_diff = recent[-1]["km"] - recent[0]["km"]
            days_diff = (date.fromisoformat(recent[-1]["date"]) - date.fromisoformat(recent[0]["date"])).days
            if days_diff > 0:
                daily_avg_km = round(km_diff / days_diff, 1)
                days_to_year_end = (date(date.today().year, 12, 31) - date.today()).days
                year_end_km = round(current_km + daily_avg_km * days_to_year_end, 0)

    return {
        "current_km": current_km,
        "last_updated": last_updated,
        "history": history,
        "prediction": {
            "year_end_km": year_end_km,
            "daily_avg_km": daily_avg_km,
        },
    }
