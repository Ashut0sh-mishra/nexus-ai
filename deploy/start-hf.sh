#!/usr/bin/env bash
# Hugging Face Space entrypoint: Redis + Celery worker + uvicorn in one
# container. HF routes external traffic to port 7860.
set -uo pipefail

# 1) Local Redis broker (Celery + SSE pub/sub). Run in background; ephemeral.
echo "start-hf: launching redis ..."
redis-server --port 6379 --save "" --appendonly no &

# Wait until Redis answers PING before starting Celery (avoids a startup race
# where the worker gives up connecting before the broker is ready).
for i in $(seq 1 40); do
  if redis-cli -p 6379 ping >/dev/null 2>&1; then
    echo "start-hf: redis ready"
    break
  fi
  sleep 0.5
done

# 2) Celery worker in the background.
#    --pool=solo runs tasks in the worker's main process with NO forking.
#    The default prefork pool forks child workers, which misbehaves under
#    PID 1 in a single HF container (zombies aren't reaped; forked children
#    can fail to consume). solo is the reliable choice for one concurrency.
echo "start-hf: launching celery worker (solo pool) ..."
celery -A workers.celery_app.celery_app worker \
  --loglevel=info --pool=solo --concurrency=1 &

# 3) Web server in the foreground on HF's port (7860). init_models() creates
#    the SQLite schema on startup, so no migration step is needed.
echo "start-hf: launching uvicorn ..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-7860}" --workers 1
