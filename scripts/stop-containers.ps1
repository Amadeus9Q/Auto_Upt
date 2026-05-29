param(
    [switch]$RemoveVolumes
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $RepoRoot
try {
    if ($RemoveVolumes) {
        Write-Host "Stopping Docker Compose services and removing volumes."
        docker compose down --volumes
    }
    else {
        Write-Host "Stopping Docker Compose services. Volumes will be kept."
        docker compose down
    }

    if ($LASTEXITCODE -ne 0) {
        throw "docker compose down failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
