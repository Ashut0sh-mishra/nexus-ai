#!/usr/bin/env bash
# Hugging Face Space entrypoint. Single container, port 7860.
#
# Generation runs IN-PROCESS (NEXUS_INLINE_GENERATION=true) — no separate
# Celery worker. We still run a local Redis for SSE pub/sub (the progress
# stream) and as a harmless broker default.
set -uo pipefail

echo "start-hf: launching redis (SSE pub/sub) ..."
redis-server --port 6379 --save "" --appendonly no &

for i in $(seq 1 40); do
  if redis-cli -p 6379 ping >/dev/null 2>&1; then
    echo "start-hf: redis ready"
    break
  fi
  sleep 0.5
done

# Web server in the foreground on HF's port. init_models() creates the
# SQLite schema on startup. Generation runs inline via asyncio in this
# same process (see workers/inline.py), so there is no worker to start.
echo "start-hf: launching uvicorn ..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-7860}" --workers 1
