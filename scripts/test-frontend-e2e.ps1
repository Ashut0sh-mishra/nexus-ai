#requires -Version 5.1
<#
.SYNOPSIS
    Reproducible runner for the frontend Playwright visual-regression gate.

.DESCRIPTION
    - Installs npm deps if node_modules/.package-lock.json is missing.
    - Installs the Playwright chromium browser binary if missing.
    - Runs the gallery snapshot suite (every canonical layout + alias
      coverage + zero-warning console check).
    - Pass -UpdateSnapshots to regenerate baselines (do this only when
      you've intentionally changed the renderer or added a new layout).

.EXAMPLE
    pwsh ./scripts/test-frontend-e2e.ps1

.EXAMPLE
    pwsh ./scripts/test-frontend-e2e.ps1 -UpdateSnapshots
#>

[CmdletBinding()]
param(
    [switch] $UpdateSnapshots,
    [switch] $SkipInstall
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $repoRoot 'frontend'

if (-not (Test-Path $frontend)) {
    throw "Cannot find frontend folder at $frontend"
}

Push-Location $frontend
try {
    if (-not $SkipInstall) {
        if (-not (Test-Path 'node_modules/@playwright/test')) {
            Write-Host '[e2e] Installing npm dependencies...' -ForegroundColor Cyan
            npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install failed (exit $LASTEXITCODE)" }
        }

        # Playwright browser binary (chromium only — we don't test other engines).
        $cacheDir = Join-Path $env:USERPROFILE 'AppData\Local\ms-playwright'
        $hasChromium = (Test-Path $cacheDir) -and (Get-ChildItem $cacheDir -Filter 'chromium-*' -Directory -ErrorAction SilentlyContinue)
        if (-not $hasChromium) {
            Write-Host '[e2e] Installing Playwright chromium...' -ForegroundColor Cyan
            npx playwright install chromium
            if ($LASTEXITCODE -ne 0) { throw "playwright install failed (exit $LASTEXITCODE)" }
        }
    }

    $script = if ($UpdateSnapshots) { 'test:e2e:update' } else { 'test:e2e' }
    Write-Host "[e2e] npm run $script" -ForegroundColor Cyan
    npm run $script
    if ($LASTEXITCODE -ne 0) {
        throw "Playwright suite failed (exit $LASTEXITCODE). See frontend/playwright-report for traces."
    }

    Write-Host '[e2e] Pass.' -ForegroundColor Green
}
finally {
    Pop-Location
}
