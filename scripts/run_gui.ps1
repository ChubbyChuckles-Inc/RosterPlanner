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
  [switch]$NoVenv,
  [switch]$SafeMode,
  [switch]$VerboseStartup,
  [switch]$ForceUnlock,
  [switch]$ResetLayout,
  [switch]$IgnoreLock,
  [switch]$LockVerbose
)

$ErrorActionPreference = 'Stop'

Write-Host "== RosterPlanner GUI Launcher ==" -ForegroundColor Cyan
Write-Host "ClubId=$ClubId Season=$Season DataDir=$DataDir SafeMode=$SafeMode VerboseStartup=$VerboseStartup"

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

function Test-PythonModule {
  param(
    [Parameter(Mandatory)][string]$Name
  )
  $code = "import importlib,sys; importlib.import_module('$Name')"
  & python -c $code 2>$null
  return ($LASTEXITCODE -eq 0)
}

try {
  if (-not (Test-PythonModule -Name 'PyQt6')) {
    Write-Host "PyQt6 not installed. Installing..." -ForegroundColor Yellow
    pip install PyQt6 | Out-Null
  }
}
catch {
  Write-Host "Python not available or pip issue: $_" -ForegroundColor Red
  exit 2
}

# Export environment variables
if ($ForceUnlock) {
  $lockPath = Join-Path -Path ([IO.Path]::GetTempPath()) -ChildPath 'rosterplanner.lock'
  if (Test-Path $lockPath) {
    try {
      Remove-Item $lockPath -Force -ErrorAction Stop
      Write-Host "Removed stale lock file: $lockPath" -ForegroundColor Yellow
    } catch {
      $errMsg = $_
      Write-Host ("Failed to remove lock file {0}: {1}" -f $lockPath, $errMsg) -ForegroundColor Red
    }
  }
}

$env:ROSTERPLANNER_DATA_DIR = $DataDir
# Merge existing PYTHONPATH if present
if ($env:PYTHONPATH) {
  if ($env:PYTHONPATH.Split([IO.Path]::PathSeparator) -notcontains 'src') {
    $env:PYTHONPATH = "src" + [IO.Path]::PathSeparator + $env:PYTHONPATH
  }
} else {
  $env:PYTHONPATH = 'src'
}

if ($VerboseStartup) {
  Write-Host "PYTHONPATH=$($env:PYTHONPATH)" -ForegroundColor DarkGray
  Write-Host "Using python: $(Get-Command python | Select-Object -ExpandProperty Source)" -ForegroundColor DarkGray
}

if ($ResetLayout) {
  $env:ROSTERPLANNER_RESET_LAYOUT = '1'
  if ($VerboseStartup) { Write-Host "Will reset persisted layout (ROSTERPLANNER_RESET_LAYOUT=1)" -ForegroundColor DarkGray }
}

if ($IgnoreLock) {
  $env:ROSTERPLANNER_IGNORE_LOCK = '1'
  Write-Host "WARNING: Ignoring single-instance lock (ROSTERPLANNER_IGNORE_LOCK=1)" -ForegroundColor Yellow
}
if ($LockVerbose) {
  $env:ROSTERPLANNER_LOCK_VERBOSE = '1'
  if ($VerboseStartup) { Write-Host "Lock verbose diagnostics enabled" -ForegroundColor DarkGray }
}
$lockPath = Join-Path -Path ([IO.Path]::GetTempPath()) -ChildPath 'rosterplanner.lock'
if ($VerboseStartup -and (Test-Path $lockPath)) {
  try {
    $pid = Get-Content $lockPath -ErrorAction Stop
    Write-Host "Existing lock contents: PID=$pid ($lockPath)" -ForegroundColor DarkGray
    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($proc) { Write-Host "Process alive: $($proc.ProcessName) (StartTime=$($proc.StartTime))" -ForegroundColor DarkGray } else { Write-Host "Process not alive (stale candidate)" -ForegroundColor DarkGray }
  } catch {
    Write-Host "Could not read existing lock file ($lockPath): $_" -ForegroundColor DarkGray
  }
}

# Launch (club/season currently hardcoded inside launcher; future: parameterize)
Write-Host "Launching GUI..." -ForegroundColor Green
$argsList = @('-m','gui')
if ($SafeMode) { $argsList += '--safe-mode' }
if ($VerboseStartup) { $argsList += '--verbose-startup' }
python @argsList
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host "GUI exited with code $exitCode" -ForegroundColor Red
}
else {
    Write-Host "GUI exited normally." -ForegroundColor Green
}
exit $exitCode
