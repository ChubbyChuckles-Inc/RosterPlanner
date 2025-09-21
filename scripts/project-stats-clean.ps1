# Table Tennis Scraper Project Statistics
# Analysis of the Python project structure and development metrics

param(
    [switch]$Detailed,
    [switch]$Export,
    [string]$OutputPath = "project-stats-report.txt"
)

function Write-ColorText {
    param([string]$Text, [string]$Color = "White")
    $colors = @{
        "Header" = "Cyan"
        "Success" = "Green" 
        "Warning" = "Yellow"
        "Error" = "Red"
        "Info" = "Blue"
        "Highlight" = "Magenta"
    }
    $colorValue = if ($colors.ContainsKey($Color)) { $colors[$Color] } else { $Color }
    Write-Host $Text -ForegroundColor $colorValue
}

function Format-Number {
    param([int]$Number)
    return $Number.ToString("N0")
}

function Format-Bytes {
    param([long]$Bytes)
    if ($Bytes -gt 1MB) { return "{0:N1} MB" -f ($Bytes / 1MB) }
    elseif ($Bytes -gt 1KB) { return "{0:N1} KB" -f ($Bytes / 1KB) }
    else { return "$Bytes bytes" }
}

function Get-FileStats {
    param([string]$FilePath)
    
    try {
        $content = Get-Content $FilePath -ErrorAction Stop
        $lines = @($content).Count
        $codeLines = 0
        $commentLines = 0
        $blankLines = 0
        
        foreach ($line in $content) {
            $trimmed = $line.Trim()
            if ([string]::IsNullOrWhiteSpace($trimmed)) {
                $blankLines++
            }
            elseif ($trimmed.StartsWith("#")) {
                $commentLines++
            }
            else {
                $codeLines++
            }
        }
        
        return @{
            TotalLines = $lines
            CodeLines = $codeLines
            CommentLines = $commentLines
            BlankLines = $blankLines
            Size = (Get-Item $FilePath).Length
        }
    }
    catch {
        return @{
            TotalLines = 0
            CodeLines = 0
            CommentLines = 0
            BlankLines = 0
            Size = 0
        }
    }
}

function Get-ComplexityMetrics {
    param([string]$FilePath)
    
    try {
        $content = Get-Content $FilePath -Raw -ErrorAction Stop
        
        $classes = ([regex]::Matches($content, "class\s+\w+")).Count
        $functions = ([regex]::Matches($content, "def\s+\w+")).Count
        $imports = ([regex]::Matches($content, "import\s+\w+|from\s+\w+\s+import")).Count
        $conditionals = ([regex]::Matches($content, "\b(if|elif|else|for|while|try|except|finally)\b")).Count
        
        return @{
            Classes = $classes
            Functions = $functions
            Imports = $imports
            Conditionals = $conditionals
        }
    }
    catch {
        return @{
            Classes = 0
            Functions = 0
            Imports = 0
            Conditionals = 0
        }
    }
}

# Main analysis
Write-ColorText "============================================================" "Header"
Write-ColorText "         TABLE TENNIS SCRAPER PROJECT ANALYSIS" "Header"
Write-ColorText "============================================================" "Header"
Write-Host ""

# Initialize counters
$totalFiles = 0
$totalLines = 0
$totalCodeLines = 0
$totalCommentLines = 0
$totalBlankLines = 0
$totalSize = 0
$totalClasses = 0
$totalFunctions = 0
$totalImports = 0
$totalConditionals = 0

$fileDetails = @()
$directoryStats = @{}

# Get project Python files only (exclude external libraries)
$projectDirs = @("src", "tests", "scripts")
$pythonFiles = @()

foreach ($dir in $projectDirs) {
    if (Test-Path $dir) {
        $pythonFiles += Get-ChildItem -Path $dir -Recurse -Include "*.py" | Where-Object { 
            $_.FullName -notlike "*__pycache__*" 
        }
    }
}

# Also include root level Python files
$rootPythonFiles = Get-ChildItem -Path "." -Include "*.py" | Where-Object { 
    $_.FullName -notlike "*__pycache__*" 
}
$pythonFiles += $rootPythonFiles

Write-ColorText "Project Overview:" "Success"
Write-Host "  Total Python files found: $($pythonFiles.Count)"
Write-Host ""

if ($pythonFiles.Count -eq 0) {
    Write-ColorText "No Python files found in the project directories!" "Error"
    Write-Host "Checked directories: $($projectDirs -join ', ')"
    exit 1
}

