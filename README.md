# driving-heatmap

A personal driving heatmap that syncs GPS trip data from the [Connected Cars](https://connectedcars.io/) GraphQL API, stores it in PostgreSQL + PostGIS, and renders a Strava-style heatmap with additive brightness on dark maps and multiply blending on light maps.

## Features

- **Strava-style heatmap** — overlapping routes glow brighter (dark mode) or darken (light mode)
- **Multiple basemaps** — Dark, Light, and Satellite with per-map blending modes
- **Trip browsing** — searchable, sortable trip list with infinite scroll
- **Trip detail** — tabbed view with overview stats, driving events, and speed profile chart
- **Insights dashboard** — aggregate statistics (driving time, distance, trips) with bar charts, odometer history, and parked-vs-driving breakdown
- **Global date filtering** — filter both the heatmap and trip list by date range
- **Map hover tooltips** — hover over any route to see trip details
- **Time animation** — slider to animate routes appearing chronologically
- **Automatic sync** — background service pulls new trips every 6 hours
- **Vehicle selector** — multi-vehicle support with per-vehicle filtering

## Architecture

```
┌────────────┐     ┌──────────┐     ┌──────────┐     ┌──────────────┐
│ Connected  │────>│  Sync    │────>│ PostGIS  │<────│   FastAPI    │
│ Cars API   │     │ (Python) │     │   DB     │     │     API      │
└────────────┘     └──────────┘     └──────────┘     └──────┬───────┘
                                                            │
                                                     ┌──────┴───────┐
                                                     │    Svelte    │
                                                     │  (nginx)     │
                                                     └──────────────┘
```

Four Docker containers: **PostGIS** database, **Python sync** service (APScheduler), **FastAPI** REST API, and **Svelte 5 SPA** served by nginx.

## Quick start

Prerequisites: [Docker](https://docs.docker.com/get-docker/) with Compose v2.

```bash
git clone https://github.com/johannesmols/driving-heatmap.git
cd driving-heatmap
cp .env.example .env
# Edit .env — set DB_PASSWORD, CC_EMAIL, CC_PASSWORD, PGADMIN_PASSWORD
docker compose up -d --build
```

Open <http://localhost:3000>. The sync service will start pulling trips immediately — watch progress with `docker compose logs -f sync`.

### Development

The `compose.override.yaml` automatically adds dev conveniences (exposed ports, pgAdmin):

| Service | Dev URL |
|---------|---------|
| Frontend | <http://localhost:3000> |
| API (Swagger) | <http://localhost:8000/docs> |
| PostgreSQL | `localhost:5432` |
| pgAdmin | <http://localhost:5050> |

For frontend hot-reload during development:

```bash
cd frontend
bun install
bun run dev    # Vite dev server at http://localhost:5173
```

### Production (TrueNAS / server)

Rename or delete `compose.override.yaml` to use the production-baseline `compose.yaml` (no exposed db/api ports, no pgAdmin):

```bash
mv compose.override.yaml compose.override.yaml.bak
docker compose up -d --build
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_PASSWORD` | Yes | — | PostgreSQL password (internal to Docker network) |
| `CC_EMAIL` | Yes | — | Connected Cars account email |
| `CC_PASSWORD` | Yes | — | Connected Cars account password |
| `CC_NAMESPACE` | No | `semler:minvolkswagen` | App namespace (Min Volkswagen DK). Other examples: `semler:minskoda` |
| `SYNC_INTERVAL_HOURS` | No | `6` | Hours between sync runs |
| `FRONTEND_PORT` | No | `3000` | Host port for the web UI |
| `PGADMIN_EMAIL` | No | `admin@local.dev` | pgAdmin login email (dev only) |
| `PGADMIN_PASSWORD` | Yes* | — | pgAdmin login password (*only needed with dev override) |

## API endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check (DB connectivity) |
| `GET /api/stats` | Trip counts, totals, date range. Supports `vehicle_id`, `from`, `to` |
| `GET /api/vehicles` | List vehicles with trip counts |
| `GET /api/trips` | Paginated trip list with search, sort, date range |
| `GET /api/trips/{id}` | Single trip with full route GeoJSON and GPS positions |
| `GET /api/tracks` | GeoJSON FeatureCollection for the heatmap. Supports bbox, simplify, date range |
| `GET /api/insights` | Aggregate statistics by period (30d, month, year) |
| `GET /api/odometer` | Odometer history with year-end prediction |

## Connected Cars compatibility

This project works with any car connected via the [Connected Cars](https://connectedcars.io/) platform. Known compatible apps:

- **Min Volkswagen** (Denmark) — namespace: `semler:minvolkswagen`
- **MySkoda** — namespace: `semler:minskoda`

Set the `CC_NAMESPACE` environment variable to match your app. See [docs/connected-cars-api.md](docs/connected-cars-api.md) for detailed API documentation.

## License

[MIT](LICENSE)
