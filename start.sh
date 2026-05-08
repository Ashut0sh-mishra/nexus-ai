#!/usr/bin/env bash
# NEXUS dev launcher — boots Postgres, Redis, backend, worker, and frontend.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "❌ .env not found. Copy .env.example → .env and fill in your keys."
  exit 1
fi

echo "▶ booting postgres + redis + backend + worker (docker-compose) ..."
docker compose up -d postgres redis backend worker

echo "▶ installing frontend deps ..."
cd frontend
if [ ! -d node_modules ]; then
  npm install
fi

echo "▶ starting frontend (http://localhost:5173) ..."
npm run dev