foreach ($file in $pythonFiles) {
    $stats = Get-FileStats -FilePath $file.FullName
    $complexity = Get-ComplexityMetrics -FilePath $file.FullName
    
    $totalFiles++
    $totalLines += $stats.TotalLines
    $totalCodeLines += $stats.CodeLines
    $totalCommentLines += $stats.CommentLines
    $totalBlankLines += $stats.BlankLines
    $totalSize += $stats.Size
    $totalClasses += $complexity.Classes
    $totalFunctions += $complexity.Functions
    $totalImports += $complexity.Imports
    $totalConditionals += $complexity.Conditionals
    
    # Directory statistics
    $relativePath = $file.FullName.Replace((Get-Location).Path, "").TrimStart("\")
    $directory = if ($relativePath.Contains("\")) { 
        $relativePath.Substring(0, $relativePath.LastIndexOf("\"))
    } else { 
        "root" 
    }
    
    if (-not $directoryStats.ContainsKey($directory)) {
        $directoryStats[$directory] = @{ Files = 0; Lines = 0; Size = 0 }
    }
    $directoryStats[$directory].Files++
    $directoryStats[$directory].Lines += $stats.TotalLines
    $directoryStats[$directory].Size += $stats.Size
    
    $fileDetails += @{
        Path = $relativePath
        Stats = $stats
        Complexity = $complexity
    }
}

# Calculate percentages
$commentPercentage = if ($totalLines -gt 0) { [math]::Round(($totalCommentLines / $totalLines) * 100, 1) } else { 0 }
$codePercentage = if ($totalLines -gt 0) { [math]::Round(($totalCodeLines / $totalLines) * 100, 1) } else { 0 }
$blankPercentage = if ($totalLines -gt 0) { [math]::Round(($totalBlankLines / $totalLines) * 100, 1) } else { 0 }

# File Statistics
Write-ColorText "File Statistics:" "Info"
Write-Host "  Total Files: $(Format-Number $totalFiles)"
Write-Host "  Total Lines: $(Format-Number $totalLines)"
Write-Host "  Code Lines: $(Format-Number $totalCodeLines) ($codePercentage%)"
Write-Host "  Comment Lines: $(Format-Number $totalCommentLines) ($commentPercentage%)"
Write-Host "  Blank Lines: $(Format-Number $totalBlankLines) ($blankPercentage%)"
Write-Host "  Total Size: $(Format-Bytes $totalSize)"
Write-Host ""

# Code Structure Analysis
Write-ColorText "Code Structure Analysis:" "Info"
Write-Host "  Classes: $(Format-Number $totalClasses)"
Write-Host "  Functions: $(Format-Number $totalFunctions)"
Write-Host "  Import Statements: $(Format-Number $totalImports)"
Write-Host "  Control Structures: $(Format-Number $totalConditionals)"
Write-Host ""

# Development Effort Estimation
$hoursPerLine = 1.0 / 15.0
$totalHours = $totalCodeLines * $hoursPerLine
$days = $totalHours / 8
$weeks = $days / 5

Write-ColorText "Development Effort Estimation:" "Highlight"
Write-Host "  Estimated Hours: $([math]::Round($totalHours, 1))"
Write-Host "  Estimated Days: $([math]::Round($days, 1))"
Write-Host "  Estimated Weeks: $([math]::Round($weeks, 1))"
Write-Host "  (Based on ~15 lines of code per hour standard)"
Write-Host ""

# Directory Breakdown
Write-ColorText "Directory Breakdown:" "Info"
$sortedDirs = $directoryStats.GetEnumerator() | Sort-Object { $_.Value.Lines } -Descending
foreach ($dir in $sortedDirs) {
    $dirName = if ($dir.Key -eq "root") { "Root Directory" } else { $dir.Key }
    Write-Host "  $dirName"
    Write-Host "    Files: $($dir.Value.Files) | Lines: $(Format-Number $dir.Value.Lines) | Size: $(Format-Bytes $dir.Value.Size)"
}
Write-Host ""

# Quality Indicators
Write-ColorText "Project Quality Indicators:" "Success"
$qualityScore = 0

# Documentation score
$docScore = if ($commentPercentage -ge 20) { 25 } elseif ($commentPercentage -ge 15) { 20 } elseif ($commentPercentage -ge 10) { 15 } else { 5 }
$qualityScore += $docScore

# Code organization score
$orgScore = if ($directoryStats.Count -ge 5) { 20 } elseif ($directoryStats.Count -ge 3) { 15 } else { 10 }
$qualityScore += $orgScore

# Modularity score
$avgFunctionsPerFile = if ($totalFiles -gt 0) { $totalFunctions / $totalFiles } else { 0 }
$modScore = if ($avgFunctionsPerFile -ge 5) { 20 } elseif ($avgFunctionsPerFile -ge 3) { 15 } else { 10 }
$qualityScore += $modScore

# File size distribution
$avgLinesPerFile = if ($totalFiles -gt 0) { $totalLines / $totalFiles } else { 0 }
$sizeScore = if ($avgLinesPerFile -le 200) { 20 } elseif ($avgLinesPerFile -le 400) { 15 } else { 10 }
$qualityScore += $sizeScore

# Import complexity
$avgImportsPerFile = if ($totalFiles -gt 0) { $totalImports / $totalFiles } else { 0 }
$impScore = if ($avgImportsPerFile -le 5) { 15 } elseif ($avgImportsPerFile -le 10) { 10 } else { 5 }
$qualityScore += $impScore

Write-Host "  Documentation Coverage: $commentPercentage% (Score: $docScore/25)"
Write-Host "  Code Organization: $($directoryStats.Count) directories (Score: $orgScore/20)"
Write-Host "  Modularity: $([math]::Round($avgFunctionsPerFile, 1)) functions/file (Score: $modScore/20)"
Write-Host "  File Size Distribution: $([math]::Round($avgLinesPerFile, 1)) lines/file (Score: $sizeScore/20)"
Write-Host "  Import Complexity: $([math]::Round($avgImportsPerFile, 1)) imports/file (Score: $impScore/15)"
Write-Host ""
Write-ColorText "Overall Quality Score: $qualityScore/100" "Highlight"

$qualityLevel = if ($qualityScore -ge 80) { "Excellent" } 
                elseif ($qualityScore -ge 60) { "Good" } 
                elseif ($qualityScore -ge 40) { "Fair" } 
                else { "Needs Improvement" }
Write-ColorText "Quality Assessment: $qualityLevel" $(if ($qualityScore -ge 60) { "Success" } else { "Warning" })
Write-Host ""

if ($Detailed) {
    Write-ColorText "Top 10 Largest Files:" "Info"
    $sortedFiles = $fileDetails | Sort-Object { $_.Stats.TotalLines } -Descending | Select-Object -First 10
    foreach ($file in $sortedFiles) {
        Write-Host "  $($file.Path)"
        Write-Host "    Lines: $($file.Stats.TotalLines) | Classes: $($file.Complexity.Classes) | Functions: $($file.Complexity.Functions)"
    }
    Write-Host ""
    
    Write-ColorText "Most Complex Files:" "Info"
    $complexFiles = $fileDetails | Sort-Object { $_.Complexity.Conditionals } -Descending | Select-Object -First 10
    foreach ($file in $complexFiles) {
        if ($file.Complexity.Conditionals -gt 0) {
            Write-Host "  $($file.Path)"
            Write-Host "    Control Structures: $($file.Complexity.Conditionals) | Functions: $($file.Complexity.Functions)"
        }
    }
    Write-Host ""
}

# Export option
if ($Export) {
    $reportContent = @"
TABLE TENNIS SCRAPER PROJECT ANALYSIS REPORT
Generated: $(Get-Date)

FILE STATISTICS:
- Total Files: $totalFiles
- Total Lines: $totalLines
- Code Lines: $totalCodeLines ($codePercentage%)
- Comment Lines: $totalCommentLines ($commentPercentage%)
- Blank Lines: $totalBlankLines ($blankPercentage%)
- Total Size: $(Format-Bytes $totalSize)

CODE STRUCTURE:
- Classes: $totalClasses
- Functions: $totalFunctions
- Import Statements: $totalImports
- Control Structures: $totalConditionals

DEVELOPMENT EFFORT:
- Estimated Hours: $([math]::Round($totalHours, 1))
- Estimated Days: $([math]::Round($days, 1))
- Estimated Weeks: $([math]::Round($weeks, 1))

QUALITY SCORE: $qualityScore/100 ($qualityLevel)
"@
    
    $reportContent | Out-File -FilePath $OutputPath -Encoding UTF8
    Write-ColorText "Report exported to: $OutputPath" "Success"
}

Write-Host ""
Write-ColorText "Analysis Complete!" "Success"
Write-ColorText "============================================================" "Header"
