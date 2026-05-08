@echo off
REM NEXUS dev launcher (Windows) — boots Postgres, Redis, backend, worker, frontend.
setlocal

cd /d "%~dp0"

if not exist ".env" (
  echo [X] .env not found. Copy .env.example to .env and fill in your keys.
  exit /b 1
)

echo [+] booting postgres + redis + backend + worker via docker-compose ...
docker compose up -d postgres redis backend worker
if errorlevel 1 (
  echo [X] docker compose failed. Is Docker Desktop running?
  exit /b 1
)

echo [+] installing frontend deps ...
cd frontend
if not exist "node_modules" (
  call npm install
)

echo [+] starting frontend at http://localhost:5173
call npm run dev

endlocal
