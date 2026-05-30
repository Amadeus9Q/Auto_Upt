param(
    [string]$PythonPath = "C:\Users\17325\.conda\envs\auto_upt\python.exe",
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
$OutLog = Join-Path $LogDir "worker.out.log"

if (-not (Test-Path $PythonPath)) {
    throw "Python executable not found: $PythonPath"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$ArgsList = @(
    "-m",
    "celery",
    "-A",
    "backend.app.tasks.celery_app.celery_app",
    "worker",
    "--loglevel=info",
    "--logfile=$OutLog",
    "--pool=threads",
    "--concurrency=1",
    "--without-mingle"
)

Push-Location $RepoRoot
try {
    Write-Host "Starting Celery worker in foreground."
    Write-Host "Press Ctrl+C to stop the worker."
    Write-Host "Logs: $OutLog"
    & $PythonPath @ArgsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
