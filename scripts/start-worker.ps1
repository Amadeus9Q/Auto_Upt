param(
    [string]$PythonPath = "",
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
$PidFile = Join-Path $LogDir "worker.pid"
$OutLog = Join-Path $LogDir "worker.out.log"
$ErrLog = Join-Path $LogDir "worker.err.log"

. (Join-Path $PSScriptRoot "load-env.ps1")
$PythonPath = Resolve-AutoUptPythonPath -PythonPath $PythonPath -RepoRoot $RepoRoot
$PythonPath = Resolve-AutoUptExecutablePath -ExecutablePath $PythonPath -DisplayName "Python"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not $Foreground -and (Test-Path $PidFile)) {
    $ExistingPid = (Get-Content $PidFile -Raw).Trim()
    if ($ExistingPid) {
        $ExistingProcess = Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue
        if ($ExistingProcess) {
            Write-Host "Celery worker is already running with PID $ExistingPid."
            Write-Host "Logs: $OutLog"
            exit 0
        }
    }
}

$ArgsList = @(
    "-m",
    "celery",
    "-A",
    "backend.app.tasks.celery_app.celery_app",
    "worker",
    "--loglevel=info",
    "--pool=threads",
    "--concurrency=1",
    "--without-mingle"
)

if (-not $Foreground) {
    $ArgsList += "--logfile=$OutLog"
}

Push-Location $RepoRoot
try {
    if ($Foreground) {
        Write-Host "Starting Celery worker in foreground."
        Write-Host "Press Ctrl+C to stop the worker."
        & $PythonPath @ArgsList
        exit $LASTEXITCODE
    }

    Write-Host "Starting Celery worker in background."
    $Process = Start-Process `
        -FilePath $PythonPath `
        -ArgumentList $ArgsList `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog `
        -WindowStyle Hidden `
        -PassThru

    $Process.Id | Set-Content -Encoding ASCII $PidFile
    Start-Sleep -Seconds 2

    $RunningProcess = Get-Process -Id $Process.Id -ErrorAction SilentlyContinue
    if (-not $RunningProcess) {
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        Write-Host "Celery worker failed to stay running."
        Write-Host "Error log: $ErrLog"
        if (Test-Path $ErrLog) {
            Get-Content -Tail 80 $ErrLog
        }
        exit 1
    }

    Write-Host "Celery worker started with PID $($Process.Id)."
    Write-Host "Logs: $OutLog"
}
finally {
    Pop-Location
}
