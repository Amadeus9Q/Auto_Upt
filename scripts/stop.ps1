param(
    [int]$Port = 8000,
    [switch]$RemoveVolumes
)

$ErrorActionPreference = "Stop"

$StopBackend = Join-Path $PSScriptRoot "stop-backend.ps1"
$StopWorker = Join-Path $PSScriptRoot "stop-worker.ps1"
$StopContainers = Join-Path $PSScriptRoot "stop-containers.ps1"

& $StopBackend -Port $Port -ByPort
& $StopWorker

if ($RemoveVolumes) {
    & $StopContainers -RemoveVolumes
}
else {
    & $StopContainers
}
