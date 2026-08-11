#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Compose file not found: $COMPOSE_FILE" >&2
    exit 1
fi

echo "Using compose file: $COMPOSE_FILE"
echo "Rebuilding services..."
docker compose -f "$COMPOSE_FILE" build

echo "Recreating and restarting services..."
docker compose -f "$COMPOSE_FILE" up -d --force-recreate

echo "Done."
exit 0
