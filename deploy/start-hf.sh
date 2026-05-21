#!/usr/bin/env bash
# Hugging Face Space entrypoint: Redis + Celery worker + uvicorn in one
# container. HF routes external traffic to port 7860.
set -euo pipefail

# 1) Local Redis broker (Celery + SSE pub/sub). Daemonize; data is ephemeral.
redis-server --daemonize yes --port 6379 --save "" --appendonly no
echo "start-hf: redis up on :6379"

# 2) Celery worker in the background. concurrency=1 fits the free RAM budget.
celery -A workers.celery_app.celery_app worker --loglevel=info --concurrency=1 &
echo "start-hf: celery worker started"

# 3) Web server in the foreground on HF's port (7860). init_models() creates
#    the SQLite schema on startup, so no migration step is needed.
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-7860}" --workers 1
