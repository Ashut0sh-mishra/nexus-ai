# NEXUS live-eval harness wrapper (Phase 6D).
#
# Refuses to run without explicit opt-in:
#   $env:NEXUS_RUN_LIVE_EVAL = "true"
#
# Without the opt-in flag this script will exit non-zero. Live evaluation
# is NOT part of the normal backend test gate.
#
# Usage examples:
#   .\scripts\run-live-eval.ps1                           # all prompts (will fail without flag)
#   .\scripts\run-live-eval.ps1 -PromptId biz-001         # single prompt
#   $env:NEXUS_RUN_LIVE_EVAL = "true";                    `
#       .\scripts\run-live-eval.ps1 -PromptId biz-001     # actual live call (still requires
#                                                         # /api/generate wiring; see Phase 6D notes)

[CmdletBinding()]
param(
    [string]$PromptId = "",
    [string]$BaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

$repoRoot   = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $repoRoot "backend"
$benchmarksDir = Join-Path $repoRoot "benchmarks"
$evalsHostDir  = Join-Path $backendDir "storage\evals"
$devImg     = "nexus-ai-backend:dev"

if (-not (Test-Path $benchmarksDir)) {
    Write-Error "Benchmarks directory not found at $benchmarksDir."
    exit 1
}
if (-not (Test-Path $evalsHostDir)) {
    New-Item -ItemType Directory -Force -Path $evalsHostDir | Out-Null
}

$flag = $env:NEXUS_RUN_LIVE_EVAL
if (-not $flag -or $flag.ToLower() -ne "true") {
    Write-Host "[run-live-eval] NEXUS_RUN_LIVE_EVAL is not 'true' — the harness will refuse." -ForegroundColor Yellow
}

$args = @("-m", "scripts.run_live_eval", "--base-url", $BaseUrl)
if ($PromptId) { $args += @("--prompt-id", $PromptId) }

docker run --rm `
    -v "${backendDir}:/app" `
    -v "${benchmarksDir}:/benchmarks:ro" `
    -w /app `
    -e PYTHONPATH=/app `
    -e NEXUS_RUN_LIVE_EVAL="$($env:NEXUS_RUN_LIVE_EVAL)" `
    -e NEXUS_EVAL_OUTPUT_DIR="/app/storage/evals" `
    $devImg `
    python @args

exit $LASTEXITCODE
