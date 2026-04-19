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
├── api/                    # FastAPI server (Phase 2 — placeholder)
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
```

Inspect the database:

```bash
docker compose exec db psql -U heatmap -d heatmap -c "\dt"
docker compose exec db psql -U heatmap -d heatmap -c "SELECT COUNT(*) FROM trips;"
```

## Phase status

- [x] Phase 0 — plan
- [ ] Phase 1 — sync service + database
- [ ] Phase 2 — API server
- [ ] Phase 3 — heatmap frontend
- [ ] Phase 4 — Docker Compose hardening + TrueNAS deployment
