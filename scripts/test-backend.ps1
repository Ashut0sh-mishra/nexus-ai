# Run backend tests against THIS workspace.
# Builds the dev image if missing, then mounts the local backend/ folder.
#
# Usage:  pwsh ./scripts/test-backend.ps1

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $repoRoot "backend"
$benchmarksDir = Join-Path $repoRoot "benchmarks"
$liveEvalDir = Join-Path $repoRoot "audits\LIVE_EVAL_RESULTS"

# Ensure prod image exists (dev image FROMs it).
$prodImg = "nexus-ai-backend:latest"
$devImg  = "nexus-ai-backend:dev"

function Test-DockerImage {
    param([string]$Image)
    # Run image inspect in a way that does NOT terminate the script when the
    # image is missing. With $ErrorActionPreference = "Stop", stderr from a
    # native command (`docker image inspect`) is escalated to a terminating
    # error. We locally relax that and gate purely on $LASTEXITCODE:
    # 0 == found, non-zero == missing.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        docker image inspect $Image *> $null
    } finally {
        $ErrorActionPreference = $prev
    }
    return ($LASTEXITCODE -eq 0)
}

if (-not (Test-DockerImage $prodImg)) {
    Write-Host "Building $prodImg ..."
    docker build -t $prodImg $backendDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not (Test-DockerImage $devImg)) {
    Write-Host "Building $devImg ..."
    docker build -f (Join-Path $backendDir "Dockerfile.dev") -t $devImg $backendDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Workspace : $repoRoot"
Write-Host "Mounting  : $backendDir -> /app"
Write-Host "Mounting  : $benchmarksDir -> /benchmarks (ro)"
if (Test-Path $liveEvalDir) {
    Write-Host "Mounting  : $liveEvalDir -> /live_eval_results (ro)"
}

if (-not (Test-Path $benchmarksDir)) {
    Write-Error "Benchmarks directory not found at $benchmarksDir. Phase 6B benchmark tests require this folder to be mounted into the container at /benchmarks."
    exit 1
}

$dockerArgs = @(
    "run", "--rm",
    "-v", "${backendDir}:/app",
    "-v", "${benchmarksDir}:/benchmarks:ro"
)
if (Test-Path $liveEvalDir) {
    $dockerArgs += @("-v", "${liveEvalDir}:/live_eval_results:ro")
}
$dockerArgs += @(
    "-w", "/app",
    "-e", "PYTHONPATH=/app",
    "-e", "DATABASE_URL=sqlite+aiosqlite:///:memory:",
    $devImg,
    "python", "-m", "pytest", "-q"
)

docker @dockerArgs
