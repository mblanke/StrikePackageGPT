# StrikePackageGPT Pre-flight Check

$AllPassed = $true

function Show-Check {
    param([string]$Name, [bool]$Passed, [string]$Message)
    if ($Passed) {
        Write-Host "  [OK] $Name" -ForegroundColor Green
        if ($Message) { Write-Host "       $Message" -ForegroundColor DarkGray }
    } else {
        Write-Host "  [X]  $Name" -ForegroundColor Red
        if ($Message) { Write-Host "       $Message" -ForegroundColor Yellow }
        $script:AllPassed = $false
    }
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "         StrikePackageGPT Pre-flight Check              " -ForegroundColor Cyan  
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Hardware
Write-Host "  HARDWARE" -ForegroundColor White
Write-Host "  --------" -ForegroundColor DarkGray
$os = Get-CimInstance Win32_OperatingSystem
$ram = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
Show-Check "RAM: ${ram}GB" ($ram -ge 8) ""
$disk = [math]::Round((Get-PSDrive (Get-Location).Drive.Name).Free / 1GB, 1)
Show-Check "Disk: ${disk}GB free" ($disk -ge 20) ""

Write-Host ""

# Docker
Write-Host "  DOCKER" -ForegroundColor White
Write-Host "  ------" -ForegroundColor DarkGray
$dockerOk = $null -ne (Get-Command docker -ErrorAction SilentlyContinue)
Show-Check "Docker installed" $dockerOk ""
$dockerRun = $false
if ($dockerOk) { try { docker info 2>$null | Out-Null; $dockerRun = $true } catch {} }
Show-Check "Docker running" $dockerRun ""

Write-Host ""

# Containers
Write-Host "  CONTAINERS" -ForegroundColor White  
Write-Host "  ----------" -ForegroundColor DarkGray
if ($dockerRun) {
    $containers = @("dashboard","hackgpt-api","llm-router","kali","kali-executor")
    foreach ($c in $containers) {
        $name = "strikepackage-$c"
        $status = docker ps --filter "name=$name" --format "{{.Status}}" 2>$null
        if ($status) {
            Show-Check $name $true $status
        } else {
            Write-Host "  [ ]  $name - Not running" -ForegroundColor DarkGray
        }
    }
}

Write-Host ""

# Ollama
Write-Host "  OLLAMA" -ForegroundColor White
Write-Host "  ------" -ForegroundColor DarkGray
try {
    $r = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -ErrorAction Stop
    $m = ($r.models | ForEach-Object { $_.name }) -join ", "
    Show-Check "Local Ollama" $true $m
} catch {
    Write-Host "  [ ]  Local Ollama - Not running" -ForegroundColor DarkGray
}
try {
    $r = Invoke-RestMethod -Uri "http://192.168.1.50:11434/api/tags" -TimeoutSec 3 -ErrorAction Stop
    $m = ($r.models | ForEach-Object { $_.name }) -join ", "
    Show-Check "Dell LLM Box" $true $m
} catch {
    Write-Host "  [ ]  Dell LLM Box - Not reachable" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor DarkGray
if ($AllPassed) {
    Write-Host "  ALL CHECKS PASSED!" -ForegroundColor Green
} else {
    Write-Host "  Some checks failed" -ForegroundColor Yellow
}
Write-Host ""
