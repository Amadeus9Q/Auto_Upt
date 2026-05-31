# Restart full stack: Stop all -> Start backend -> Build & Dev frontend
param([switch]$NoFrontend)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Push-Location $Root
try {
    Write-Host "`n[1/4] Stopping all services..." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "stop.ps1")
    if ($LASTEXITCODE -ne 0) { Write-Host "[WARN] stop.ps1 non-zero exit" -ForegroundColor DarkYellow }

    Write-Host "`n[2/4] Starting backend services..." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "start.ps1")
    if ($LASTEXITCODE -ne 0) { Write-Host "[WARN] start.ps1 non-zero exit" -ForegroundColor DarkYellow }
}
finally { Pop-Location }

if (-not $NoFrontend) {
    Push-Location (Join-Path $Root "frontend")
    try {
        Write-Host "`n[3/4] Building frontend..." -ForegroundColor Yellow
        npm run build
        if ($LASTEXITCODE -ne 0) { Write-Error "Frontend build failed!"; exit $LASTEXITCODE }

        Write-Host "`n[4/4] Starting frontend dev server..." -ForegroundColor Yellow
        npm run dev
    }
    finally { Pop-Location }
}

Write-Host "`n[DONE] Full stack restart completed." -ForegroundColor Green
