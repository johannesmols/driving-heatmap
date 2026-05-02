# Deploy

## How it works

Pushes to `main` trigger [.github/workflows/build-and-push.yml](../.github/workflows/build-and-push.yml). It builds three `linux/amd64` images in parallel and pushes them to Docker Hub:

- `johannesmols/driving-heatmap-frontend`
- `johannesmols/driving-heatmap-api`
- `johannesmols/driving-heatmap-sync`

Each push produces two tags: `latest` and `sha-<short>`.

The NAS only needs `compose.yaml`, `.env`, `db/init/`, `db/pgadmin/`, and the `data/` directory.

## One-time setup

1. Create a Docker Hub access token: Docker Hub → Account Settings → Security → New Access Token (read+write).
2. Add two secrets to the GitHub repo (Settings → Secrets and variables → Actions):
   - `DOCKERHUB_USERNAME` = `johannesmols`
   - `DOCKERHUB_TOKEN` = the token from step 1

## Updating the NAS

```bash
cd /path/to/driving-heatmap
git pull            # only needed if compose.yaml or db/init/* changed
docker compose pull
docker compose up -d
docker image prune -f   # optional, frees disk
```

The first time after switching from the old `build:`-based compose, run `docker compose down` once before `up -d` so compose doesn't try to reconcile the old build-tagged containers.

## Rolling back

Edit `compose.yaml`, change one `:latest` to `:sha-abc1234` (the short SHA of the commit you want), then:

```bash
docker compose up -d <service>
```

Find available tags at `https://hub.docker.com/r/johannesmols/driving-heatmap-<service>/tags`.

## Local dev

Full stack with bind-mounted source and uvicorn `--reload`:

```bash
docker compose -f compose.dev.yaml up -d
```

For frontend hot-reload, run Vite separately (it proxies `/api` to `localhost:8000`):

```bash
cd frontend
bun install
bun run dev
```
