# Doctor script — prints the exact workspace + Docker Compose context.
# Run BEFORE `docker compose up` to confirm which folder you are wiring.
#
# Usage:  pwsh ./scripts/doctor.ps1   (or)   powershell ./scripts/doctor.ps1

$ErrorActionPreference = "Stop"

# Resolve repo root = parent of this scripts/ folder.
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Write-Host "==== NEXUS doctor ===="
Write-Host "Workspace path     : $repoRoot"
Write-Host "Hostname           : $env:COMPUTERNAME"
Write-Host ""

$composeFile = Join-Path $repoRoot "docker-compose.yml"
if (-not (Test-Path $composeFile)) {
    Write-Host "ERROR: docker-compose.yml not found at $composeFile" -ForegroundColor Red
    exit 1
}

# Compose project name. Prefer COMPOSE_PROJECT_NAME from env, else .env, else
# the top-level `name:` key in the compose file, else the folder name.
$projectName = $env:COMPOSE_PROJECT_NAME
if (-not $projectName) {
    $envFile = Join-Path $repoRoot ".env"
    if (Test-Path $envFile) {
        $line = Get-Content $envFile | Where-Object { $_ -match "^COMPOSE_PROJECT_NAME=" } | Select-Object -First 1
        if ($line) { $projectName = $line.Split("=", 2)[1].Trim() }
    }
}
if (-not $projectName) {
    $line = Get-Content $composeFile | Where-Object { $_ -match "^name:\s*" } | Select-Object -First 1
    if ($line) { $projectName = ($line -replace "^name:\s*", "").Trim() }
}
if (-not $projectName) { $projectName = (Split-Path $repoRoot -Leaf) }

Write-Host "Compose project    : $projectName"
Write-Host "Compose file       : $composeFile"
Write-Host ""

# Show currently-running compose containers across ALL projects so the user
# can spot collisions with sibling clones.
Write-Host "---- All running containers (any project) ----"
try {
    docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Label \"com.docker.compose.project\"}}" 2>$null
} catch {
    Write-Host "docker ps failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "If a container above is labeled with a DIFFERENT project name than '$projectName',"
Write-Host "it belongs to another folder/clone and will NOT see edits in this workspace."
