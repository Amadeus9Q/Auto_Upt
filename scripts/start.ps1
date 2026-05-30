param(
    [string[]]$Services = @("postgres", "redis"),
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [string]$PythonPath = "C:\Users\17325\.conda\envs\auto_upt\python.exe",
    [switch]$Reload,
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"

$StartContainers = Join-Path $PSScriptRoot "start-containers.ps1"
$StartBackend = Join-Path $PSScriptRoot "start-backend.ps1"

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
