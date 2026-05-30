param(
    [int]$Port = 8000,
    [switch]$ByPort
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
$PidFile = Join-Path $LogDir "backend.pid"

function Stop-BackendProcess {
    param([int]$ProcessId)

    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $Process) {
        return $false
    }

    Write-Host "Stopping backend process PID $ProcessId."
    Stop-Process -Id $ProcessId -Force
    return $true
}

$Stopped = $false

if (Test-Path $PidFile) {
    $ExistingPid = (Get-Content $PidFile -Raw).Trim()
    if ($ExistingPid) {
        $Stopped = Stop-BackendProcess -ProcessId ([int]$ExistingPid)
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue
}

if (-not $Stopped -and $ByPort) {
    $MatchingLines = netstat -ano | Select-String ":$Port\s+.*LISTENING"
    foreach ($Line in $MatchingLines) {
        $Parts = ($Line.ToString() -split "\s+") | Where-Object { $_ }
        $PortPid = [int]$Parts[-1]
        if (Stop-BackendProcess -ProcessId $PortPid) {
            $Stopped = $true
        }
    }
}

if ($Stopped) {
    Write-Host "Backend stopped."
}
else {
    Write-Host "No backend process found."
    if (-not $ByPort) {
        Write-Host "Use -ByPort to also stop any process listening on port $Port."
    }
}
