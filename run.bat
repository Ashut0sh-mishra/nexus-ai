@echo off
REM ============================================================
REM  NEXUS AI — one-shot dev launcher (Docker Compose)
REM  Usage:
REM    run.bat            -> start everything (default)
REM    run.bat up         -> start everything
REM    run.bat down       -> stop everything (keep data)
REM    run.bat reset      -> stop + wipe DB/storage volumes
REM    run.bat rebuild    -> rebuild backend image and restart
REM    run.bat logs       -> tail backend + worker logs
REM    run.bat ps         -> show container status
REM    run.bat restart    -> restart backend + worker
REM ============================================================
setlocal
cd /d "%~dp0"

set ACTION=%1
if "%ACTION%"=="" set ACTION=up

if /I "%ACTION%"=="up" goto :up
if /I "%ACTION%"=="start" goto :up
if /I "%ACTION%"=="down" goto :down
if /I "%ACTION%"=="stop" goto :down
if /I "%ACTION%"=="reset" goto :reset
if /I "%ACTION%"=="rebuild" goto :rebuild
if /I "%ACTION%"=="logs" goto :logs
if /I "%ACTION%"=="ps" goto :ps
if /I "%ACTION%"=="status" goto :ps
if /I "%ACTION%"=="restart" goto :restart

echo Unknown action: %ACTION%
echo Run "run.bat" with one of: up, down, reset, rebuild, logs, ps, restart
exit /b 1

:up
echo [NEXUS] Starting full stack...
docker compose up -d
if errorlevel 1 exit /b 1
echo.
echo [NEXUS] Containers:
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo.
echo   Frontend : http://localhost:5173
echo   Backend  : http://localhost:8080/api/health
echo   API docs : http://localhost:8080/docs
echo.
echo Run "run.bat logs" to tail backend/worker logs.
exit /b 0

:down
echo [NEXUS] Stopping stack (data preserved)...
docker compose down
exit /b %errorlevel%

:reset
echo [NEXUS] WIPING all volumes (database + storage)...
docker compose down -v
exit /b %errorlevel%

:rebuild
echo [NEXUS] Rebuilding backend image and restarting...
docker compose up -d --build backend worker
exit /b %errorlevel%

:logs
docker compose logs -f backend worker
exit /b %errorlevel%

:ps
docker compose ps
exit /b %errorlevel%

:restart
echo [NEXUS] Restarting backend and worker...
docker compose restart backend worker
exit /b %errorlevel%
