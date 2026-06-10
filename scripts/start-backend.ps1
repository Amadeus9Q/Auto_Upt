param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [string]$PythonPath = "",
    [switch]$Reload,
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
$PidFile = Join-Path $LogDir "backend.pid"
$OutLog = Join-Path $LogDir "backend.out.log"
$ErrLog = Join-Path $LogDir "backend.err.log"

. (Join-Path $PSScriptRoot "load-env.ps1")
$PythonPath = Resolve-AutoUptPythonPath -PythonPath $PythonPath -RepoRoot $RepoRoot
$PythonPath = Resolve-AutoUptExecutablePath -ExecutablePath $PythonPath -DisplayName "Python"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (Test-Path $PidFile) {
    $ExistingPid = (Get-Content $PidFile -Raw).Trim()
    if ($ExistingPid) {
        $ExistingProcess = Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue
        if ($ExistingProcess) {
            Write-Host "Backend is already running with PID $ExistingPid."
            Write-Host "Docs: http://$HostName`:$Port/docs"
            exit 0
        }
    }
}

$ArgsList = @(
    "-m",
    "uvicorn",
    "backend.app.main:app",
    "--host",
    $HostName,
    "--port",
    $Port.ToString()
)

if ($Reload) {
    $ArgsList += "--reload"
}

Push-Location $RepoRoot
try {
    if ($Foreground) {
        Write-Host "Starting backend in foreground at http://$HostName`:$Port"
        & $PythonPath @ArgsList
        exit $LASTEXITCODE
    }

    Write-Host "Starting backend at http://$HostName`:$Port"
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
        Write-Host "Backend failed to stay running."
        Write-Host "Error log: $ErrLog"
        if (Test-Path $ErrLog) {
            Get-Content -Tail 80 $ErrLog
        }
        exit 1
    }

    Write-Host "Backend started with PID $($Process.Id)."
    Write-Host "Docs: http://$HostName`:$Port/docs"
    Write-Host "Health: http://$HostName`:$Port/health"
    Write-Host "Logs: $OutLog"
}
finally {
    Pop-Location
}
