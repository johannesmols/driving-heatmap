# CLAUDE.md

## Project overview

Personal driving heatmap — syncs GPS trips from the Connected Cars GraphQL API, stores in PostgreSQL + PostGIS, renders a Strava-style heatmap in the browser.

## Architecture

- **db** — PostGIS 18 + 3.6 (Alpine). Schema in `db/init/001_schema.sql`. Core tables: `vehicles`, `trips` (with route LineString geometry), `positions` (GPS points).
- **sync** — Python 3.13 service (`sync/main.py`). Authenticates with CC API, pages through trips backwards using cursor pagination, writes to PostgreSQL. Runs on startup then every N hours via APScheduler.
- **api** — FastAPI (`api/main.py`). Async with asyncpg connection pool. Endpoints: health, stats, vehicles, trips, tracks (GeoJSON), insights, odometer.
- **frontend** — Svelte 5 SPA (`frontend/src/`). MapLibre GL JS + deck.gl PathLayer for the heatmap. Tailwind CSS 4 + shadcn-svelte for UI. Built with Vite, served by nginx.

## Key decisions

- **PostGIS geometry storage** — routes stored as LineString, not arrays of points. Enables server-side simplification (`ST_SimplifyPreserveTopology`) and bbox filtering (`ST_Intersects`).
- **Additive blending on dark maps, multiply on light** — deck.gl PathLayer `parameters` control WebGL blend modes. Additive (`src-alpha`/`one`) for glow, multiply (`dst`/`zero`) for darkening.
- **Map recreation on basemap switch** — `map.setStyle()` has a known race condition with deck.gl MapboxOverlay. We destroy and recreate the entire map + overlay instead.
- **nginx as reverse proxy** — frontend serves static files and proxies `/api/` to the FastAPI container. No CORS needed.

## Running locally

```bash
cp .env.example .env  # fill in CC_EMAIL, CC_PASSWORD, DB_PASSWORD
docker compose up -d --build
# Frontend: http://localhost:3000
# API docs: http://localhost:8000/docs
```

For frontend dev with hot reload: `cd frontend && bun install && bun run dev`

## CC API docs

See `docs/connected-cars-api.md` for authentication, pagination quirks, and query examples.
