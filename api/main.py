import json
import os
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

pool: asyncpg.Pool = None


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    search: Optional[str] = Query(None),
    sort:   Optional[str] = Query("date_desc"),
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
