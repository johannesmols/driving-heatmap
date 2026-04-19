#!/usr/bin/env bash
# Daily PostgreSQL backup for the driving-heatmap database.
# Schedule as a cron job: 0 3 * * * /path/to/driving-heatmap/scripts/backup.sh
#
# Keeps the last 7 backups and deletes older ones.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
KEEP_DAYS=7

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/heatmap_${TIMESTAMP}.dump"

echo "[$(date)] Starting backup..."
docker compose -f "$PROJECT_DIR/compose.yaml" exec -T db \
  pg_dump -U heatmap -d heatmap --format=custom > "$BACKUP_FILE"

echo "[$(date)] Backup saved: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# Clean up old backups
find "$BACKUP_DIR" -name "heatmap_*.dump" -mtime +$KEEP_DAYS -delete
echo "[$(date)] Cleaned backups older than $KEEP_DAYS days."
