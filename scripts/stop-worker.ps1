$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
$PidFile = Join-Path $LogDir "worker.pid"

function Stop-WorkerProcess {
    param([int]$ProcessId)

    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $Process) {
        return $false
    }

    Write-Host "Stopping Celery worker PID $ProcessId."
    Stop-Process -Id $ProcessId -Force
    return $true
}

$Stopped = $false

if (Test-Path $PidFile) {
    $ExistingPid = (Get-Content $PidFile -Raw).Trim()
    if ($ExistingPid) {
        $Stopped = Stop-WorkerProcess -ProcessId ([int]$ExistingPid)
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
}

if ($Stopped) {
    Write-Host "Celery worker stopped."
}
else {
    Write-Host "No Celery worker process found."
}
