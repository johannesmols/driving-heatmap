# driving-heatmap

Personal driving heatmap: pulls GPS trips from the Connected Cars GraphQL API,
stores them in PostgreSQL + PostGIS, and renders a Strava-style heatmap.

Full design lives in [plan.md](plan.md).

## Repo layout

```
driving-heatmap/
├── compose.yaml            # full stack (db + sync; api/frontend added later)
├── .env.example            # copy to .env and fill in
├── db/init/                # SQL auto-run on first PostGIS container start
├── sync/                   # Python trip-sync service (Phase 1)
├── api/                    # FastAPI server (Phase 2)
└── frontend/               # Svelte 5 SPA   (Phase 3 — placeholder)
```

## Local dev quickstart

Prerequisites: Docker Desktop (or Docker Engine + Compose v2).

```bash
cp .env.example .env
# edit .env: set DB_PASSWORD, CC_EMAIL, CC_PASSWORD

docker compose up -d db
docker compose logs -f db          # wait for "ready to accept connections"

docker compose up -d --build sync
docker compose logs -f sync        # watch the initial backfill

docker compose up -d --build api
open http://localhost:8000/docs    # Swagger UI
```

Inspect the database via psql:

```bash
docker compose exec db psql -U heatmap -d heatmap -c "\dt"
docker compose exec db psql -U heatmap -d heatmap -c "SELECT COUNT(*) FROM trips;"
```

Or open pgAdmin at <http://localhost:5050>. Log in with `PGADMIN_EMAIL` /
`PGADMIN_PASSWORD` from `.env`. The `driving-heatmap` server is pre-registered
via [db/pgadmin/servers.json](db/pgadmin/servers.json); enter the PostgreSQL
password (`DB_PASSWORD`) the first time you connect.

## Phase status

- [x] Phase 0 — plan
- [x] Phase 1 — sync service + database
- [x] Phase 2 — API server
- [ ] Phase 3 — heatmap frontend
- [ ] Phase 4 — Docker Compose hardening + TrueNAS deployment

### Phase 1 backfill results

First full sync against the live Connected Cars API (vehicle: Volkswagen up! id=34881):

- 4,535 trips, 695,841 positions
- Date range: 2022-01-24 → 2026-04-10
- Initial backfill: 470.8s; incremental re-run: ~1.5s (short-circuits on last-synced timestamp)

### Phase 2 endpoints

FastAPI service at <http://localhost:8000>. Swagger UI at <http://localhost:8000/docs>.

| Endpoint | Purpose |
|---|---|
| `GET /api/stats` | counts, total km / fuel, date range |
| `GET /api/trips?from=&to=&limit=&offset=` | paginated trip list, newest first |
| `GET /api/trips/{id}` | single trip with route GeoJSON + chronological positions |
| `GET /api/tracks?from=&to=&bbox=&simplify=` | GeoJSON `FeatureCollection` for the heatmap |

Observed on the Phase 1 dataset: `/api/tracks` returns 4,479 `LineString` features (full detail); `bbox=8,54,13,58` trims to 4,331; `simplify=0.001` reduces a sample route from 37 → 2 coordinates.
