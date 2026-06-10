function Get-AutoUptEnvValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot)
    )

    $EnvPath = Join-Path $RepoRoot ".env"
    if (-not (Test-Path -LiteralPath $EnvPath)) {
        return $null
    }

    foreach ($Line in Get-Content -LiteralPath $EnvPath -Encoding UTF8) {
        $Trimmed = $Line.Trim()
        if (-not $Trimmed -or $Trimmed.StartsWith("#")) {
            continue
        }

        if ($Trimmed -notmatch "^\s*([^=\s]+)\s*=\s*(.*)\s*$") {
            continue
        }

        if ($Matches[1] -ne $Name) {
            continue
        }

        $Value = $Matches[2].Trim()
        if (
            ($Value.StartsWith('"') -and $Value.EndsWith('"')) -or
            ($Value.StartsWith("'") -and $Value.EndsWith("'"))
        ) {
            $Value = $Value.Substring(1, $Value.Length - 2)
        }
        return $Value
    }

    return $null
}

function Resolve-AutoUptPythonPath {
    param(
        [string]$PythonPath,
        [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot)
    )

    if (-not [string]::IsNullOrWhiteSpace($PythonPath)) {
        return $PythonPath.Trim()
    }

    $EnvPythonPath = Get-AutoUptEnvValue -Name "AUTO_UPT_PYTHON_PATH" -RepoRoot $RepoRoot
    if (-not [string]::IsNullOrWhiteSpace($EnvPythonPath)) {
        return $EnvPythonPath.Trim()
    }

    $ProcessPythonPath = [Environment]::GetEnvironmentVariable("AUTO_UPT_PYTHON_PATH")
    if (-not [string]::IsNullOrWhiteSpace($ProcessPythonPath)) {
        return $ProcessPythonPath.Trim()
    }

    return "python"
}

function Resolve-AutoUptExecutablePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExecutablePath,
        [string]$DisplayName = "Executable"
    )

    $Candidate = $ExecutablePath.Trim()
    if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
        return (Resolve-Path -LiteralPath $Candidate).Path
    }

    $Command = Get-Command $Candidate -CommandType Application -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }

    throw "$DisplayName executable not found: $Candidate"
}
