# Driving Heatmap — Frontend

Svelte 5 single-page app that renders GPS trip routes as a Strava-style heatmap
with additive blending on a dark basemap.

## Stack

| Layer       | Technology                              |
| ----------- | --------------------------------------- |
| Framework   | Svelte 5 (runes, no SvelteKit)          |
| Bundler     | Vite 8                                  |
| Styling     | Tailwind CSS 4 (CSS-based config)       |
| Map tiles   | MapLibre GL JS 5 + CARTO dark-matter    |
| Overlay     | deck.gl 9 PathLayer (additive blending) |
| Language    | TypeScript 6                            |
| Package mgr | Bun                                     |

## Development

```bash
cd frontend
bun install
bun run dev        # http://localhost:5173 — proxies /api to :8000
```

The Vite dev server proxies `/api/*` to `http://localhost:8000` so the API
container must be running (`docker compose up -d api`).

## Production build

```bash
bun run build      # outputs to dist/
bun run preview    # serve the production build locally
```

## Docker

The multi-stage Dockerfile builds with Bun and serves via nginx:alpine.
Nginx proxies `/api/` to the `api` container and serves the SPA with
`try_files` fallback.

```bash
# From the repo root:
docker compose up -d --build frontend   # http://localhost:3000
```

## Type checking

```bash
bun run check      # runs svelte-check + tsc
```
