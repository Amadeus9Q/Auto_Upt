param(
    [int]$Port = 8000,
    [switch]$RemoveVolumes
)

$ErrorActionPreference = "Stop"

$StopBackend = Join-Path $PSScriptRoot "stop-backend.ps1"
$StopContainers = Join-Path $PSScriptRoot "stop-containers.ps1"

& $StopBackend -Port $Port -ByPort

if ($RemoveVolumes) {
    & $StopContainers -RemoveVolumes
}
else {
    & $StopContainers
}
