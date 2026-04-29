#!/bin/sh
set -e

echo "[entrypoint] Installing dependencies..."
cd /app/src
bun install

echo "[entrypoint] Building frontend..."
bun run build

echo "[entrypoint] Copying build output to nginx..."
rm -rf /usr/share/nginx/html/*
cp -r /app/src/dist/* /usr/share/nginx/html/

echo "[entrypoint] Starting nginx..."
exec nginx -g 'daemon off;'
