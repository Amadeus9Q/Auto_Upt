param(
    [string[]]$Services = @("postgres", "redis"),
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [string]$PythonPath = "",
    [switch]$Reload,
    [switch]$Foreground,
    [switch]$NoWorker
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "load-env.ps1")

$RepoRoot = Split-Path -Parent $PSScriptRoot
$StartContainers = Join-Path $PSScriptRoot "start-containers.ps1"
$StartBackend = Join-Path $PSScriptRoot "start-backend.ps1"
$StartWorker = Join-Path $PSScriptRoot "start-worker.ps1"

$PythonPath = Resolve-AutoUptPythonPath -PythonPath $PythonPath -RepoRoot $RepoRoot
$PythonPath = Resolve-AutoUptExecutablePath -ExecutablePath $PythonPath -DisplayName "Python"

& $StartContainers -Services $Services

$BackendParams = @{
    HostName = $HostName
    Port = $Port
    PythonPath = $PythonPath
}

if ($Reload) {
    $BackendParams.Reload = $true
}

if ($Foreground) {
    $BackendParams.Foreground = $true
}

& $StartBackend @BackendParams

if (-not $NoWorker -and -not $Foreground) {
    & $StartWorker -PythonPath $PythonPath
}
