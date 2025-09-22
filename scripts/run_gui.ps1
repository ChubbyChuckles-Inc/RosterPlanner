<#!
.SYNOPSIS
  Convenience launcher for RosterPlanner GUI on Windows PowerShell.
.DESCRIPTION
  Activates local .venv if present (unless -NoVenv specified), ensures PYTHONPATH includes src,
  allows overriding club id / season / data dir, then launches the PyQt6 GUI.
.PARAMETER ClubId
  Numeric club id to load (default 2294).
.PARAMETER Season
  Season year (default 2025).
.PARAMETER DataDir
  Data directory (default ./data or env ROSTERPLANNER_DATA_DIR if set).
.PARAMETER NoVenv
  Skip automatic venv activation.
.EXAMPLE
  ./scripts/run_gui.ps1 -ClubId 2294 -Season 2025
#>
[CmdletBinding()]
param(
    [int]$ClubId = 2294,
    [int]$Season = 2025,
    [string]$DataDir = $(if ($env:ROSTERPLANNER_DATA_DIR) { $env:ROSTERPLANNER_DATA_DIR } else { "data" }),
    [switch]$NoVenv
)

$ErrorActionPreference = 'Stop'

Write-Host "== RosterPlanner GUI Launcher ==" -ForegroundColor Cyan
Write-Host "ClubId=$ClubId Season=$Season DataDir=$DataDir"

# Activate venv if present
if (-not $NoVenv) {
    $venvActivate = Join-Path -Path $PSScriptRoot -ChildPath "..\.venv\Scripts\Activate.ps1"
    if (Test-Path $venvActivate) {
        Write-Host "Activating virtual environment (.venv)..."
        . $venvActivate
    }
    else {
        Write-Host "No .venv found, continuing with current interpreter" -ForegroundColor Yellow
    }
}

# Ensure PyQt6 is available (lightweight check)
try {
    python -c "import importlib, sys;\nimport importlib;\nimport sys;\nimportlib.import_module('PyQt6')" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "PyQt6 not installed. Installing..." -ForegroundColor Yellow
        pip install PyQt6 | Out-Null
    }
}
catch {
    Write-Host "Python not available or pip issue: $_" -ForegroundColor Red
    exit 2
}

# Export environment variables
$env:ROSTERPLANNER_DATA_DIR = $DataDir
$env:PYTHONPATH = "src"

# Launch (club/season currently hardcoded inside launcher; future: parameterize)
Write-Host "Launching GUI..." -ForegroundColor Green
python -m gui
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "GUI exited with code $exitCode" -ForegroundColor Red
}
else {
    Write-Host "GUI exited normally." -ForegroundColor Green
}
exit $exitCode
