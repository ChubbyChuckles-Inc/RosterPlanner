param(
    [string]$DatabasePath = ""
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Resolve-Path (Join-Path $scriptDir '..')
Push-Location $root
try {
    if (-not $DatabasePath) {
        if (Test-Path 'rosterplanner.db') { $DatabasePath = 'rosterplanner.db' }
        elseif (Test-Path 'data/rosterplanner.db') { $DatabasePath = 'data/rosterplanner.db' }
        else { Write-Host 'No database path provided and no default found.'; exit 2 }
    }
    Write-Host "Running migration v2 on $DatabasePath" -ForegroundColor Cyan
    python scripts/migrate_v2.py $DatabasePath
}
finally {
    Pop-Location
}
