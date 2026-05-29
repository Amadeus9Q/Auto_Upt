param(
    [string[]]$Services = @("postgres", "redis")
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $RepoRoot
try {
    Write-Host "Starting Docker Compose services: $($Services -join ', ')"
    docker compose up -d @Services

    if ($LASTEXITCODE -ne 0) {
        throw "docker compose up failed with exit code $LASTEXITCODE"
    }

    docker compose ps @Services
}
finally {
    Pop-Location
}
