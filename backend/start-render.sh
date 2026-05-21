#!/usr/bin/env bash
# Render free-tier entrypoint: run the Celery worker AND the web server in a
# single free Web Service instance (Render's free plan does not include a
# separate Background Worker). Generation is always triggered by an HTTP
# request, which keeps the instance awake long enough for the co-located
# worker to pick the task off Redis.
#
# The worker runs in the background; uvicorn runs in the foreground as PID 1's
# child so Render's health checks and graceful shutdown target the web server.
set -euo pipefail

# Run DB migrations best-effort (no-op if already current). Never fail the
# boot on a migration hiccup — init_models() also creates tables on startup.
alembic upgrade head 2>/dev/null || echo "start-render: alembic skipped/failed (continuing)"

# Background Celery worker. concurrency=1 keeps RAM under the 512MB free cap.
celery -A workers.celery_app.celery_app worker --loglevel=info --concurrency=1 &

# Foreground web server. Render injects $PORT.
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
